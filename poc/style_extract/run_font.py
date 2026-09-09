"""스타일 추출 — 굵기·폰트 계열 시험 (추가 축).

계획서에는 **범위 밖(12월)**으로 적힌 항목이다. 되는지만 보려고 붙인다.
전부 로컬 실행, 비용 0.

무엇을 재는가
    굵기   글자 획 두께 ÷ 글자 높이. 이진화한 글자 화소에 거리 변환을 걸어
           획 반지름을 구하고 두 배 한다. 크기에 무관한 비율이라 비교가 된다.
    계열   설치된 한글 폰트 후보로 같은 글자를 렌더해 원본과 겹쳐 본다.
           가장 잘 겹치는 후보의 계열(고딕/명조)과 굵기를 답으로 삼는다.

**한계 — 후보 안에서만 고른다.** 브랜드 전용 폰트나 장식체는 후보에 없으므로
"가장 비슷한 것"이 나올 뿐 정답이 아니다. 계열(고딕/명조) 수준까지가 현실적이다.

variant
    stroke_ratio  획 두께 비율만. 폰트 렌더 없음
    font_match    후보 렌더 대조까지. 계열·굵기를 함께 답한다

입력
    ../B_ocr/results/baseline/regions/{stem}.json
    ../product_label/results/vlm_relation/blocks/{stem}.json   라벨 제외용
    ../../data/images/{stem}.jpg

출력
    results_font/{variant}/fonts/{stem}.json
    results_font/{variant}/vis/{stem}.jpg     조판 대상만. 굵기·계열을 띠에 표기
    results_font/{variant}/meta.json

판정
    사람이 vis/ 를 보고 육안 대조한다. 이 코드는 등급을 매기지 않는다.

사용법
    python run_font.py --variant all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
REGIONS = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"
BLOCKS = ROOT / "poc" / "product_label" / "results" / "vlm_relation" / "blocks"
RESULTS = HERE / "results_font"
FONT_DIR = Path("C:/Windows/Fonts")

# 굵기 판정 임계 — 획 두께 ÷ 글자 높이.
# 본문용 고딕이 대략 0.09~0.12, bold가 0.14~0.18에 온다. 실측으로 다시 볼 값.
BOLD_AT = 0.14

# 폰트 후보. (파일, 계열, 굵기)
CANDIDATES = [
    ("malgun.ttf", "고딕", "regular"),
    ("malgunbd.ttf", "고딕", "bold"),
    ("malgunsl.ttf", "고딕", "light"),
    ("HANDotum.ttf", "고딕", "regular"),
    ("HANDotumB.ttf", "고딕", "bold"),
    ("Hancom Gothic Regular.ttf", "고딕", "regular"),
    ("Hancom Gothic Bold.ttf", "고딕", "bold"),
    ("HanSantteutDotum-Regular.ttf", "고딕", "regular"),
    ("HanSantteutDotum-Bold.ttf", "고딕", "bold"),
    ("gulim.ttc", "고딕", "regular"),
    ("batang.ttc", "명조", "regular"),
    ("HANBatang.ttf", "명조", "regular"),
    ("HANBatangB.ttf", "명조", "bold"),
    ("NotoSerifKR-VF.ttf", "명조", "regular"),
]

VARIANTS = {"stroke_ratio": {"match": False}, "font_match": {"match": True}}
HANGUL = re.compile(r"[가-힣]")
MIN_H = 18          # 이보다 낮은 영역은 획 두께가 의미 없다
NORM_H = 64         # 폰트 대조용 정규화 높이


# ---------------------------------------------------------------- 마스크

def text_mask(crop: np.ndarray) -> np.ndarray:
    """글자 화소만 True. Otsu로 가른 뒤 화소가 적은 쪽을 글자로 본다."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = m.astype(bool)
    return ~m if m.sum() > (~m).sum() else m


def stroke_ratio(mask: np.ndarray) -> float | None:
    """획 두께 ÷ 글자 높이.

    거리 변환의 최대값이 획 반지름이다. 잡음에 흔들리지 않게 상위 20% 평균을 쓴다.
    """
    if mask.sum() < 20:
        return None
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    vals = dist[mask]
    if vals.size == 0:
        return None
    top = np.sort(vals)[int(vals.size * 0.8):]
    return round(float(2 * top.mean() / mask.shape[0]), 3)


# ---------------------------------------------------------------- 폰트 대조

_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def load(file: str, px: int):
    key = (file, px)
    if key not in _cache:
        try:
            _cache[key] = ImageFont.truetype(str(FONT_DIR / file), px)
        except OSError:
            _cache[key] = None
    return _cache[key]


def render_mask(text: str, file: str, height: int) -> np.ndarray | None:
    """후보 폰트로 글자를 그려 이진 마스크를 만든다. 높이를 맞춰 정규화한다."""
    font = load(file, height)
    if font is None:
        return None
    w = int(font.getlength(text)) + 4
    if w < 4:
        return None
    img = Image.new("L", (w, int(height * 1.6)), 0)
    ImageDraw.Draw(img).text((2, 0), text, fill=255, font=font)
    a = np.array(img) > 127
    ys, xs = np.where(a)
    if ys.size == 0:
        return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def norm(mask: np.ndarray) -> np.ndarray:
    """세로를 NORM_H로 맞추고 가로는 비율 유지. 겹침 비교용."""
    h, w = mask.shape
    if h == 0 or w == 0:
        return np.zeros((NORM_H, NORM_H), bool)
    scale = NORM_H / h
    out = cv2.resize(mask.astype(np.uint8), (max(1, int(w * scale)), NORM_H),
                     interpolation=cv2.INTER_AREA)
    return out > 0


