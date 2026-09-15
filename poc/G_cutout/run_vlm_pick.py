"""누끼 — 요소 선별 `vlm_pick` (`.venv`에서 실행 · 유료).

규칙 기반(`rule_comp` · `rule_flat`)은 "그래픽인가 사진인가"를 의미로 가르지 못해 한계였다
(그래픽 잔존 27 · 대상 누락 10/57). VLM에게 **덩어리마다 번호를 그려 보여주고 대상 번호를 고르게** 한다.
좌표를 묻지 않는다 — 섹션 분해에서 확인한 방식(결과 문서 8장 ⑩).

대상 (2026-09-14 결정)
    남김   사람 · 제품 · 사진류(피부 전후 확대 · 원료 · 제형 · 현미경)
    버림   그래픽(말풍선 · 배지 · 차트 · 아이콘 · 패널 · 선 · QR) · 도식 · 문서 이미지 · 지운 자국

입력
    덩어리   `birefnet_erased_s50` 마스크를 `rule_comp`와 같은 조건(면적 0.3% 이상)으로 쪼갬 — 번호가 rule_comp와 같음
    이미지   s50 글자 지운 섹션에 덩어리 윤곽·번호를 그려 폭 768px로 줄이고, 높이 2,000px 조각으로 나눔

한 덩어리에 대상과 그래픽이 섞였으면 **남김**(대상 누락이 그래픽 잔존보다 나쁨) — kind를 `혼합`으로 받음.
응답에 빠진 번호도 남김으로 처리하고 기록함.

출력
    results/vlm_pick/views/{section}_{i}.jpg   VLM에 보낸 이미지
    results/vlm_pick/mask/{section}.png · rgba/{section}.png
    results/vlm_pick/vis/{section}.jpg         번호 그린 섹션 | 선별 결과
    results/vlm_pick/answers.json · meta.json
    cache/gemini-3.8-flash/vlm_pick_{지문}/{section}.json

variant
    vlm_pick   rule_comp 덩어리 · 프롬프트 v1
    sam_pick   SAM 2 조각(run_sam_parts.py) · 프롬프트 v2 — **3D 렌더를 대상에 추가**(2026-09-14 결정),
               한 물체가 여러 조각으로 쪼개졌을 수 있음을 알림. 결과는 results/sam_pick/

사용법
    python run_vlm_pick.py --dry-run                       # 이미지·조각 수만 (과금 없음)
    python run_vlm_pick.py --variant sam_pick --dry-run
    python run_vlm_pick.py --sections A000000250199_009_005 A000000219554_002_008
    python run_vlm_pick.py                                  # 덩어리 있는 전 섹션
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
SRC_MASK = RESULTS / "birefnet_erased_s50" / "mask"
SRC_IMG = RESULTS / "_erase_s50" / "erased"
RULE_FEATURES = RESULTS / "rule_comp" / "features.json"
OUT = RESULTS / "vlm_pick"
CACHE = HERE / "cache"

# poc/section_split/run_color_vlm.py — 복사
MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

MIN_AREA = 0.003   # run_rule.py와 같음 — 덩어리 번호를 rule_comp와 맞춤
VIEW_W = 768
CHUNK_H = 2000
PALETTE = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
           (70, 240, 240), (240, 50, 230), (128, 128, 0)]
KINDS = ["사람", "제품", "사진", "혼합", "그래픽", "도식", "문서", "지운 자국"]

SYSTEM = """너는 한국 이커머스 상품 상세페이지의 한 섹션에서 **재배치할 요소**를 고른다.

배경을 지운 뒤 남은 조각마다 **색 윤곽선과 `#번호`**를 그렸다. 페이지 글자는 이미 지웠다.
이미지가 여러 장이면 위에서 아래로 이어진 한 섹션이다.

남길 것 (keep = true)
- 사람 — 얼굴 · 손 · 몸
- 제품 — 용기 · 튜브 · 패키지 · 박스 (인쇄 글자가 지워져 있어도 제품이다)
- 사진 — 피부 전후 확대 사진 · 원료 · 제형(크림 질감) · 현미경 사진 (흑백이어도 사진이다)

버릴 것 (keep = false)
- 그래픽 — 말풍선 · 배지 · 아이콘 · 차트 · 막대 · 표 칸 · 빈 박스 · 테두리 · 선 · 화살표 · QR 코드
- 도식 — 원리 설명 일러스트 · 3D 그래프
- 문서 — 시험성적서 · 논문 · 앱 화면 캡처
- 지운 자국 — 글자를 지운 자리에 남은 흐릿한 얼룩 · 빈 패널

