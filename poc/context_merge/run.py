"""섹션 분해 — 처리 단위 OCR → 맥락 병합 (ctx_text · ctx_hint).

현행 `color_snap_vlm2`는 경계 대부분을 배경색 전환(픽셀 신호)으로 정한다.
여기서는 여백 처리 단위(`ws_std`)로 먼저 OCR하고, **LLM이 단위 텍스트를 읽고
새 섹션이 시작되는 단위 번호만 고른다.** 경계는 단위 사이에서만 고를 수 있어
글자 관통·스냅 실패가 구조상 없다.

OCR은 추가가 아니라 순서 이동이다. 단위 OCR 결과를 섹션 좌표로 옮기면 하류가
그대로 쓴다. 따라서 비교할 시간은 현행 VLM 80.6s 대 맥락 병합 호출 시간이다.

단계
    ocr     단위 OCR(확정 조건) + 단위 블록(`heuristic_v2`) → results/units/{stem}.json
    merge   맥락 병합 LLM 호출 → results/{variant}/sections/{stem}.json · timing.json

variant
    ctx_text   단위 블록 텍스트 · 글자 높이만
    ctx_hint   ctx_text + 단위 사이 배경색 전환 표시(color_snap ①②)
    ctx_text2  ctx_text + 단위 사전 병합(MERGE_GAP) + 입도 규칙(v2)
    ctx_hint2  ctx_hint + 단위 사전 병합(MERGE_GAP) + 입도 규칙(v2)

v1 단건 결과 (최장 페이지) — y8462 두 줄 제목이 단위 경계에 걸려 갈림, 최대 6,846px 과소분할.
v2는 두 줄 제목·라벨을 단위 사전 병합으로 막고, 입도 규칙으로 과소분할을 줄인다.

입력
    poc/section_split/results/ws_std/sections/{stem}.json        처리 단위
    poc/section_split/results/color_snap_ws/plan/{stem}.json     배경색 전환 절단
    poc/section_split/results/color_snap_vlm2/sections/{stem}.json  비교 기준 (vis)
    data/golden_sample/**/{stem}.jpg

출력
    results/units/{stem}.json                 단위별 region·block (단위 로컬 좌표)
    results/units/meta.json                   OCR 소요
    results/{variant}/prompts/{stem}.txt      LLM에 보낸 텍스트
    results/{variant}/sections/{stem}.json    섹션 · top_offset · 구성 단위 · 이름 · region(섹션 로컬)
    results/{variant}/vis/{stem}.jpg          왼쪽 현행(color_snap_vlm2) · 오른쪽 이 variant
    results/{variant}/timing.json             호출별 소요·토큰 (실행마다 누적)
    cache/{model}/{variant}_{지문}/{stem}.json

사용법
    python run.py ocr
    python run.py merge --variant all --images A000000219554_002.jpg --no-cache --repeat 3
    python run.py merge --variant ctx_text --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
SPLIT = ROOT / "poc" / "section_split" / "results"
UNITS = SPLIT / "ws_std" / "sections"
PLAN = SPLIT / "color_snap_ws" / "plan"
BASE = SPLIT / "color_snap_vlm2" / "sections"
RESULTS = HERE / "results"
CACHE = HERE / "cache"

# v2 — 단위 사전 병합(두 줄 제목·라벨 보호) + 과소분할 억제 프롬프트
VARIANTS = {
    "ctx_text": dict(hint=False, prompt="v1", premerge=False),
    "ctx_hint": dict(hint=True, prompt="v1", premerge=False),
    "ctx_text2": dict(hint=False, prompt="v2", premerge=True),
    "ctx_hint2": dict(hint=True, prompt="v2", premerge=True),
}

MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

# 텍스트 추출 확정 조건 — poc/B_ocr/run.py `baseline` (poc/ocr_split/run.py와 같음)
OCR_KWARGS = dict(
    lang="korean",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)
MIN_SCORE = 0.5       # 원문 지우기 확정 조건(erase_s50)과 같은 하한 — 이하는 프롬프트에서 뺌
HINT_TOL = 100        # 배경색 절단이 단위 경계에서 이 안이면 그 경계의 전환으로 봄 (px)
BLOCK_CHARS = 60      # 프롬프트에 넣는 블록 텍스트 최대 글자
UNIT_BLOCKS = 15      # 단위당 프롬프트에 넣는 블록 최대 수
# 사전 병합 — 앞 단위 마지막 블록과 뒤 단위 첫 블록 사이 간격이 큰 쪽 글자 높이의
# 이 배수 이하이면 두 단위를 하나로 본다. 골든 251경계 중 이 구간은 대부분
# "리드 문구·라벨 → 큰 제목" (y8462 두 줄 제목 0.25 · RECOMMEND 0.47)
MERGE_GAP = 0.5

# 줄·문단 병합 1단계 확정 조건 — poc/block_role/run.py `heuristic_v2`
HCFG = dict(line_gap=0.7, para_gap=0.6, h_ratio=1.5, overlap=0.5, gutter=True)

SYSTEM_BASE = """너는 한국 이커머스 상품 상세페이지를 문맥 단위 섹션으로 나눈다.

