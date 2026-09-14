"""긴 이미지 분할 경계 — OCR 실행기.

초장축 상세페이지는 검출기 입력 긴 변 상한(4,000px) 때문에 통째로 넣으면 축소된다.
잘라서 넣으면 **자른 자리의 글자가 빠지거나 잘리거나 두 번 나올 수 있다.**
분할 방식별로 OCR을 돌려 페이지 좌표로 합쳐 둔다. 판정은 compare.py.

입력 — 골든 샘플 34장. 전부 로컬, 비용 0.
OCR 조건 — 텍스트 추출 확정 조건(poc/B_ocr/run.py `baseline`).

variant
    full_page       자르지 않음 — 축소 영향 확인용
    tile_2000       2,000px 띠, 겹침 없음
    tile_2000_ov300 2,000px 띠, 300px 겹침. 중심이 띠의 몫(겹침 절반씩)에 든 region만 남김
    unit_ws_std     섹션 분해 `ws_std` 처리 단위 — 여백마다 자름(최대 2,112px)
    section_vlm2    섹션 분해 채택안 `color_snap_vlm2` 의미 섹션(최대 4,491px)

출력
    results/{variant}/regions/{stem}.json   region(페이지 좌표) · 조각 목록 · 이음선
    results/{variant}/meta.json

사용법
    python run.py --variant all
    python run.py --variant tile_2000 --images A000000219554_002.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
SECTIONS = ROOT / "poc" / "section_split" / "results"
RESULTS = HERE / "results"

VARIANTS = ("full_page", "tile_2000", "tile_2000_ov300", "unit_ws_std", "section_vlm2")
TILE, OVERLAP = 2000, 300
EDGE_PX = 2   # 조각 위아래 경계에서 이 안에 닿으면 '경계에 닿은 region'

# 텍스트 추출 확정 조건 — poc/B_ocr/run.py `baseline`
OCR_KWARGS = dict(
    lang="korean",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)


def chunks_of(variant: str, stem: str, h: int) -> tuple[list[tuple[int, int]], list[int], list[tuple[int, int]]]:
    """(조각 [top, bottom), 이음선 y, 조각별 region 채택 구간)."""
    if variant == "full_page":
        return [(0, h)], [], [(0, h)]
    if variant == "tile_2000":
        ch = [(t, min(h, t + TILE)) for t in range(0, h, TILE)]
        return ch, [t for t, _ in ch[1:]], ch
    if variant == "tile_2000_ov300":
        tops = list(range(0, max(1, h - OVERLAP), TILE - OVERLAP))
        ch = [(t, min(h, t + TILE)) for t in tops]
        keep = []
        for i, (t, b) in enumerate(ch):
            lo = t + (OVERLAP // 2 if i > 0 else 0)
            hi = b - (OVERLAP // 2 if i < len(ch) - 1 else 0)
            keep.append((lo, hi))
        return ch, [k[0] for k in keep[1:]], keep
    src = {"unit_ws_std": "ws_std", "section_vlm2": "color_snap_vlm2"}[variant]
    sec = json.loads((SECTIONS / src / "sections" / f"{stem}.json").read_text(encoding="utf-8"))
    ch = [tuple(s["range"]) for s in sec["sections"]]
    return ch, [t for t, _ in ch[1:]], ch


def run_variant(model, variant: str, paths: list[Path]) -> None:
    out = RESULTS / variant / "regions"
    out.mkdir(parents=True, exist_ok=True)
    per, t_all = [], time.perf_counter()
    for path in paths:
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        h = img.shape[0]
        chunks, seams, keep = chunks_of(variant, path.stem, h)
        regions, errors, t0 = [], [], time.perf_counter()
        for ci, ((top, bottom), (lo, hi)) in enumerate(zip(chunks, keep)):
            try:
                res = list(model.predict(img[top:bottom]))[0]
            except cv2.error as e:
                # 32,767px 넘는 입력은 PaddleOCR 내부 크롭(cv2.warpPerspective)이 거부함
                errors.append({"chunk": ci, "range": [top, bottom], "error": str(e).splitlines()[-1][:160]})
                continue
            for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
                xs = [float(p[0]) for p in poly]
                ys = [float(p[1]) for p in poly]
                y0, y1 = min(ys) + top, max(ys) + top
                cy = (y0 + y1) / 2
                if not (lo <= cy < hi or (ci == len(chunks) - 1 and cy >= hi)):
                    continue
                touch = ((top > 0 and min(ys) <= EDGE_PX) or
                         (bottom < h and max(ys) >= (bottom - top) - EDGE_PX))
                regions.append({"bbox": [int(min(xs)), int(y0), int(max(xs)), int(y1)],
                                "text": text, "score": round(float(score), 4),
                                "chunk": ci, "edge_touch": bool(touch)})
        sec = round(time.perf_counter() - t0, 2)
        (out / f"{path.stem}.json").write_text(json.dumps(
            {"image": path.name, "variant": variant, "height": h, "chunks": chunks, "seams": seams,
             "regions": regions, "errors": errors, "sec": sec}, ensure_ascii=False, indent=1), encoding="utf-8")
        per.append({"image": path.name, "chunks": len(chunks), "max_chunk": max(b - t for t, b in chunks),
                    "regions": len(regions), "errors": len(errors), "sec": sec})
        print(f"  [{variant}] {path.name:<24} 조각 {len(chunks):>3}  region {len(regions):>4}  "
              f"{sec}s{'  오류 ' + str(len(errors)) if errors else ''}")
    meta = {"variant": variant, "tile": TILE, "overlap": OVERLAP, "images": len(paths),
            "total_regions": sum(p["regions"] for p in per),
            "total_sec": round(time.perf_counter() - t_all, 2), "per_image": per,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (RESULTS / variant / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{variant}] region {meta['total_regions']} · {meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    paths = sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name))
    if args.images:
        paths = [p for p in paths if p.name in args.images]
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for n in names:
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")

    from paddleocr import PaddleOCR

    model = PaddleOCR(**OCR_KWARGS)
    for n in names:
        run_variant(model, n, paths)


if __name__ == "__main__":
    main()