한 조각에 남길 것과 버릴 것이 섞였으면 keep = true, kind = "혼합"으로 답한다.

출력은 JSON 하나. 모든 번호를 빠짐없이 적는다.
{"regions": [{"id": 1, "keep": true, "kind": "사람", "note": "제품을 든 모델"}]}

kind는 사람 · 제품 · 사진 · 혼합 · 그래픽 · 도식 · 문서 · 지운 자국 중 하나. note는 20자 이내."""


SYSTEM_V2 = """너는 한국 이커머스 상품 상세페이지의 한 섹션에서 **재배치할 요소**를 고른다.

배경을 지운 뒤 남은 부분을 **물체 단위 조각**으로 나눠 조각마다 **색 윤곽선과 `#번호`**를 그렸다.
페이지 글자는 이미 지웠다. 이미지가 여러 장이면 위에서 아래로 이어진 한 섹션이다.
**한 물체가 여러 조각으로 쪼개졌을 수 있다** — 사람·제품·사진에 속한 조각은 작아도 빠짐없이 남긴다.

남길 것 (keep = true)
- 사람 — 얼굴 · 머리카락 · 손 · 몸 · 옷
- 제품 — 용기 · 튜브 · 패키지 · 박스 · 뚜껑 (인쇄 글자가 지워져 있어도 제품이다)
- 사진 — 피부 전후 확대 사진 · 원료 · 제형(크림 질감) · 현미경 사진 (흑백이어도 사진이다)
- 3D 렌더 — 오일 방울 · 성분 구체 · 캡슐 같은 입체 렌더 이미지

버릴 것 (keep = false)
- 그래픽 — 말풍선 · 배지 · 아이콘 · 차트 · 막대 · 표 칸 · 빈 박스 · 테두리 · 선 · 화살표 · QR 코드
- 도식 — 원리 설명 일러스트(평면 그림)
- 문서 — 시험성적서 · 논문 · 앱 화면 캡처
- 지운 자국 — 글자를 지운 자리에 남은 흐릿한 얼룩 · 빈 패널

한 조각에 남길 것과 버릴 것이 섞였으면 keep = true, kind = "혼합"으로 답한다.

출력은 JSON 하나. 모든 번호를 빠짐없이 적는다.
{"regions": [{"id": 1, "keep": true, "kind": "사람", "note": "모델 얼굴"}]}