상세페이지 한 장을 위에서 아래로 여백마다 자른 **처리 단위** 목록을 준다.
단위마다 번호(#), 세로 위치, 높이, 그 안의 OCR 텍스트 블록이 있다.
블록 앞 `[숫자px]`는 글자 높이다 — 크면 제목·소제목일 가능성이 높다. OCR이라 오타가 있을 수 있다.

**새 섹션이 시작되는 단위의 번호**를 고른다.

나누는 신호
- 새 **소제목**이 등장한다. 예) "더 특별한 이유", "POINT 02", "Test", "이런 분들께 추천"
- 다루는 대상이 바뀐다. 예) 성분 A 설명 → 성분 B 설명, 설문 결과 → 시험 결과
- 역할이 바뀐다. 예) 제품 소개 → 효과 근거 → 사용법 → 추천 대상 → 성분표

**큰 주제가 같아도 소제목으로 논점이 새로 시작되면 나눈다.** 성분 설명이 이어지더라도
성분마다 소제목이 따로 있으면 각각 한 섹션이다.

나누지 않는 자리
- 소제목과 그 바로 아래 설명·그래프·사진 사이
- 소제목 위의 작은 라벨(예: "RECOMMEND", "POINT 01", "CHECK")과 그 소제목 사이 — 라벨은 아래 소제목과 같은 섹션
- 한 소제목 아래 나열된 항목 1·2·3 사이
- 시험 결과와 그 바로 아래 출처·각주 사이

글자 없는 단위(사진·그래픽만)는 앞뒤 중 어울리는 쪽에 붙인다. 대개 바로 위 소제목에 딸린 사진이다.
"""

HINT_NOTE = """
`── 배경색 전환 ──` 줄은 앞뒤 단위의 배경색이 크게 바뀐 자리다. 섹션이 바뀌는 경우가 많지만
같은 논점 안에서 배경만 바뀌기도 한다. **참고만 하고 판단은 텍스트 문맥으로 한다.**
"""

SYSTEM_TAIL = """
문맥 전환이 없으면 cuts를 빈 배열로 답한다.

출력은 JSON 하나. 설명을 붙이지 않는다.
{"cuts": [4, 9], "sections": ["제품 소개", "레티날 성분", "사용법"]}

`cuts`는 새 섹션이 시작되는 단위 번호(#1 제외), `sections`는 나뉜 구간의 이름을 위에서부터 적는다(개수 = cuts + 1)."""

# v2 — v1 단건에서 최대 6,846px 섹션(POINT 02 · 저자극 테스트 · 쿨링 · 발림성)이 나와 입도를 좁힘
GRAIN_V2 = """
입도
- 섹션 하나는 보통 단위 2~6개, 높이 1,000~3,000px이다.
- 3,000px 넘는 섹션을 만들려면 그 안에 새 소제목이 정말 없는지 다시 확인한다.
- 단위 첫머리의 큰 글자 블록(머리말의 `큰 글자` 기준 이상)은 새 소제목일 가능성이 높다.
- 시험·테스트 결과(인체적용시험 · 저자극 테스트 · 만족도 조사)는 앞 설명과 떨어진 별도 논점이다.
- 한 단위에 여러 번호가 병합돼 있어도(`#5 [단위 7~8 병합]`) 하나의 단위로 다룬다.
"""


def system_of(variant: str) -> str:
    cfg = VARIANTS[variant]
    return (SYSTEM_BASE + (GRAIN_V2 if cfg["prompt"] == "v2" else "")
            + (HINT_NOTE if cfg["hint"] else "") + SYSTEM_TAIL)


def fingerprint(variant: str) -> str:
    cfg = VARIANTS[variant]
    raw = {"system": system_of(variant), "model": MODEL["model_id"],
           "min_score": MIN_SCORE, "hint_tol": HINT_TOL,
           "block_chars": BLOCK_CHARS, "unit_blocks": UNIT_BLOCKS}
    if cfg["premerge"]:
        raw["merge_gap"] = MERGE_GAP
    raw = json.dumps(raw, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def stems_of(images: list[str] | None) -> list[Path]:
    paths = sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name))
    return [p for p in paths if not images or p.name in images]


