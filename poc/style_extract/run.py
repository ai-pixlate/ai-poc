"""스타일 추출 — variant 실행기.

번역문을 원본과 비슷하게 얹으려면 원문의 **글자색·크기·정렬**이 필요하다.
그 셋을 원본 이미지에서 뽑아낸다. 전부 로컬 실행, 비용 0.

variant — 글자색을 어떻게 배경에서 갈라내는가
    dominant_color  bbox 안 화소를 2색으로 군집(k-means). 적은 쪽을 글자로 본다.
    contrast_split  밝기 히스토그램을 Otsu로 자른다. 적은 쪽을 글자로 본다.

두 방식 모두 **글자는 배경보다 화소가 적다**는 가정에 선다. 굵은 대형 글자나
글자가 박스를 가득 채우는 경우 이 가정이 깨진다 — 판정에서 볼 지점.

크기·정렬은 두 variant가 같다. 변인은 색 추출 방식뿐이다.
    크기  bbox 높이 = 글자 획 높이. em 환산은 × 1.35 (길이 팽창률 과업과 같은 가정)
    정렬  블록 안 행들의 좌·중앙·우 좌표 분산을 비교해 가장 고른 축을 고른다

범위 밖 (12월)
    굵기 추정, 폰트 패밀리 식별

입력
    ../B_ocr/results/baseline/regions/{stem}.json          영역 bbox
    ../product_label/results/vlm_relation/blocks/{stem}.json  블록·역할·라벨 여부
    ../../data/images/{stem}.jpg

출력
    results/{variant}/styles/{stem}.json   영역별 색·크기 + 블록별 정렬
    results/{variant}/vis/{stem}.jpg        전체 영역
    results/{variant}/vis_target/{stem}.jpg **조판 대상만** — 제품 라벨 제외.
                                            번호는 전체 뷰와 같게 유지한다
    results/{variant}/meta.json            집계

판정
    사람이 vis/ 를 보고 색·크기·정렬을 육안 대조한다. 이 코드는 등급을 매기지 않는다.

사용법
    python run.py --variant all
"""

from __future__ import annotations

import argparse
import json
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
RESULTS = HERE / "results"

EM_RATIO = 1.35        # bbox 높이 → em. 길이 팽창률 과업과 같은 가정
ALIGN_TOL = 0.12       # 정렬 판정 허용 오차 (블록 폭 대비)

VARIANTS = {"dominant_color": {}, "contrast_split": {}}


# ---------------------------------------------------------------- 색 추출

def _hex(bgr) -> str:
    b, g, r = (int(round(v)) for v in bgr)
    return f"#{r:02X}{g:02X}{b:02X}"


def _luma(bgr) -> float:
    b, g, r = bgr
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    """WCAG 명도 대비. 색 추출이 실제로 갈렸는지 보는 기계 지표."""
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def rel(bgr):
        bb, gg, rr = (lin(v) for v in bgr)
        return 0.2126 * rr + 0.7152 * gg + 0.0722 * bb

    l1, l2 = sorted((rel(a), rel(b)), reverse=True)
    return round(float((l1 + 0.05) / (l2 + 0.05)), 2)