kind는 사람 · 제품 · 사진 · 3D 렌더 · 혼합 · 그래픽 · 도식 · 문서 · 지운 자국 중 하나. note는 20자 이내."""

VARIANTS = {"vlm_pick": {"parts": "rule_comp", "system": SYSTEM},
            "sam_pick": {"parts": "sam_parts", "system": SYSTEM_V2}}
SAM_PARTS = RESULTS / "sam_parts"


def fingerprint(variant: str = "vlm_pick") -> str:
    if variant == "vlm_pick":  # 기존 캐시 지문 유지
        raw = json.dumps({"system": SYSTEM, "model": MODEL["model_id"], "view_w": VIEW_W,
                          "chunk_h": CHUNK_H, "min_area": MIN_AREA, "palette": PALETTE}, ensure_ascii=False)
    else:
        raw = json.dumps({"variant": variant, "system": VARIANTS[variant]["system"], "model": MODEL["model_id"],
                          "view_w": VIEW_W, "chunk_h": CHUNK_H, "palette": PALETTE}, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def sam_components(name: str) -> tuple[np.ndarray, list[dict]]:
    """run_sam_parts.py가 만든 조각 번호 지도 — 번호 = 조각 번호."""
    labels = cv2.imdecode(np.fromfile(str(SAM_PARTS / "labels" / f"{name}.png"), np.uint8), cv2.IMREAD_UNCHANGED).astype(np.int32)
    comps = []
    for i in range(1, int(labels.max()) + 1):
        ys, xs = np.nonzero(labels == i)
        if len(ys):
            comps.append({"id": i, "label": i, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
    return labels, comps


def read(p: Path, flag=cv2.IMREAD_COLOR) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def components(alpha: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """rule_comp와 같은 덩어리 — 번호 순서도 같음."""
    fg = alpha > 127
    h, w = fg.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8))
    comps = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < MIN_AREA * h * w:
            continue
        x, y, bw, bh = (int(stats[i, k]) for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        comps.append({"id": len(comps) + 1, "label": i, "bbox": [x, y, x + bw, y + bh]})
    return labels, comps


def render_views(img: np.ndarray, labels: np.ndarray, comps: list[dict]) -> list[Image.Image]:
    h, w = labels.shape
    s = VIEW_W / w
    vh = max(1, round(h * s))
    view = cv2.resize(img, (VIEW_W, vh), interpolation=cv2.INTER_AREA)
    lab_small = cv2.resize(labels.astype(np.int32).astype(np.float32), (VIEW_W, vh), interpolation=cv2.INTER_NEAREST).astype(np.int32)
    for c in comps:
        m = (lab_small == c["label"]).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        color = PALETTE[(c["id"] - 1) % len(PALETTE)]
        cv2.drawContours(view, cnts, -1, color[::-1], 3)
    pil = Image.fromarray(cv2.cvtColor(view, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    font = _font(26)
    for c in comps:
        x0, y0 = int(c["bbox"][0] * s), int(c["bbox"][1] * s)
        color = PALETTE[(c["id"] - 1) % len(PALETTE)]
        tx, ty = min(max(0, x0), VIEW_W - 60), max(0, y0)
        d.rectangle([tx, ty, tx + 52, ty + 32], fill=color)
        d.text((tx + 5, ty + 1), f"#{c['id']}", fill=(255, 255, 255), font=font)
    return [pil.crop((0, t, VIEW_W, min(vh, t + CHUNK_H))) for t in range(0, vh, CHUNK_H)]


def b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def ask(client, views: list[Image.Image], n: int, system: str = SYSTEM) -> tuple[dict, dict]:
    content = [{"type": "text", "text": f"섹션을 위에서 아래로 {len(views)}장으로 나눴다. 조각은 #1~#{n}."}]
    for i, v in enumerate(views, 1):
        content.append({"type": "text", "text": f"[{i}/{len(views)}]"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64(v)}})
    for attempt in range(5):
        try:
            res = client.chat.completions.create(
                model=MODEL["model_id"], temperature=0, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}])
            break
        except Exception as e:  # noqa: BLE001
            if "503" not in str(e) or attempt == 4:
                raise
            wait = 10 * (attempt + 1)
            print(f"    503 과부하 — {wait}초 뒤 재시도 ({attempt + 1}/4)")
            time.sleep(wait)
    usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
    return json.loads(res.choices[0].message.content), usage


def checker(h: int, w: int, size: int = 16) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where((((yy // size) + (xx // size)) % 2)[..., None], 205, 245).astype(np.uint8).repeat(3, axis=2)


def main() -> None:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="vlm_pick", choices=list(VARIANTS))
    ap.add_argument("--sections", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    variant = args.variant
    system = VARIANTS[variant]["system"]
    OUT = RESULTS / variant

    rule = {r["section"]: r for r in json.loads(RULE_FEATURES.read_text(encoding="utf-8"))}
    if variant == "sam_pick":
        sam_report = json.loads((SAM_PARTS / "parts.json").read_text(encoding="utf-8"))
        names = args.sections or sorted(sam_report)
    else:
        names = args.sections or sorted(s for s, r in rule.items() if r["components"] > 0)
    fp = fingerprint(variant)
    cache_dir = CACHE / MODEL["model_id"] / f"{variant}_{fp}"
    for sub in ("views", "mask", "rgba", "vis"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    client = None
    if not args.dry_run:
        from openai import OpenAI

        load_env()
        client = OpenAI(api_key=os.environ[MODEL["env_key"]], base_url=MODEL["base_url"])

    answers_path = OUT / "answers.json"
    answers = json.loads(answers_path.read_text(encoding="utf-8")) if answers_path.exists() else {}
    tok_in = tok_out = calls = chunks_total = 0
    t0 = time.perf_counter()
    for name in names:
        img = read(SRC_IMG / f"{name}.png")
        alpha = read(SRC_MASK / f"{name}.png", cv2.IMREAD_GRAYSCALE)
        if variant == "sam_pick":
            labels, comps = sam_components(name)
        else:
            labels, comps = components(alpha)
            # 번호가 rule_comp와 같은지 확인
            assert [c["bbox"] for c in comps] == [c["bbox"] for c in rule[name]["comps"]], f"{name} 덩어리 불일치"
        if not comps:
            continue
        views = render_views(img, labels, comps)
        chunks_total += len(views)
        for i, v in enumerate(views):
            v.save(OUT / "views" / f"{name}_{i}.jpg", quality=85)
        if args.dry_run:
            print(f"  {name:<24} 덩어리 {len(comps):>2}  조각 {len(views)}")
            continue

        cp = cache_dir / f"{name}.json"
        if cp.exists():
            c = json.loads(cp.read_text(encoding="utf-8"))
            ans, usage, hit = c["answer"], c["usage"], " (캐시)"
        else:
            ans, usage = ask(client, views, len(comps), system)
            cp.write_text(json.dumps({"answer": ans, "usage": usage}, ensure_ascii=False, indent=1), encoding="utf-8")
            hit = ""
            calls += 1
            tok_in += usage["in"]
            tok_out += usage["out"]

        if isinstance(ans, list):  # 가끔 {"regions": [...]} 없이 배열만 돌려줌
            ans = {"regions": ans}
        by_id = {int(r["id"]): r for r in ans.get("regions", []) if str(r.get("id", "")).isdigit() or isinstance(r.get("id"), int)}
        keep_mask = np.zeros(alpha.shape, bool)
        picked = []
        for c in comps:
            r = by_id.get(c["id"])
            missing = r is None
            keep = True if missing else bool(r.get("keep", True))
            picked.append({"id": c["id"], "bbox": c["bbox"], "keep": keep, "missing": missing,
                           "kind": None if missing else r.get("kind"), "note": None if missing else r.get("note")})
            if keep:
                keep_mask |= labels == c["label"]
        out_alpha = np.where(keep_mask, alpha, 0).astype(np.uint8)
        cv2.imwrite(str(OUT / "mask" / f"{name}.png"), out_alpha)
        cv2.imwrite(str(OUT / "rgba" / f"{name}.png"), np.dstack([img, out_alpha]))
        answers[name] = {"usage": usage, "regions": picked}

        # 대지 — 번호 그린 섹션 | 선별 결과
        full = np.vstack([cv2.cvtColor(np.array(v), cv2.COLOR_RGB2BGR) for v in views])
        sel = (img * (out_alpha[..., None] / 255.0) + checker(*alpha.shape) * (1 - out_alpha[..., None] / 255.0)).astype(np.uint8)
        sel = cv2.resize(sel, (VIEW_W, full.shape[0]), interpolation=cv2.INTER_AREA)
        sheet = np.hstack([full, np.full((full.shape[0], 14, 3), 40, np.uint8), sel])
        pil = Image.fromarray(cv2.cvtColor(sheet, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(pil)
        font = _font(18)
        y = 6
        for p in picked:
            txt = f"#{p['id']} {'남김' if p['keep'] else '버림'} {p['kind'] or '응답 없음'} {p['note'] or ''}"
            d.rectangle([VIEW_W + 18, y, VIEW_W + 18 + 12 * len(txt) + 10, y + 24], fill=(255, 255, 255))
            d.text((VIEW_W + 22, y + 2), txt, fill=(0, 120, 0) if p["keep"] else (200, 0, 0), font=font)
            y += 28
        pil.save(OUT / "vis" / f"{name}.jpg", quality=85)
        print(f"  {name:<24} 덩어리 {len(comps):>2}  조각 {len(views)}  in {usage['in']} out {usage['out']}{hit}  "
              + "  ".join(f"#{p['id']}:{'O' if p['keep'] else 'x'}{p['kind'] or '?'}" for p in picked), flush=True)

    if args.dry_run:
        print(f"[dry-run] 섹션 {len(names)} · 조각 {chunks_total}")
        return
    answers_path.write_text(json.dumps(answers, ensure_ascii=False, indent=1), encoding="utf-8")
    cost = tok_in / 1e6 * MODEL["price_in"] + tok_out / 1e6 * MODEL["price_out"]
    all_in = sum(a["usage"]["in"] for a in answers.values())
    all_out = sum(a["usage"]["out"] for a in answers.values())
    meta = {"variant": variant, "model": MODEL["model_id"], "prompt_fingerprint": fp, "view_w": VIEW_W,
            "chunk_h": CHUNK_H, "min_area": MIN_AREA, "sections_answered": len(answers),
            "this_run": {"calls": calls, "tokens_in": tok_in, "tokens_out": tok_out, "cost_usd": round(cost, 4),
                         "sec": round(time.perf_counter() - t0, 1)},
            "all_answers": {"tokens_in": all_in, "tokens_out": all_out,
                            "cost_usd": round(all_in / 1e6 * MODEL["price_in"] + all_out / 1e6 * MODEL["price_out"], 4)},
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{variant}] 이번 실행 호출 {calls} · in {tok_in} · out {tok_out} · ${cost:.4f}")


if __name__ == "__main__":
    main()
