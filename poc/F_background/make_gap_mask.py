"""F. 배경 가공 — 여백(조각-캔버스 경계) 마스크 생성기.

목적
    조각을 이어붙인 결과에서 조각 바깥에 남은 흰 캔버스를 채울 대상으로 잡는다.
    조각과 캔버스가 만나는 경계도 자연스럽게 이어져야 하므로, 마스크를 조각
    **안쪽으로 몇 px 파고들게** 만든다. 경계선 자체를 다시 그리게 하려는 것 —
    흰 부분만 정확히 채우면 조각 가장자리가 그대로 남아 딱딱한 선이 보인다.

사용법
    python make_gap_mask.py --images sample_1 sample_2 sample_3
    python make_gap_mask.py --images sample_2 --overlap 12 --lines sample_2:h498

출력
    results/gap_masks/{stem}.png       흰색 = 채울 곳
    results/gap_masks/vis/{stem}.jpg   원본에 마스크를 겹쳐 확인용
    results/gap_masks/meta.json
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
OUT_DIR = HERE / "results" / "gap_masks"


def find_source(stem: str) -> Path:
    for ext in (".png", ".PNG", ".jpg", ".jpeg"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"이미지 못 찾음: {stem}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--white", type=int, default=245, help="캔버스로 볼 밝기 문턱")
    ap.add_argument("--overlap", type=int, default=8,
                    help="조각 안쪽으로 파고들 px. 경계선을 다시 그리게 해 딱딱한 선을 없앤다")
    ap.add_argument("--lines", nargs="*", default=None,
                    help="추가로 채울 선. 예: sample_2:h498 (조각 내부 이음새)")
    ap.add_argument("--line-band", type=int, default=28, help="추가 선의 띠 두께")
    args = ap.parse_args()

    extra: dict[str, tuple[list[int], list[int]]] = {}
    for spec in args.lines or []:
        stem, _, coords = spec.partition(":")
        ys, xs = [], []
        for tok in coords.split(","):
            tok = tok.strip()
            if tok[:1] == "h":
                ys.append(int(tok[1:]))
            elif tok[:1] == "v":
                xs.append(int(tok[1:]))
        extra[Path(stem).stem] = (ys, xs)

    (OUT_DIR / "vis").mkdir(parents=True, exist_ok=True)
    half = max(1, args.line_band // 2)
    info = {}

    for name in args.images:
        stem = Path(name).stem
        img = cv2.imdecode(np.fromfile(str(find_source(stem)), np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        white = (img > args.white).all(axis=2).astype(np.uint8) * 255
        # 조각 안쪽 밝은 화소(흰 옷·흰 종이)가 캔버스로 오인되지 않도록 정리한다.
        # 캔버스는 큰 덩어리로 이어져 있고 화면 가장자리에 닿는다.
        white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(white, 8)
        canvas = np.zeros((h, w), np.uint8)
        for i in range(1, n):
            x, y, ww, hh, area = stats[i]
            touches_border = x == 0 or y == 0 or x + ww >= w or y + hh >= h
            if touches_border and area > 0.005 * h * w:
                canvas[labels == i] = 255

        raw_pct = float((canvas > 0).mean() * 100)
        # 조각 안쪽으로 파고들기 — 경계선을 마스크 안에 넣어 다시 그리게 한다
        if args.overlap > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * args.overlap + 1,) * 2)
            canvas = cv2.dilate(canvas, k)

        ys, xs = extra.get(stem, ([], []))
        for y in ys:
            canvas[max(0, y - half):min(h, y + half + 1), :] = 255
        for x in xs:
            canvas[:, max(0, x - half):min(w, x + half + 1)] = 255

        cv2.imwrite(str(OUT_DIR / f"{stem}.png"), canvas)
        tint = img.copy()
        tint[canvas > 0] = (0, 0, 255)
        cv2.imwrite(str(OUT_DIR / "vis" / f"{stem}.jpg"),
                    cv2.addWeighted(img, 0.55, tint, 0.45, 0), [cv2.IMWRITE_JPEG_QUALITY, 92])

        info[stem] = {
            "canvas_pct": round(raw_pct, 2),
            "mask_pct": round(float((canvas > 0).mean() * 100), 2),
            "extra_lines": {"h": ys, "v": xs},
        }
        print(f"  {stem:<12} 여백 {raw_pct:>5.1f}% → 마스크 {info[stem]['mask_pct']:>5.1f}%"
              + (f"  (추가선 h{ys} v{xs})" if ys or xs else ""))

    meta = {"white_thr": args.white, "overlap_px": args.overlap,
            "line_band": args.line_band, "images": info,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 → {OUT_DIR}")


if __name__ == "__main__":
    main()