# ---------------------------------------------------------------- heuristic_v2 (poc/block_role/run.py 복사)

def h_of(r: dict) -> int:
    return r["bbox"][3] - r["bbox"][1]


def v_overlap(a, b) -> float:
    top, bot = max(a[1], b[1]), min(a[3], b[3])
    return max(0, bot - top) / max(1, min(a[3] - a[1], b[3] - b[1]))


def h_overlap(a, b) -> float:
    left, right = max(a[0], b[0]), min(a[2], b[2])
    return max(0, right - left) / max(1, min(a[2] - a[0], b[2] - b[0]))


def union_box(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def gutters(regions, width):
    cover = bytearray(width)
    for r in regions:
        for x in range(max(0, r["bbox"][0]), min(width, r["bbox"][2])):
            cover[x] = 1
    out, run = [], None
    for x in range(width):
        if not cover[x]:
            run = x if run is None else run
        elif run is not None:
            out.append((run, x))
            run = None
    if run is not None:
        out.append((run, width))
    min_w = max(20, width // 16)
    return [(a, b) for a, b in out if b - a >= min_w and a > 0 and b < width]


def merge_lines(regions, cfg, gut):
    order = sorted(range(len(regions)), key=lambda i: regions[i]["bbox"][0])
    lines = []
    for i in order:
        ri = regions[i]
        for line in lines:
            rj = regions[line[-1]]
            a, b = rj["bbox"], ri["bbox"]
            gap = b[0] - a[2]
            base = min(h_of(ri), h_of(rj))
            if v_overlap(a, b) < 0.5:
                continue
            if not (-base * 0.5 <= gap <= base * cfg["line_gap"]):
                continue
            if max(h_of(ri), h_of(rj)) / max(1, base) > cfg["h_ratio"]:
                continue
            if cfg["gutter"] and any(a[2] <= g0 and g1 <= b[0] for g0, g1 in gut):
                continue
            line.append(i)
            break
        else:
            lines.append([i])
    lines.sort(key=lambda ln: (regions[ln[0]]["bbox"][1], regions[ln[0]]["bbox"][0]))
    return lines


def merge_paragraphs(regions, lines, cfg):
    boxes = [union_box([regions[i]["bbox"] for i in ln]) for ln in lines]
    heights = [max(h_of(regions[i]) for i in ln) for ln in lines]
    groups = []
    for k in range(len(lines)):
        for g in groups:
            j = g[-1]
            a, b = boxes[j], boxes[k]
            gap = b[1] - a[3]
            base = min(heights[j], heights[k])
            if not (-base * 0.3 <= gap <= base * cfg["para_gap"]):
                continue
            if max(heights[j], heights[k]) / max(1, base) > cfg["h_ratio"]:
                continue
            if h_overlap(a, b) < cfg["overlap"] and abs(a[0] - b[0]) > base * 0.5:
                continue
            g.append(k)
            break
        else:
            groups.append([k])
    return groups


def build_blocks(regions, width):
    gut = gutters(regions, width) if HCFG["gutter"] else []
    lines = merge_lines(regions, HCFG, gut)
    groups = merge_paragraphs(regions, lines, HCFG)
    blocks = []
    for g in groups:
        member = [lines[k] for k in g]
        ids = [i for ln in member for i in ln]
        hs = sorted(h_of(regions[i]) for i in ids)
        blocks.append({
            "bbox": union_box([regions[i]["bbox"] for i in ids]),
            "text": "\n".join(" ".join(regions[i]["text"] for i in ln) for ln in member),
            "font_h": hs[len(hs) // 2],
            "regions": sorted(ids),
        })
    blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return blocks


# ---------------------------------------------------------------- ocr

def cmd_ocr(args) -> None:
    from paddleocr import PaddleOCR

    model = PaddleOCR(**OCR_KWARGS)
    out = RESULTS / "units"
    out.mkdir(parents=True, exist_ok=True)
    per, t_all = [], time.perf_counter()
    for path in stems_of(args.images):
        sec = json.loads((UNITS / f"{path.stem}.json").read_text(encoding="utf-8"))
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        w = img.shape[1]
        t0 = time.perf_counter()
        units = []
        for s in sec["sections"]:
            top, bottom = s["range"]
            res = list(model.predict(img[top:bottom]))[0]
            regions = []
            for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
                xs = [float(p[0]) for p in poly]
                ys = [float(p[1]) for p in poly]
                regions.append({"bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                                "text": text, "score": round(float(score), 4)})
            units.append({"index": s["index"], "range": [top, bottom], "height": bottom - top,
                          "regions": regions})
        t_ocr = time.perf_counter() - t0
        t1 = time.perf_counter()
        for u in units:
            keep = [r for r in u["regions"] if r["text"].strip() and r["score"] >= MIN_SCORE]
            u["blocks"] = build_blocks(keep, w) if keep else []
        t_blk = time.perf_counter() - t1
        (out / f"{path.stem}.json").write_text(json.dumps(
            {"image": path.name, "size": [w, img.shape[0]], "units": units,
             "ocr_sec": round(t_ocr, 2), "block_sec": round(t_blk, 3)},
            ensure_ascii=False, indent=1), encoding="utf-8")
        n_reg = sum(len(u["regions"]) for u in units)
        per.append({"image": path.name, "units": len(units), "regions": n_reg,
                    "ocr_sec": round(t_ocr, 2), "block_sec": round(t_blk, 3)})
        print(f"  {path.name:<26} 단위 {len(units):>3}  region {n_reg:>4}  OCR {t_ocr:.2f}s  블록 {t_blk:.3f}s")
    meta = {"images": len(per), "units": sum(p["units"] for p in per),
            "regions": sum(p["regions"] for p in per),
            "ocr_sec": round(sum(p["ocr_sec"] for p in per), 2),
            "block_sec": round(sum(p["block_sec"] for p in per), 3),
            "wall_sec": round(time.perf_counter() - t_all, 2),
            "per_image": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not args.images:
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[units] 단위 {meta['units']} · region {meta['regions']} · OCR {meta['ocr_sec']}s · "
          f"블록 {meta['block_sec']}s")


# ---------------------------------------------------------------- merge

def shift(items: list[dict], dy: int) -> list[dict]:
    return [{**r, "bbox": [r["bbox"][0], r["bbox"][1] + dy, r["bbox"][2], r["bbox"][3] + dy]}
            for r in items]


def logical_units(units: list[dict], premerge: bool) -> tuple[list[dict], int]:
    """사전 병합한 단위 목록과 병합 경계 수. 좌표는 병합 단위 로컬."""
    groups = [[units[0]]]
    merged = 0
    for u in units[1:]:
        prev = groups[-1][-1]
        join = False
        if premerge and prev["blocks"] and u["blocks"]:
            last = max(prev["blocks"], key=lambda b: b["bbox"][3])
            first = min(u["blocks"], key=lambda b: b["bbox"][1])
            gap = (prev["height"] - last["bbox"][3]) + first["bbox"][1]
            join = gap <= MERGE_GAP * max(last["font_h"], first["font_h"])
        if join:
            groups[-1].append(u)
            merged += 1
        else:
            groups.append([u])
    out = []
    for g in groups:
        y0 = g[0]["range"][0]
        regions, blocks = [], []
        for u in g:
            dy = u["range"][0] - y0
            regions += shift(u["regions"], dy)
            blocks += shift(u["blocks"], dy)
        out.append({"members": [u["index"] for u in g], "range": [y0, g[-1]["range"][1]],
                    "height": g[-1]["range"][1] - y0, "regions": regions, "blocks": blocks})
    return out, merged


def hint_boundaries(stem: str, units: list[dict]) -> set[int]:
    """배경색 절단과 맞닿은 단위 경계 — 값은 그 경계 아래 단위 번호(1부터)."""
    plan = json.loads((PLAN / f"{stem}.json").read_text(encoding="utf-8"))
    out = set()
    for y in plan["color_cuts"]:
        best = min(range(1, len(units)), key=lambda k: abs(units[k]["range"][0] - y), default=None)
        if best is not None and abs(units[best]["range"][0] - y) <= HINT_TOL:
            out.add(best + 1)
    return out


def build_prompt(data: dict, units: list[dict], hints: set[int] | None, grain: bool) -> str:
    w, h = data["size"]
    L = [f"상세페이지 {w}x{h}px · 처리 단위 {len(units)}개 (#1~#{len(units)})"]
    if grain:
        fh = sorted(b["font_h"] for u in units for b in u["blocks"])
        if fh:
            L.append(f"글자 높이 중앙값 {fh[len(fh) // 2]}px · 큰 글자 기준(상위 25%) {fh[int(len(fh) * 0.75)]}px")
    L.append("")
    for k, u in enumerate(units, 1):
        if hints is not None and k in hints:
            L.append("── 배경색 전환 ──")
        a, b = u["range"]
        tag = (f" [단위 {u['members'][0]}~{u['members'][-1]} 병합]"
               if grain and len(u["members"]) > 1 else "")
        L.append(f"#{k}  y{a}~{b} (높이 {b - a}){tag}")
        if not u["blocks"]:
            L.append("  [글자 없음]")
        for blk in u["blocks"][:UNIT_BLOCKS]:
            t = " / ".join(blk["text"].split("\n"))
            if len(t) > BLOCK_CHARS:
                t = t[:BLOCK_CHARS] + "…"
            L.append(f"  [{blk['font_h']}px] {t}")
        if len(u["blocks"]) > UNIT_BLOCKS:
            L.append(f"  … 외 {len(u['blocks']) - UNIT_BLOCKS}블록")
    return "\n".join(L)


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def ask(client, system: str, prompt: str) -> tuple[dict | None, dict, float, int]:
    """(응답 JSON 또는 None, 토큰, 소요초, 재시도 수). 소요는 재시도 대기 포함."""
    t0 = time.perf_counter()
    for attempt in range(5):
        try:
            res = client.chat.completions.create(
                model=MODEL["model_id"], temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
            )
            break
        except Exception as e:  # noqa: BLE001
            if "503" not in str(e) or attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
    sec = time.perf_counter() - t0
    usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
    try:
        ans = json.loads(res.choices[0].message.content)
    except (TypeError, json.JSONDecodeError):
        ans = None
    return ans, usage, sec, attempt


def assemble(variant: str, path: Path, data: dict, units: list[dict], ans: dict | None,
             hints: set[int]) -> dict:
    w, h = data["size"]
    fallback = False
    starts: set[int] = set()
    if isinstance(ans, dict) and isinstance(ans.get("cuts"), list):
        for k in ans["cuts"]:
            try:
                k = int(k)
            except (TypeError, ValueError):
                continue
            if 2 <= k <= len(units):
                starts.add(k)
    else:
        # 응답 파싱 실패 — 배경색 전환 경계로 대체
        fallback = True
        starts = set(hints)
    bounds = [1] + sorted(starts) + [len(units) + 1]
    names = ans.get("sections", []) if isinstance(ans, dict) else []
    sections = []
    for i, (k0, k1) in enumerate(zip(bounds, bounds[1:])):
        members = units[k0 - 1:k1 - 1]
        y0, y1 = members[0]["range"][0], members[-1]["range"][1]
        regions = []
        for u in members:
            dy = u["range"][0] - y0
            for r in u["regions"]:
                x0, a, x1, b = r["bbox"]
                regions.append({**r, "bbox": [x0, a + dy, x1, b + dy]})
        sections.append({"index": i + 1, "top_offset": y0, "range": [y0, y1], "height": y1 - y0,
                         "units": [k0, k1 - 1],
                         "ws_units": [members[0]["members"][0], members[-1]["members"][-1]],
                         "name": names[i] if i < len(names) else None,
                         "cut_hint": k0 in hints, "regions": regions})
    doc = {"image": path.name, "variant": variant, "size": [w, h],
           "cuts": [s["top_offset"] for s in sections[1:]], "fallback": fallback,
           "hint_units": sorted(hints), "names_match": len(names) == len(sections),
           "sections": sections}
    out = RESULTS / variant / "sections"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{path.stem}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


BLUE, RED, ORANGE, GRAY = (40, 110, 230), (220, 30, 30), (230, 130, 0), (150, 150, 150)


def visualize(variant: str, path: Path, doc: dict, units: list[dict]) -> None:
    """왼쪽 현행 · 오른쪽 이 variant. 위에 범례. 오른쪽 가장자리 회색 눈금 = 고를 수 있던 단위 경계."""
    base = json.loads((BASE / f"{path.stem}.json").read_text(encoding="utf-8"))
    img = Image.open(path).convert("RGB")
    w, h = img.size
    sw = 240
    scale = sw / w
    thumb = np.array(img.resize((sw, max(1, int(h * scale))), Image.BILINEAR))
    left, right = thumb.copy(), thumb.copy()
    for y in base["cuts"]:
        yy = int(y * scale)
        left[max(0, yy - 1):yy + 2, :] = BLUE
    for u in units[1:]:
        yy = int(u["range"][0] * scale)
        right[yy:yy + 1, sw - 16:] = GRAY
    for s in doc["sections"][1:]:
        yy = int(s["top_offset"] * scale)
        right[max(0, yy - 1):yy + 2, :] = ORANGE if s["cut_hint"] else RED
    gap = np.full((thumb.shape[0], 12, 3), 255, np.uint8)
    body = Image.fromarray(np.hstack([left, gap, right]))

    head_h = 74
    canvas = Image.new("RGB", (body.width, body.height + head_h), (255, 255, 255))
    canvas.paste(body, (0, head_h))
    d = ImageDraw.Draw(canvas)
    f, fs = _font(14), _font(11)
    x2 = sw + 12
    d.text((4, 4), "현행 color_snap_vlm2", fill=(0, 0, 0), font=f)
    d.text((4, 24), f"섹션 {len(base['sections'])}", fill=(0, 0, 0), font=fs)
    d.rectangle([4, 44, 24, 48], fill=BLUE)
    d.text((28, 39), "절단", fill=(0, 0, 0), font=fs)
    d.text((x2 + 4, 4), variant, fill=(0, 0, 0), font=f)
    d.text((x2 + 4, 24), f"섹션 {len(doc['sections'])} · 단위 {len(units)}", fill=(0, 0, 0), font=fs)
    d.rectangle([x2 + 4, 44, x2 + 24, 48], fill=RED)
    d.text((x2 + 28, 39), "맥락 절단", fill=(0, 0, 0), font=fs)
    d.rectangle([x2 + 90, 44, x2 + 110, 48], fill=ORANGE)
    d.text((x2 + 114, 39), "색 전환과 일치", fill=(0, 0, 0), font=fs)
    d.rectangle([x2 + 4, 62, x2 + 24, 63], fill=GRAY)
    d.text((x2 + 28, 56), "단위 경계(후보)", fill=(0, 0, 0), font=fs)
    out = RESULTS / variant / "vis"
    out.mkdir(parents=True, exist_ok=True)
    canvas.save(out / f"{path.stem}.jpg", quality=88)


def cmd_merge(args) -> None:
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    paths = stems_of(args.images)
    datas = {p.stem: json.loads((RESULTS / "units" / f"{p.stem}.json").read_text(encoding="utf-8"))
             for p in paths}
    client = None
    if not args.dry_run:
        load_env()
        from openai import OpenAI
        client = OpenAI(api_key=os.environ[MODEL["env_key"]], base_url=MODEL["base_url"])

    for variant in names:
        cfg = VARIANTS[variant]
        fp = fingerprint(variant)
        system = system_of(variant)
        cache_dir = CACHE / MODEL["model_id"] / f"{variant}_{fp}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        pdir = RESULTS / variant / "prompts"
        pdir.mkdir(parents=True, exist_ok=True)
        lunits, hints, prompts, premerged = {}, {}, {}, 0
        for p in paths:
            lunits[p.stem], m = logical_units(datas[p.stem]["units"], cfg["premerge"])
            premerged += m
            hints[p.stem] = hint_boundaries(p.stem, lunits[p.stem])
            prompts[p.stem] = build_prompt(datas[p.stem], lunits[p.stem],
                                           hints[p.stem] if cfg["hint"] else None,
                                           cfg["prompt"] == "v2")
            (pdir / f"{p.stem}.txt").write_text(prompts[p.stem], encoding="utf-8")
        n_units = sum(len(v) for v in lunits.values())

        if args.dry_run:
            chars = sum(len(t) for t in prompts.values()) + len(system) * len(paths)
            print(f"[{variant}] 지문 {fp} · 단위 {n_units} (사전 병합 {premerged}) · 호출 {len(paths)} · "
                  f"프롬프트 {chars:,}자 (추정 in ≈ {chars // 2:,} 토큰)")
            continue

        print(f"[{variant}] 지문 {fp} · {'캐시 미사용' if args.no_cache else '캐시 우선'} · "
              f"동시 {args.concurrency} · 반복 {args.repeat}")
        runs = []
        for rep in range(1, args.repeat + 1):
            def one(p: Path):
                cp = cache_dir / f"{p.stem}.json"
                if cp.exists() and not args.no_cache:
                    c = json.loads(cp.read_text(encoding="utf-8"))
                    return p, c["answer"], c["usage"], None, 0
                ans, usage, sec, retry = ask(client, system, prompts[p.stem])
                cp.write_text(json.dumps({"answer": ans, "usage": usage, "sec": round(sec, 2)},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
                return p, ans, usage, sec, retry

            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                results = list(ex.map(one, paths))
            wall = time.perf_counter() - t0

            calls, tin, tout = [], 0, 0
            for p, ans, usage, sec, retry in results:
                doc = assemble(variant, p, datas[p.stem], lunits[p.stem], ans, hints[p.stem])
                visualize(variant, p, doc, lunits[p.stem])
                tin += usage["in"]
                tout += usage["out"]
                calls.append({"image": p.name, "sec": None if sec is None else round(sec, 2),
                              "in": usage["in"], "out": usage["out"], "retry": retry,
                              "units": len(lunits[p.stem]), "sections": len(doc["sections"]),
                              "fallback": doc["fallback"]})
                tag = "캐시" if sec is None else f"{sec:.2f}s"
                print(f"  #{rep} {p.name:<26} 단위 {len(lunits[p.stem]):>3} → 섹션 "
                      f"{len(doc['sections']):>3}  in {usage['in']} out {usage['out']}  {tag}"
                      f"{'  폴백' if doc['fallback'] else ''}{'  재시도 ' + str(retry) if retry else ''}")
            cost = tin / 1e6 * MODEL["price_in"] + tout / 1e6 * MODEL["price_out"]
            live = [c["sec"] for c in calls if c["sec"] is not None]
            runs.append({"rep": rep, "wall_sec": round(wall, 2), "sum_call_sec": round(sum(live), 2),
                         "calls": calls, "tokens": {"in": tin, "out": tout},
                         "cost_usd": round(cost, 5) if live else 0})
            print(f"  #{rep} 벽시계 {wall:.2f}s · 호출 합 {sum(live):.2f}s · in {tin} out {tout} · "
                  f"${cost if live else 0:.5f}")

        walls = [r["wall_sec"] for r in runs]
        tpath = RESULTS / variant / "timing.json"
        log = json.loads(tpath.read_text(encoding="utf-8")) if tpath.exists() else []
        log.append({"run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "fingerprint": fp,
                    "images": [p.name for p in paths], "no_cache": args.no_cache,
                    "concurrency": args.concurrency, "repeat": args.repeat,
                    "wall_median_sec": round(statistics.median(walls), 2),
                    "cost_usd": round(sum(r["cost_usd"] for r in runs), 5), "runs": runs})
        tpath.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{variant}] 벽시계 중앙값 {statistics.median(walls):.2f}s · "
              f"비용 합 ${sum(r['cost_usd'] for r in runs):.5f}\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("ocr")
    o.add_argument("--images", nargs="*", default=None)
    m = sub.add_parser("merge")
    m.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    m.add_argument("--images", nargs="*", default=None)
    m.add_argument("--no-cache", action="store_true")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--concurrency", type=int, default=1)
    m.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    if args.cmd == "merge" and args.variant not in (*VARIANTS, "all"):
        raise SystemExit(f"모르는 variant: {args.variant}")
    {"ocr": cmd_ocr, "merge": cmd_merge}[args.cmd](args)


if __name__ == "__main__":
    main()
