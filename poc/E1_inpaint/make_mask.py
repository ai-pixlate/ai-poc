"""E1. 원문 지우기 — 인페인팅 마스크 생성기.

B(OCR) 출력의 poly를 채우고 바깥으로 몇 px 부풀려 마스크를 만든다.
수동 라벨링을 하지 않으므로 마스크 출처는 B 결과가 전부다.

사용법
    python make_mask.py                          # 전체
    python make_mask.py --images 1.jpg 5.jpg     # 일부
    python make_mask.py --ratio 0.25 --tag d25   # 팽창 폭 실험

왜 부풀리는가
    B의 poly는 글자에 거의 딱 붙는다. 그대로 지우면 글자 테두리의
    안티에일리어싱 화소가 남아 얼룩으로 보인다. 반대로 너무 부풀리면
    배경까지 뭉개진다. 글자 높이에 비례시켜야 큰 제목과 잔글씨가
    같이 처리된다 — 고정 px는 한쪽이 반드시 틀어진다.

출력
    results/masks/{tag}/{stem}.png       흰색 = 지울 곳
    results/masks/{tag}/vis/{stem}.jpg   원본에 마스크를 겹쳐 확인용
    results/masks/{tag}/meta.json        팽창 규칙·영역 수
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
# E1은 B의 채택 variant 출력을 입력으로 쓴다 (2026-08-20 baseline 확정).
B_REGIONS = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"
RESULTS = HERE / "results" / "masks"


def build_mask(shape: tuple[int, int], regions: list[dict], ratio: float, min_px: int) -> np.ndarray:
    """regions → 이진 마스크. 팽창 폭은 영역마다 글자 높이에 비례해 따로 정한다."""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        d = max(min_px, int(round((y2 - y1) * ratio)))
        pad = d + 2
        # 영역 주변만 잘라 처리한다. 전체 캔버스를 영역 수만큼 팽창시키면 느리다.
        sx1, sy1 = max(0, x1 - pad), max(0, y1 - pad)
        sx2, sy2 = min(w, x2 + pad), min(h, y2 + pad)
        if sx2 <= sx1 or sy2 <= sy1:
            continue
        sub = np.zeros((sy2 - sy1, sx2 - sx1), np.uint8)
        poly = np.array(r["poly"], np.int32) - [sx1, sy1]
        cv2.fillPoly(sub, [poly], 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
        sub = cv2.dilate(sub, kernel)
        np.maximum(mask[sy1:sy2, sx1:sx2], sub, out=mask[sy1:sy2, sx1:sx2])
    return mask


def overlay(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """마스크를 빨갛게 반투명으로 얹어 어디를 지울지 눈으로 확인."""
    tint = img.copy()
    tint[mask > 0] = (0, 0, 255)
    return cv2.addWeighted(img, 0.55, tint, 0.45, 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratio", type=float, default=0.15, help="글자 높이 대비 팽창 비율")
    ap.add_argument("--min-px", type=int, default=3, help="최소 팽창 px")
    ap.add_argument("--tag", default=None, help="출력 폴더명. 기본은 ratio에서 만듦")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    tag = args.tag or f"d{int(args.ratio * 100):02d}"
    out_dir = RESULTS / tag
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    stems = [Path(n).stem for n in args.images] if args.images else None
    files = sorted(B_REGIONS.glob("*.json"), key=lambda p: (len(p.stem), p.stem))
    if stems:
        files = [f for f in files if f.stem in stems]
    if not files:
        raise SystemExit(f"{B_REGIONS} 에 대상 없음. B를 먼저 실행할 것")

    per_image, total = [], 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        img_path = IMAGES / payload["image"]
        img = cv2.imread(str(img_path))
        if img is None:
            raise SystemExit(f"이미지 못 읽음: {img_path}")

        regions = payload["regions"]
        mask = build_mask(img.shape[:2], regions, args.ratio, args.min_px)
        cv2.imwrite(str(out_dir / f"{f.stem}.png"), mask)
        cv2.imwrite(str(out_dir / "vis" / f"{f.stem}.jpg"), overlay(img, mask), [cv2.IMWRITE_JPEG_QUALITY, 92])

        covered = float((mask > 0).sum()) / mask.size * 100
        per_image.append({"image": payload["image"], "regions": len(regions), "covered_pct": round(covered, 1)})
        total += len(regions)
        print(f"  {payload['image']:<10} 영역 {len(regions):>3}개  마스크 면적 {covered:>5.1f}%")

    meta = {
        "tag": tag,
        "source": "poc/B_ocr/results/baseline",
        "dilate_ratio": args.ratio,
        "dilate_min_px": args.min_px,
        "images": len(files),
        "total_regions": total,
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{tag}] 완료 — {len(files)}장, 총 {total}개 영역 → {out_dir}")


if __name__ == "__main__":
    main()
