"""섹션 분해 — 배경색 전환 + VLM 보조 분해 (color_snap_vlm).

`run_color.py`의 ①② 결과(배경색 전환 절단)는 그대로 쓰고, **색이 안 바뀌는 긴
구간(③)만** VLM에게 맡긴다. 후보 1(여백+병합)은 길이로 병합해 문맥과 어긋났다.

VLM에게 좌표를 묻지 않는다
    VLM은 픽셀 좌표 추정이 부정확하고, 추정한 자리가 글자를 지날 수도 있다.
    대신 **자를 수 있는 여백마다 번호 붙은 빨간 선을 그려** 보여주고, 문맥이 바뀌는
    **번호만 고르게** 한다. 여백이 아닌 곳은 애초에 고를 수 없으므로 스냅 실패가 없다.

입력
    results/color_snap_ws/plan/{stem}.json   ①② 절단점과 보조 분해 대상 구간
    data/golden_sample/**/{stem}.jpg

출력 (review.py가 그대로 읽는 형식)
    results/color_snap_vlm/sections/{stem}.json
    results/color_snap_vlm/crops/{stem}/{i}.jpg
    results/color_snap_vlm/prompts/{stem}_{구간}_{조각}.jpg   VLM에 보낸 이미지
    results/color_snap_vlm/meta.json                        토큰·비용 실측
    cache/{model}/color_snap_vlm/{stem}_{구간}.json          API 응답 원본

사용법
    python run_color_vlm.py --dry-run
    python run_color_vlm.py
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
PLAN = HERE / "results" / "color_snap_ws" / "plan"
OUT = HERE / "results" / "color_snap_vlm"
CACHE = HERE / "cache"
VARIANT = "color_snap_vlm"

MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

BLANK_TOL = 6.0     # run_color.py와 같은 여백 판정
BLANK_GAP = 40
MIN_SECTION = 400   # 최종 섹션 최소 길이
CAND_MERGE = 150    # 이보다 가까운 후보선은 하나로 합친다 — 그림이 복잡해지지 않게
VIEW_W = 768        # VLM에 보낼 폭
CHUNK_H = 2000      # VLM에 보낼 조각 높이 (축소 후)

SYSTEM = """너는 한국 이커머스 상품 상세페이지를 문맥 단위 섹션으로 나눈다.

상세페이지의 한 구간을 위에서 아래로 잘라 순서대로 준다. 이미지들은 이어져 있다.
**빨간 가로선과 `#번호`는 자를 수 있는 여백 후보**다.

문맥이 바뀌는 자리의 번호만 고른다. 상세페이지의 문맥은 보통 이런 흐름이다.
  제품 소개 · 사용자 고민 · 제품 제시 · 핵심 효과 · 성분·기술 근거 · 시험·인증 결과
  · 사용법 · 추천 대상 · 라인업 · 브랜드 가치 · 성분표·고지

지킬 것
- 같은 문맥 안의 여백은 고르지 않는다. 제목과 그 설명 사이, 항목 1·2·3 사이는 같은 문맥이다.
- 한 섹션은 보통 화면 여러 장 분량이다. 잘게 나누지 않는다.
- 문맥 전환이 없으면 빈 배열로 답한다.

출력은 JSON 하나. 설명을 붙이지 않는다.
{"cuts": [3, 7], "sections": ["제품 소개", "시험 결과", "사용법"]}