def iou(a: np.ndarray, b: np.ndarray) -> float:
    w = min(a.shape[1], b.shape[1])
    if w == 0:
        return 0.0
    a, b = a[:, :w], b[:, :w]
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def match_font(crop_mask: np.ndarray, text: str) -> dict | None:
    """후보를 렌더해 가장 잘 겹치는 것을 고른다."""
    ys, xs = np.where(crop_mask)
    if ys.size == 0:
        return None
    tight = crop_mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    target = norm(tight)

    scored = []
    for file, family, weight in CANDIDATES:
        m = render_mask(text, file, NORM_H)
        if m is None:
            continue
        scored.append((iou(target, norm(m)), file, family, weight))
    if not scored:
        return None
    scored.sort(reverse=True)
    best = scored[0]
    fam = {}
    for sc, _f, family, _w in scored:
        fam[family] = max(fam.get(family, 0), sc)
    return {
        "font_best": best[1], "font_family": best[2], "font_weight": best[3],
        "font_score": round(best[0], 3),
        "family_gap": round(abs(fam.get("고딕", 0) - fam.get("명조", 0)), 3),
    }


# ---------------------------------------------------------------- 시각화

def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def visualize(img_path: Path, rows: list[dict], out_path: Path) -> None:
    img = Image.open(img_path).convert("RGB")
    pad = 380
    size = max(12, min(img.width, img.height) // 70)
    row_h = max(18, size + 8)
    canvas = Image.new("RGB", (img.width + pad, max(img.height, 8 + len(rows) * row_h)),
                       (250, 250, 250))
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(size)

    for r in rows:
        x1, y1, x2, y2 = r["bbox"]
        draw.rectangle([x1, y1, x2, y2], outline=(120, 120, 120), width=1)
        draw.text((x1, max(0, y1 - size - 2)), str(r["no"]), fill=(90, 90, 90), font=font)

    for i, r in enumerate(rows):
        top = 4 + i * row_h
        x = img.width + 6
        sr = r["stroke_ratio"]
        parts = [f"{r['no']:>3}", f"{r['est_font_px']:>3}px",
                 f"{sr if sr is not None else '—':>5}", r["weight_est"] or "—"]
        if r.get("font_family"):
            parts.append(f"{r['font_family']}/{r['font_weight']} {r['font_score']}")
        parts.append(r["text"][:10])
        draw.text((x, top), "  ".join(str(p) for p in parts), fill=(40, 40, 40), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


# ---------------------------------------------------------------- 실행

def run_variant(name: str, stems: list[str]) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    (out_dir / "fonts").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    print(f"[{name}] 폰트 대조 {'있음' if cfg['match'] else '없음'}")
    per_image, weights, families = [], {}, {}
    t_all = time.perf_counter()

    for stem in stems:
        regions = json.loads((REGIONS / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
        blocks = json.loads((BLOCKS / f"{stem}.json").read_text(encoding="utf-8"))["blocks"]
        label_of = {}
        for b in blocks:
            for ri in b["regions"]:
                label_of[ri] = b["is_product_label"]

        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        bgr = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)

        rows = []
        for ri, reg in enumerate(regions):
            if label_of.get(ri):        # 제품 라벨은 하류에서 빠지므로 재지 않는다
                continue
            x1, y1, x2, y2 = reg["bbox"]
            crop = bgr[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
            if crop.size == 0 or (y2 - y1) < MIN_H:
                continue
            mask = text_mask(crop)
            sr = stroke_ratio(mask)
            row = {
                "no": ri + 1, "region": ri, "bbox": reg["bbox"], "text": reg["text"],
                "est_font_px": y2 - y1,
                "stroke_ratio": sr,
                "weight_est": None if sr is None else ("bold" if sr >= BOLD_AT else "regular"),
            }
            if cfg["match"] and HANGUL.search(reg["text"]) and len(reg["text"].strip()) >= 2:
                got = match_font(mask, reg["text"].strip())
                if got:
                    row.update(got)
                    families[got["font_family"]] = families.get(got["font_family"], 0) + 1
            weights[row["weight_est"]] = weights.get(row["weight_est"], 0) + 1
            rows.append(row)

        (out_dir / "fonts" / f"{stem}.json").write_text(
            json.dumps({"image": img_path.name, "variant": name, "regions": rows},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        visualize(img_path, rows, out_dir / "vis" / f"{stem}.jpg")
        srs = [r["stroke_ratio"] for r in rows if r["stroke_ratio"] is not None]
        med = round(sorted(srs)[len(srs) // 2], 3) if srs else None
        per_image.append({"image": img_path.name, "regions": len(rows), "stroke_median": med})
        print(f"  {img_path.name:<10} 대상 {len(rows):>3}  획비율 중앙 {med}")

    meta = {
        "variant": name, "cfg": {**cfg, "bold_at": BOLD_AT, "min_height": MIN_H},
        "candidates": len(CANDIDATES),
        "images": len(stems),
        "total_regions": sum(p["regions"] for p in per_image),
        "weight_dist": weights, "family_dist": families,
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image, "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 대상 {meta['total_regions']}, {meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    stems = (
        [Path(n).stem for n in args.images]
        if args.images
        else sorted((p.stem for p in REGIONS.glob("*.json")), key=lambda s: (len(s), s))
    )
    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, stems)


if __name__ == "__main__":
    main()
