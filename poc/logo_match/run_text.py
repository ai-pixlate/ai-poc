"""브랜드 로고 제외 — 텍스트 대조 variant 실행기.

템플릿 매칭 대신 **OCR이 읽은 글자를 브랜드명과 대조**한다. 표본 로고가 전부
워드마크라 OCR 영역에 이미 들어 있다는 확인에서 출발했다. 전부 로컬, 비용 0.

단계
    ① OCR — 텍스트 추출 확정 조건(PaddleOCR `baseline`). 초장축은 검출기가 긴 변을
       줄여 글자가 사라지므로 **2,000px 띠로 겹쳐 잘라** 읽고 합친다. variant 공통, 캐시.
    ② 대조 — region(OCR 한 줄) 텍스트를 정규화해 그 상품의 브랜드명 사전과 비교.

⚠️ **브랜드명 사전은 가정이다.** 상품 메타가 없어 페이지에서 확인한 표기를 넣었다.
실서비스는 상품 메타에서 영·한 표기를 받는다고 본다.

variant
    text_exact     정규화 텍스트 == 브랜드명
    text_fuzzy     유사도(difflib) ≥ 0.8 — OCR 오독 허용
    text_contains  브랜드명이 텍스트에 포함 — **부분 일치의 과잉 제외를 보려는 대조군**
    line_exact     `heuristic_v2`로 **줄 병합 후** 줄 텍스트 == 브랜드명
    block_exact    `heuristic_v2`로 **줄·문단 병합 후** 블록 텍스트 == 브랜드명

    region 단위는 OCR이 제목을 끊어 읽으면 브랜드명만 한 줄로 떨어져 오탐이 난다
    (`셀리맥스` | `레티날 샷 부스터`). 병합 단위가 이를 없애는지, 대신 로고가 옆 글자와
    묶여 놓치는지 본다. 병합은 줄·문단 병합 확정안의 1단계(`heuristic_v2`)만 쓴다 —
    2단계 LLM 보정은 유료라 뺌.

정규화 — NFKC · 소문자 · 공백·문장부호 제거 (`b.clinicx` → `bclinicx`)

범위 — 템플릿 variant와 같음. 제품 패키지 위 로고는 라벨 판정 소관.

출력
    results/_ocr/{stem}.json              띠 OCR 결과 (variant 공통 캐시)
    results/{variant}/matches/{stem}.json 통과 region — 텍스트·좌표·유사도
    results/{variant}/vis/{stem}.jpg      통과가 있는 이미지만. 초록 박스
    results/{variant}/hits.jpg            통과 region을 주변과 함께 잘라 모은 대지
    results/{variant}/meta.json

--sample golden (골든 샘플 단계 4 재확인)
    단계 2 `llm_assist` 블록(poc/golden/2_block_role)에 `block_exact`를 적용하고 기존 정답 페이지 로고 7개와
    페이지 좌표로 기계 대조. 라벨 블록(poc/golden/3_product_label 정답) 위 통과는 라벨 소관이라 세지 않음.
    출력 results/golden/block_exact/meta.json · logos.jpg → poc/golden/move.py 4 로 이동

사용법
    python run_text.py --variant all
    python run_text.py --variant text_exact --images A000000219554_001.jpg
    python run_text.py --sample golden
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
RESULTS = HERE / "results"
OCR_CACHE = RESULTS / "_ocr"

# 상품 폴더 → 브랜드명 표기 (가정 — 페이지에서 확인한 표기)
BRANDS = {
    "images_A000000213548": ["b.clinicx", "비클리닉스"],
    "images_A000000219554": ["goodal", "구달"],
    "images_A000000250199": ["celimax", "셀리맥스"],
}

VARIANTS: dict[str, dict] = {
    "text_exact": {"mode": "exact"},
    "text_fuzzy": {"mode": "fuzzy", "ratio": 0.8},
    "text_contains": {"mode": "contains"},
    "line_exact": {"mode": "exact", "unit": "line"},
    "block_exact": {"mode": "exact", "unit": "block"},
}

# poc/block_role/run.py `heuristic_v2` — 복사
MERGE_CFG = dict(line_gap=0.7, para_gap=0.6, h_ratio=1.5, overlap=0.5, gutter=True)

TILE, OVERLAP = 2000, 300

# 텍스트 추출 확정 조건 — poc/B_ocr/run.py `baseline`
OCR_KWARGS = dict(
    lang="korean",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\W_]+", "", s)


# ── ① OCR ────────────────────────────────────────────────────────────

def ocr_page(model, path: Path) -> dict:
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    h = img.shape[0]
    tops = list(range(0, max(1, h - OVERLAP), TILE - OVERLAP))
    regions = []
    t0 = time.perf_counter()
    for i, top in enumerate(tops):
        strip = img[top:top + TILE]
        res = list(model.predict(strip))[0]
        bottom = top + strip.shape[0]
        # 겹친 띠에서 한 번만 남긴다 — 중심이 이 띠의 몫(겹침 절반씩 나눔)에 있을 때
        lo = top + (OVERLAP // 2 if i > 0 else 0)
        hi = bottom - (OVERLAP // 2 if i < len(tops) - 1 else 0)
        for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) + top for p in poly]
            cy = (min(ys) + max(ys)) / 2
            if not (lo <= cy < hi):
                continue
            regions.append({"bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                            "text": text, "score": round(float(score), 4)})
    return {"image": path.name, "height": h, "tiles": len(tops), "regions": regions,
            "sec": round(time.perf_counter() - t0, 2)}


def load_ocr(paths: list[Path]) -> dict[str, dict]:
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    todo = [p for p in paths if not (OCR_CACHE / f"{p.stem}.json").exists()]
    if todo:
        from paddleocr import PaddleOCR

        model = PaddleOCR(**OCR_KWARGS)
        for p in todo:
            d = ocr_page(model, p)
            (OCR_CACHE / f"{p.stem}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
            print(f"  OCR {p.name:<24} 띠 {d['tiles']:>2}  region {len(d['regions']):>4}  {d['sec']}s")
    return {p.name: json.loads((OCR_CACHE / f"{p.stem}.json").read_text(encoding="utf-8")) for p in paths}


# ── 병합 (poc/block_role/run.py 복사 — 역할 분류는 뺌) ─────────────────

def h_of(r: dict) -> int:
    return r["bbox"][3] - r["bbox"][1]


def v_overlap(a: list[int], b: list[int]) -> float:
    top, bot = max(a[1], b[1]), min(a[3], b[3])
    return max(0, bot - top) / max(1, min(a[3] - a[1], b[3] - b[1]))


def h_overlap(a: list[int], b: list[int]) -> float:
    left, right = max(a[0], b[0]), min(a[2], b[2])
    return max(0, right - left) / max(1, min(a[2] - a[0], b[2] - b[0]))


def union_box(boxes: list[list[int]]) -> list[int]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def gutters(regions: list[dict], width: int) -> list[tuple[int, int]]:
    cover = bytearray(width)
    for r in regions:
        x1, x2 = max(0, r["bbox"][0]), min(width, r["bbox"][2])
        for x in range(x1, x2):
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


def merge_lines(regions: list[dict], cfg: dict, gut: list[tuple[int, int]]) -> list[list[int]]:
    order = sorted(range(len(regions)), key=lambda i: regions[i]["bbox"][0])
    lines: list[list[int]] = []
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


def merge_paragraphs(regions: list[dict], lines: list[list[int]], cfg: dict) -> list[list[int]]:
    boxes = [union_box([regions[i]["bbox"] for i in ln]) for ln in lines]
    heights = [max(h_of(regions[i]) for i in ln) for ln in lines]
    groups: list[list[int]] = []
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


def units_of(regions: list[dict], unit: str, width: int) -> list[dict]:
    """대조 단위 목록 — region 그대로 / 병합한 줄 / 병합한 블록."""
    if unit == "region":
        return regions
    gut = gutters(regions, width) if MERGE_CFG["gutter"] else []
    lines = merge_lines(regions, MERGE_CFG, gut)
    if unit == "line":
        groups = [[k] for k in range(len(lines))]
    else:
        groups = merge_paragraphs(regions, lines, MERGE_CFG)
    out = []
    for g in groups:
        ids = [i for k in g for i in lines[k]]
        out.append({"bbox": union_box([regions[i]["bbox"] for i in ids]),
                    "text": "\n".join(" ".join(regions[i]["text"] for i in lines[k]) for k in g),
                    "n_regions": len(ids)})
    return out


# ── ② 대조 ───────────────────────────────────────────────────────────

def match(text: str, keys: list[str], cfg: dict) -> tuple[str, float] | None:
    t = norm(text)
    if not t:
        return None
    best = None
    for k in keys:
        nk = norm(k)
        if cfg["mode"] == "exact":
            r = 1.0 if t == nk else 0.0
            ok = r == 1.0
        elif cfg["mode"] == "fuzzy":
            r = difflib.SequenceMatcher(None, t, nk).ratio()
            ok = r >= cfg["ratio"]
        else:
            r = 1.0 if nk in t else 0.0
            ok = r == 1.0
        if ok and (best is None or r > best[1]):
            best = (k, round(r, 3))
    return best


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def visualize(path: Path, found: list[dict], out: Path) -> None:
    img = Image.open(path).convert("RGB")
    s = 600 / img.width
    img = img.resize((600, max(1, int(img.height * s))), Image.BILINEAR)
    d = ImageDraw.Draw(img)
    font = _font(14)
    for m in found:
        x1, y1, x2, y2 = (int(v * s) for v in m["bbox"])
        d.rectangle([x1, y1, x2, y2], outline=(20, 170, 60), width=3)
        d.rectangle([x1, max(0, y1 - 18), x1 + 160, max(0, y1 - 18) + 18], fill=(20, 170, 60))
        d.text((x1 + 3, max(0, y1 - 17)), m["text"][:18], fill=(255, 255, 255), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=88)


def hit_sheet(items: list[tuple[Path, dict]], out: Path) -> None:
    """통과 region을 주변 여백과 함께 잘라 한 장에 모은다."""
    if not items:
        return
    cw, ch, cols = 300, 170, 5
    font = _font(13)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (120, 120, 120))
    opened: dict[Path, Image.Image] = {}
    for i, (path, m) in enumerate(items):
        if path not in opened:
            opened[path] = Image.open(path).convert("RGB")
        im = opened[path]
        x1, y1, x2, y2 = m["bbox"]
        pad = 40
        box = (max(0, x1 - pad), max(0, y1 - pad), min(im.width, x2 + pad), min(im.height, y2 + pad))
        crop = im.crop(box)
        dr = ImageDraw.Draw(crop)
        dr.rectangle([x1 - box[0], y1 - box[1], x2 - box[0], y2 - box[1]], outline=(20, 170, 60), width=2)
        r = min((cw - 4) / crop.width, (ch - 38) / crop.height, 2.0)
        crop = crop.resize((max(1, int(crop.width * r)), max(1, int(crop.height * r))))
        tile = Image.new("RGB", (cw - 2, ch - 2), (255, 255, 255))
        tile.paste(crop, (0, 36))
        td = ImageDraw.Draw(tile)
        td.text((3, 1), f"{i} {path.stem[-10:]} y{y1}", fill=(200, 0, 0), font=font)
        td.text((3, 18), f"「{m['text'][:28]}」 {m['ratio']}".replace("\n", " / "), fill=(0, 0, 0), font=font)
        sheet.paste(tile, ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


def run_variant(name: str, paths: list[Path], ocr: dict[str, dict], ocr_sec: float) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    (out_dir / "matches").mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    per, sheet_items = [], []
    for path in paths:
        keys = BRANDS[path.parent.name]
        found = []
        with Image.open(path) as im:
            width = im.width
        for rg in units_of(ocr[path.name]["regions"], cfg.get("unit", "region"), width):
            hit = match(rg["text"], keys, cfg)
            if hit:
                found.append({**rg, "key": hit[0], "ratio": hit[1]})
        (out_dir / "matches" / f"{path.stem}.json").write_text(
            json.dumps({"image": path.name, "variant": name, "brand_keys": keys, "matches": found},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        per.append({"image": path.name, "brand_folder": path.parent.name, "pass": len(found)})
        sheet_items += [(path, m) for m in found]
    match_sec = round(time.perf_counter() - t0, 3)

    for path in paths:
        found = json.loads((out_dir / "matches" / f"{path.stem}.json").read_text(encoding="utf-8"))["matches"]
        if found:
            visualize(path, found, out_dir / "vis" / f"{path.stem}.jpg")
    hit_sheet(sheet_items, out_dir / "hits.jpg")

    meta = {"variant": name, "cfg": cfg, "brands": BRANDS, "images": len(paths),
            "total_pass": sum(p["pass"] for p in per),
            "ocr_sec": ocr_sec, "match_sec": match_sec, "tile": TILE, "overlap": OVERLAP,
            "per_image": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] 통과 {meta['total_pass']} · 대조 {match_sec}s")
    for path, m in sheet_items:
        print(f"    {path.stem:<20} y{m['bbox'][1]:>6}  {m['ratio']:<5} 「{m['text']}」".replace("\n", " / "))


# ── 골든 샘플 — 단계 4 재확인 ───────────────────────────────────────────
# 입력 = 단계 2 `llm_assist` 블록(섹션 좌표) + 단계 3 라벨 정답. 대조 규칙은 `block_exact` 그대로.
# 기존 정답과 페이지 좌표로 기계 대조한다. 패키지 위 로고(라벨 블록)는 라벨 판정 소관이라 세지 않는다.
GOLDEN_BLOCKS = ROOT / "poc" / "golden" / "2_block_role" / "results" / "llm_assist" / "blocks"  # 단계 2 이동 후 위치
GOLDEN_LABELS = ROOT / "poc" / "golden" / "3_product_label" / "results" / "vlm_relation" / "truth.json"  # 단계 3 정답
GOLDEN_REGIONS = ROOT / "poc" / "golden" / "1_B_ocr" / "results" / "baseline" / "regions"  # 단계 1 이동 후 위치
GOLDEN_RESULTS = RESULTS / "golden" / "block_exact"
# 대조 단위별 규칙 — 정규화·완전 일치는 같고 입력 단위만 다름
RULE = {"block": VARIANTS["block_exact"], "region": VARIANTS["text_exact"]}
RULE_NAME = {"block": "block_exact", "region": "region_exact"}

# 기존 정답 — 페이지 로고 7개(5장), 페이지 좌표.
# summary.md 6장 `text_exact` 판정(찾음 7 · 놓침 0)의 통과 region 중 단계 3 라벨 블록 밖이고
# 기존 오탐(`비클리닉스` 제목 첫 줄 2건)이 아닌 것. 페이지별 개수가 기존 판정과 일치함.
PAGE_LOGOS = [
    {"image": "A000000213548_002.jpg", "bbox": [385, 162, 611, 230], "text": "b.clinicx"},
    {"image": "A000000213548_002.jpg", "bbox": [386, 5565, 611, 5628], "text": "b.clinicx"},
    {"image": "A000000213548_018.jpg", "bbox": [376, 7601, 623, 7675], "text": "b.clinicx"},
    {"image": "A000000219554_001.jpg", "bbox": [421, 1219, 580, 1288], "text": "goodal"},
    {"image": "A000000219554_002.jpg", "bbox": [556, 33883, 727, 33945], "text": "goodal"},
    {"image": "A000000219554_002.jpg", "bbox": [64, 36418, 396, 36553], "text": "goodal"},
    {"image": "A000000250199_002.jpg", "bbox": [274, 86, 487, 124], "text": "celimax×"},
]
PREV = {"found": 6, "missed": 1, "false": 0}  # 기존 `block_exact`(heuristic_v2 블록) 결과 — 결과 문서 6장


def iou(a: list[int], b: list[int]) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if not inter:
        return 0.0
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def contains(outer: list[int], inner: list[int], tol: int = 6) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def logo_sheet(rows: list[dict], out: Path) -> None:
    """정답 로고 7개 — 초록 찾음 · 빨강 놓침, 파랑 = 로고를 품은 블록."""
    paths = {p.name: p for p in SRC.rglob("*.jpg")}
    cw, ch, cols = 420, 230, 2
    font = _font(13)
    sheet = Image.new("RGB", (cols * cw, ((len(rows) + cols - 1) // cols) * ch), (120, 120, 120))
    opened: dict[str, Image.Image] = {}
    for i, r in enumerate(rows):
        if r["image"] not in opened:
            opened[r["image"]] = Image.open(paths[r["image"]]).convert("RGB")
        im = opened[r["image"]]
        boxes = [r["bbox"]] + ([r["host_page_bbox"]] if r.get("host_page_bbox") else [])
        u = union_box(boxes)
        pad = 30
        box = (max(0, u[0] - pad), max(0, u[1] - pad), min(im.width, u[2] + pad), min(im.height, u[3] + pad))
        crop = im.crop(box)
        dr = ImageDraw.Draw(crop)
        if r.get("host_page_bbox"):
            h = r["host_page_bbox"]
            dr.rectangle([h[0] - box[0], h[1] - box[1], h[2] - box[0], h[3] - box[1]], outline=(30, 90, 220), width=3)
        col = (20, 170, 60) if r["status"] == "찾음" else (220, 30, 30)
        x1, y1, x2, y2 = r["bbox"]
        dr.rectangle([x1 - box[0], y1 - box[1], x2 - box[0], y2 - box[1]], outline=col, width=2)
        s = min((cw - 4) / crop.width, (ch - 40) / crop.height, 2.0)
        crop = crop.resize((max(1, int(crop.width * s)), max(1, int(crop.height * s))))
        tile = Image.new("RGB", (cw - 2, ch - 2), (255, 255, 255))
        tile.paste(crop, (0, 38))
        td = ImageDraw.Draw(tile)
        td.text((3, 1), f"{i + 1} {r['image'][:-4]} y{y1} — {r['status']}", fill=col, font=font)
        td.text((3, 19), f"블록 「{(r.get('host_text') or '없음')[:34]}」".replace("\n", " / "), fill=(0, 0, 0), font=font)
        sheet.paste(tile, ((i % cols) * cw, (i // cols) * ch))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)


def golden_units(unit: str, labels: dict) -> tuple[dict, list, int]:
    """대조 단위를 만든다. `block` = 단계 2 블록 · `region` = 단계 1 OCR 영역.

    영역 단위는 **블록 경계 변화에 영향받지 않는다.** 로고가 옆 글자와 병합돼 놓치는
    문제를 없애는 대신, OCR이 제목을 끊어 읽으면 오탐이 난다 — 그 맞교환을 잰다.
    라벨 소관 판단은 두 단위 모두 **단계 3 정답 블록** 기준(영역은 소속 블록을 따름).
    """
    units_by_page: dict[str, list[dict]] = {}
    hits: list[dict] = []
    sections = 0
    for f in sorted(GOLDEN_BLOCKS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sid, off = d["section"], d["top_offset"]
        image = f"{sid[:17]}.jpg"
        keys = BRANDS[f"images_{sid[:13]}"]
        lab = set(labels.get(sid, []))
        sections += 1
        rows = []
        if unit == "block":
            for i, b in enumerate(d["blocks"], 1):
                rows.append({"section": sid, "block": i, "text": b["text"], "bbox": b["bbox"],
                             "is_product_label": i in lab})
        else:
            regions = json.loads((GOLDEN_REGIONS / f"{sid}.json").read_text(encoding="utf-8"))["regions"]
            owner = {ri: i for i, b in enumerate(d["blocks"], 1) for ri in b["regions"]}
            for ri, reg in enumerate(regions):
                bi = owner.get(ri)
                rows.append({"section": sid, "block": bi, "region": ri + 1, "text": reg["text"],
                             "bbox": reg["bbox"], "is_product_label": bi in lab})
        for row in rows:
            x0, y0, x1, y1 = row["bbox"]
            row = {**row, "image": image, "page_bbox": [x0, y0 + off, x1, y1 + off]}
            units_by_page.setdefault(image, []).append(row)
            h = match(row["text"], keys, RULE[unit])
            if h:
                hits.append({**row, "key": h[0]})
    return units_by_page, hits, sections


def run_golden(unit: str = "block") -> None:
    if not GOLDEN_BLOCKS.exists() or not GOLDEN_LABELS.exists():
        raise SystemExit("단계 2·3 결과 없음 — poc/golden/2_block_role · 3_product_label 확인")
    if unit == "region" and not GOLDEN_REGIONS.exists():
        raise SystemExit(f"단계 1 영역 없음 — {GOLDEN_REGIONS}")
    labels = json.loads(GOLDEN_LABELS.read_text(encoding="utf-8"))["labels"]
    rule = RULE_NAME[unit]
    cfg = RULE[unit]
    out_dir = RESULTS / "golden" / rule
    t0 = time.perf_counter()
    blocks_by_page, hits, sections = golden_units(unit, labels)
    match_sec = round(time.perf_counter() - t0, 3)

    prev = {}
    for g in PAGE_LOGOS:
        m = json.loads((RESULTS / "block_exact" / "matches" / f"{g['image'][:-4]}.json").read_text(encoding="utf-8"))["matches"]
        prev[(g["image"], tuple(g["bbox"]))] = any(iou(g["bbox"], x["bbox"]) >= 0.5 for x in m)

    truth_rows, used = [], set()
    for g in PAGE_LOGOS:
        page_hits = [h for h in hits if h["image"] == g["image"] and not h["is_product_label"]]
        best = max(page_hits, key=lambda h: iou(g["bbox"], h["page_bbox"]), default=None)
        ok = best is not None and iou(g["bbox"], best["page_bbox"]) >= 0.5
        if ok:
            used.add((best["section"], best["block"], best.get("region")))
        host = next((b for b in blocks_by_page.get(g["image"], []) if contains(b["page_bbox"], g["bbox"])), None)
        truth_rows.append({**g, "status": "찾음" if ok else "놓침",
                           "prev_block_exact": "찾음" if prev[(g["image"], tuple(g["bbox"]))] else "놓침",
                           "host_section": host["section"] if host else None, "host_block": host["block"] if host else None,
                           "host_text": host["text"] if host else None, "host_page_bbox": host["page_bbox"] if host else None,
                           "host_is_label": host["is_product_label"] if host else None})
    false_hits = [h for h in hits if not h["is_product_label"]
                  and (h["section"], h["block"], h.get("region")) not in used]
    package = [h for h in hits if h["is_product_label"]]
    counts = {"found": sum(r["status"] == "찾음" for r in truth_rows),
              "missed": sum(r["status"] == "놓침" for r in truth_rows), "false": len(false_hits)}
    passed = counts["missed"] <= PREV["missed"] and counts["false"] <= PREV["false"]

    out_dir.mkdir(parents=True, exist_ok=True)
    logo_sheet(truth_rows, out_dir / "logos.jpg")
    meta = {"variant": rule, "unit": unit, "sample": "golden", "cfg": cfg, "brands": BRANDS,
            "source": ("poc/golden/1_B_ocr/results/baseline 영역" if unit == "region"
                       else "poc/golden/2_block_role/results/llm_assist 블록")
                      + " · 라벨 poc/golden/3_product_label/.../truth.json",
            "sections": sections, "units": sum(len(v) for v in blocks_by_page.values()),
            "pass": len(hits), "pass_label": len(package), "match_sec": match_sec,
            "counts": counts, "prev": PREV, "gate": "통과" if passed else "미달",
            "page_logos": truth_rows, "false_hits": false_hits, "package_hits": package,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[golden/{rule}] 섹션 {sections} · 통과 {len(hits)} (라벨 소관 {len(package)}) · {match_sec}s")
    print(f"  찾음 {counts['found']} · 놓침 {counts['missed']} · 오탐 {counts['false']}  "
          f"(기존 {PREV['found']}·{PREV['missed']}·{PREV['false']}) → {meta['gate']}")
    for r in truth_rows:
        print(f"    {r['image']:<22} y{r['bbox'][1]:>6} {r['status']} (기존 {r['prev_block_exact']})  "
              f"블록 {r['host_section']}#{r['host_block']} 「{r['host_text']}」".replace("\n", " / "))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    ap.add_argument("--sample", choices=("default", "golden"), default="default",
                    help="golden = 골든 샘플 단계 4 재확인")
    ap.add_argument("--unit", choices=("block", "region", "all"), default="block",
                    help="golden 전용 — 대조 단위. block=단계 2 블록(block_exact) · region=단계 1 영역(region_exact)")
    args = ap.parse_args()

    if args.sample == "golden":
        for u in (("block", "region") if args.unit == "all" else (args.unit,)):
            run_golden(u)
        return
    if not args.variant:
        raise SystemExit("--variant 필요")

    paths = sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name))
    if args.images:
        paths = [p for p in paths if p.name in args.images]
    ocr = load_ocr(paths)
    ocr_sec = round(sum(d["sec"] for d in ocr.values()), 2)
    print(f"OCR {len(paths)}장 · region {sum(len(d['regions']) for d in ocr.values())} · {ocr_sec}s")

    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, paths, ocr, ocr_sec)


if __name__ == "__main__":
    main()