`sections`는 고른 번호로 나뉜 구간의 문맥 이름을 위에서부터 적는다(개수 = cuts + 1)."""


def blank_centers(gray: np.ndarray) -> list[int]:
    std = gray.std(axis=1)
    b = std <= BLANK_TOL
    out, s = [], None
    for y, x in enumerate(b):
        if x and s is None:
            s = y
        elif not x and s is not None:
            if y - s >= BLANK_GAP:
                out.append((s + y) // 2)
            s = None
    return out


def candidates(centers: list[int], a: int, b: int) -> list[int]:
    """구간 안의 여백 후보. 가장자리와 너무 가까운 것은 빼고, 붙어 있는 것은 합친다."""
    c = [y for y in centers if a + MIN_SECTION <= y <= b - MIN_SECTION]
    merged: list[int] = []
    for y in c:
        if merged and y - merged[-1] < CAND_MERGE:
            continue
        merged.append(y)
    return merged


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_chunks(img: Image.Image, a: int, b: int, cands: list[int]) -> list[Image.Image]:
    """구간을 폭 VIEW_W로 줄이고 후보선을 그린 뒤 CHUNK_H씩 나눈다."""
    w = img.width
    scale = VIEW_W / w
    seg = img.crop((0, a, w, b)).resize((VIEW_W, max(1, round((b - a) * scale))), Image.BILINEAR)
    draw = ImageDraw.Draw(seg)
    font = _font(22)
    for i, y in enumerate(cands, 1):
        yy = round((y - a) * scale)
        draw.line([(0, yy), (VIEW_W, yy)], fill=(230, 20, 20), width=3)
        label = f"#{i}"
        tw = int(draw.textlength(label, font=font)) + 12
        draw.rectangle([4, yy - 15, 4 + tw, yy + 15], fill=(230, 20, 20))
        draw.text((10, yy - 13), label, fill=(255, 255, 255), font=font)

    chunks = []
    for top in range(0, seg.height, CHUNK_H):
        chunks.append(seg.crop((0, top, VIEW_W, min(seg.height, top + CHUNK_H))))
    return chunks


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


def ask(client, chunks: list[Image.Image], n_cands: int) -> tuple[dict, dict]:
    content = [{"type": "text",
                "text": f"구간을 위에서 아래로 {len(chunks)}장으로 나눴다. 후보는 #1~#{n_cands}."}]
    for i, ch in enumerate(chunks, 1):
        content.append({"type": "text", "text": f"[{i}/{len(chunks)}]"})
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b64(ch)}})
    # 503(일시 과부하)은 잠시 뒤 다시 시도한다. 그 외 오류는 그대로 올린다.
    for attempt in range(5):
        try:
            res = client.chat.completions.create(
                model=MODEL["model_id"], temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": content}],
            )
            break
        except Exception as e:  # noqa: BLE001
            if "503" not in str(e) or attempt == 4:
                raise
            wait = 10 * (attempt + 1)
            print(f"    503 과부하 — {wait}초 뒤 재시도 ({attempt + 1}/4)")
            time.sleep(wait)
    usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
    return json.loads(res.choices[0].message.content), usage


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    plans = sorted(PLAN.glob("*.json"))
    if args.images:
        plans = [p for p in plans if f"{p.stem}.jpg" in args.images]
    if not plans:
        raise SystemExit(f"{PLAN} 없음 — run_color.py 를 먼저 돌릴 것")

    client = None
    if not args.dry_run:
        load_env()
        from openai import OpenAI

        client = OpenAI(api_key=os.environ[MODEL["env_key"]], base_url=MODEL["base_url"])
    cache_dir = CACHE / MODEL["model_id"] / VARIANT
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{VARIANT}] {'dry-run' if args.dry_run else MODEL['model_id']}")
    tok_in = tok_out = calls = images = 0
    per = []
    t0 = time.perf_counter()

    for plan_path in plans:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        src = next(SRC.rglob(plan["image"]))
        img = Image.open(src).convert("RGB")
        w, h = img.size
        centers = blank_centers(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY))

        cuts: dict[int, str] = {y: "color" for y in plan["color_cuts"]}
        notes = []
        for ti, (a, b) in enumerate(plan["aux_targets"], 1):
            cands = candidates(centers, a, b)
            if not cands:
                notes.append({"range": [a, b], "candidates": 0, "picked": []})
                continue
            chunks = render_chunks(img, a, b, cands)
            images += len(chunks)
            (OUT / "prompts").mkdir(parents=True, exist_ok=True)
            for ci, ch in enumerate(chunks, 1):
                ch.save(OUT / "prompts" / f"{plan_path.stem}_{ti}_{ci}.jpg", quality=85)

            if args.dry_run:
                print(f"  {plan['image']:<26} 구간 y{a}~{b}  후보 {len(cands):>2}  조각 {len(chunks)}")
                continue

            cp = cache_dir / f"{plan_path.stem}_{ti}.json"
            if cp.exists() and not args.no_cache:
                c = json.loads(cp.read_text(encoding="utf-8"))
                ans, usage, hit = c["answer"], c["usage"], " (캐시)"
            else:
                ans, usage = ask(client, chunks, len(cands))
                cp.write_text(json.dumps({"answer": ans, "usage": usage, "candidates": cands},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
                hit = ""
                calls += 1
            tok_in += usage["in"]
            tok_out += usage["out"]

            picked = []
            for k in ans.get("cuts", []):
                try:
                    k = int(k)
                except (TypeError, ValueError):
                    continue
                if 1 <= k <= len(cands):
                    y = cands[k - 1]
                    if all(abs(y - c) >= MIN_SECTION for c in cuts):
                        cuts[y] = "aux_vlm"
                        picked.append(k)
            notes.append({"range": [a, b], "candidates": len(cands), "picked": picked,
                          "labels": ans.get("sections", [])})
            print(f"  {plan['image']:<26} 구간 y{a}~{b}  후보 {len(cands):>2}  선택 {picked}  "
                  f"in {usage['in']} out {usage['out']}{hit}")

        if args.dry_run:
            continue

        bounds = [0] + sorted(cuts) + [h]
        crop_dir = OUT / "crops" / plan_path.stem
        crop_dir.mkdir(parents=True, exist_ok=True)
        sections = []
        for i, (y0, y1) in enumerate(zip(bounds, bounds[1:]), 1):
            img.crop((0, y0, w, y1)).save(crop_dir / f"{i:03d}.jpg", quality=92)
            sections.append({"index": i, "top_offset": y0, "range": [y0, y1],
                             "height": y1 - y0, "cut_source": "시작" if y0 == 0 else cuts[y0],
                             "forced": False, "crop": f"crops/{plan_path.stem}/{i:03d}.jpg"})
        (OUT / "sections").mkdir(parents=True, exist_ok=True)
        (OUT / "sections" / f"{plan_path.stem}.json").write_text(
            json.dumps({"image": plan["image"], "variant": VARIANT, "size": [w, h],
                        "cuts": sorted(cuts), "cut_sources": {str(k): v for k, v in cuts.items()},
                        "snap_failed": plan["snap_failed"], "aux": notes, "forced_cuts": [],
                        "sections": sections}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        per.append({"image": plan["image"], "size": [w, h], "sections": len(sections),
                    "color_cuts": len(plan["color_cuts"]),
                    "vlm_cuts": sum(1 for s in cuts.values() if s == "aux_vlm"),
                    "max_height": max(s["height"] for s in sections)})

    if args.dry_run:
        print(f"  → 이미지 조각 {images}장. 호출 없음")
        return

    cost = tok_in / 1e6 * MODEL["price_in"] + tok_out / 1e6 * MODEL["price_out"]
    meta = {"variant": VARIANT, "cfg": {"model": MODEL["model_id"], "temperature": 0,
                                        "view_w": VIEW_W, "chunk_h": CHUNK_H,
                                        "cand_merge": CAND_MERGE, "min_section": MIN_SECTION},
            "images": len(per), "total_sections": sum(p["sections"] for p in per),
            "total_forced": 0,
            "color_cuts": sum(p["color_cuts"] for p in per),
            "vlm_cuts": sum(p["vlm_cuts"] for p in per),
            "max_section_height": max(p["max_height"] for p in per),
            "calls": calls, "image_chunks": images,
            "tokens": {"in": tok_in, "out": tok_out}, "cost_usd": round(cost, 4),
            "total_sec": round(time.perf_counter() - t0, 2),
            "per_image": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print(f"[{VARIANT}] 완료 — 섹션 {meta['total_sections']} (색 {meta['color_cuts']} · "
          f"VLM {meta['vlm_cuts']}) · in {tok_in} out {tok_out} · ${cost:.4f} · {meta['total_sec']}s")


if __name__ == "__main__":
    main()