def split_kmeans(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """2색 군집. 화소가 적은 군집을 글자로 본다."""
    px = crop.reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(px, 2, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=2)
    fg, bg = (0, 1) if counts[0] <= counts[1] else (1, 0)
    return centers[fg], centers[bg]


def split_otsu(crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """밝기 Otsu 이진화. 화소가 적은 쪽을 글자로 본다."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = mask.reshape(-1).astype(bool)
    px = crop.reshape(-1, 3)
    if m.sum() == 0 or (~m).sum() == 0:
        mean = px.mean(axis=0)
        return mean, mean
    a, b = px[m], px[~m]
    fg, bg = (a, b) if len(a) <= len(b) else (b, a)
    return fg.mean(axis=0), bg.mean(axis=0)


SPLIT = {"dominant_color": split_kmeans, "contrast_split": split_otsu}


# ---------------------------------------------------------------- 정렬

def block_align(boxes: list[list[int]]) -> str:
    """블록 안 행들의 좌·중앙·우 중 어느 축이 가장 고른가."""
    if len(boxes) < 2:
        return "단일행"
    lefts = [b[0] for b in boxes]
    rights = [b[2] for b in boxes]
    centers = [(b[0] + b[2]) / 2 for b in boxes]
    width = max(rights) - min(lefts)
    if width <= 0:
        return "단일행"
    spread = {
        "left": (max(lefts) - min(lefts)) / width,
        "center": (max(centers) - min(centers)) / width,
        "right": (max(rights) - min(rights)) / width,
    }
    best = min(spread, key=spread.get)
    return best if spread[best] <= ALIGN_TOL else "불명"


# ---------------------------------------------------------------- 시각화

def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def visualize(img_path: Path, rows: list[dict], out_path: Path) -> None:
    """원본 오른쪽에 스와치 띠를 붙인다. 원본 글자와 추출색을 나란히 본다."""
    img = Image.open(img_path).convert("RGB")
    pad = 330
    size = max(12, min(img.width, img.height) // 70)
    row_h = max(18, size + 8)
    # 영역이 많으면 띠가 이미지보다 길어진다. 잘리지 않게 캔버스를 늘린다.
    height = max(img.height, 8 + len(rows) * row_h)
    canvas = Image.new("RGB", (img.width + pad, height), (250, 250, 250))
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(size)

    for r in rows:
        x1, y1, x2, y2 = r["bbox"]
        draw.rectangle([x1, y1, x2, y2], outline=(120, 120, 120), width=1)
        draw.text((x1, max(0, y1 - size - 2)), str(r["no"]), fill=(90, 90, 90), font=font)

    # 오른쪽 띠 — 영역 번호 / 글자색 / 배경색 / 크기 / 정렬
    for i, r in enumerate(rows):
        top = 4 + i * row_h
        x = img.width + 6
        draw.text((x, top), f"{r['no']:>3}", fill=(60, 60, 60), font=font)
        draw.rectangle([x + 34, top, x + 34 + row_h - 6, top + row_h - 6],
                       fill=r["font_color"], outline=(180, 180, 180))
        draw.rectangle([x + 34 + row_h, top, x + 34 + 2 * row_h - 6, top + row_h - 6],
                       fill=r["bg_color"], outline=(180, 180, 180))
        align_short = {"단일행": "1행", "left": "좌", "center": "중", "right": "우",
                       "불명": "?"}.get(r["align"], r["align"])
        draw.text((x + 34 + 2 * row_h + 6, top),
                  f"{r['font_color']} {r['est_font_px']}px {align_short} {r['text'][:8]}",
                  fill=(40, 40, 40), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


# ---------------------------------------------------------------- 실행

def run_variant(name: str, stems: list[str]) -> None:
    split = SPLIT[name]
    out_dir = RESULTS / name
    (out_dir / "styles").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis_target").mkdir(parents=True, exist_ok=True)

    print(f"[{name}]")
    per_image, aligns = [], {}
    t_all = time.perf_counter()

    for stem in stems:
        regions = json.loads((REGIONS / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
        blocks = json.loads((BLOCKS / f"{stem}.json").read_text(encoding="utf-8"))["blocks"]
        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        bgr = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)

        # 영역 → 블록 역참조. 정렬과 role은 블록 단위로 붙는다.
        owner: dict[int, int] = {}
        for bi, b in enumerate(blocks):
            for ri in b["regions"]:
                owner[ri] = bi
        align_of = {}
        for bi, b in enumerate(blocks):
            boxes = [regions[ri]["bbox"] for ri in b["regions"] if ri < len(regions)]
            align_of[bi] = block_align(boxes)

        rows = []
        for ri, reg in enumerate(regions):
            x1, y1, x2, y2 = reg["bbox"]
            crop = bgr[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
            if crop.size == 0:
                continue
            fg, bg = split(crop)
            bi = owner.get(ri)
            h = y2 - y1
            rows.append({
                "region": ri,
                "bbox": reg["bbox"],
                "text": reg["text"],
                "font_color": _hex(fg),
                "bg_color": _hex(bg),
                "contrast": contrast_ratio(fg, bg),
                "est_font_px": h,
                "est_em_px": round(h * EM_RATIO),
                "align": align_of.get(bi, "단일행"),
                "block": bi,
                "role": blocks[bi]["role"] if bi is not None else None,
                "is_product_label": blocks[bi]["is_product_label"] if bi is not None else None,
            })
            aligns[rows[-1]["align"]] = aligns.get(rows[-1]["align"], 0) + 1

        (out_dir / "styles" / f"{stem}.json").write_text(
            json.dumps({"image": img_path.name, "variant": name, "styles": rows},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        for i, r in enumerate(rows, 1):
            r["no"] = i
        visualize(img_path, rows, out_dir / "vis" / f"{stem}.jpg")
        # 조판 대상만 — 제품 라벨은 하류에서 통째로 빠지므로 판정에서도 뺀다
        target = [r for r in rows if not r["is_product_label"]]
        visualize(img_path, target, out_dir / "vis_target" / f"{stem}.jpg")
        med = sorted(r["contrast"] for r in rows)[len(rows) // 2] if rows else 0
        low = sum(1 for r in target if r["contrast"] < 1.5)
        per_image.append({"image": img_path.name, "regions": len(rows),
                          "target_regions": len(target), "target_low_contrast": low,
                          "contrast_median": med})
        print(f"  {img_path.name:<10} 영역 {len(rows):>3}  조판 대상 {len(target):>3}  "
              f"대비 중앙 {med}")

    meta = {
        "variant": name,
        "cfg": {"em_ratio": EM_RATIO, "align_tol": ALIGN_TOL},
        "images": len(stems),
        "total_regions": sum(p["regions"] for p in per_image),
        "align_dist": aligns,
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 영역 {meta['total_regions']}, {meta['total_sec']}s\n")


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
