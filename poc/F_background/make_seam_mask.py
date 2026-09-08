"""F. 배경 가공 — 조각 이음새 마스크 생성기.

사용법
    python make_seam_mask.py --images sample_1 sample_2 sample_3
    python make_seam_mask.py --images sample_2 --band 12 --min-frac 0.6

출력
    results/seam_masks/{stem}.png       흰색 = 이음새 띠
    results/seam_masks/vis/{stem}.jpg   검출 위치를 원본에 표시
    results/seam_masks/meta.json        검출된 선 좌표

⚠️ 실서비스에서는 이 검출이 필요 없다. 조각을 배치한 A(리플로우)가 이음새
좌표를 이미 알고 있으므로 F에 그대로 넘기면 된다. 여기서 검출하는 이유는
좌표 없이 합성된 PNG만 받았기 때문이며, 검출은 보조 수단으로만 본다.

검출 방식
    조각 내부를 가로지르는 선은 **조각 폭 전체에 걸쳐** 불연속이 나타난다.
    반면 사진 속 물체 경계는 국소적이다. 그래서 "불연속 화소의 비율"로 가른다.
    흰 캔버스 여백은 조각이 아니므로 계산에서 뺀다.
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
OUT_DIR = HERE / "results" / "seam_masks"


def find_source(stem: str) -> Path:
    for ext in (".png", ".PNG", ".jpg", ".jpeg"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"이미지 못 찾음: {stem}")


def seam_lines(img: np.ndarray, axis: int, min_frac: float, jump: int) -> list[int]:
    """axis=0이면 가로 이음새(y좌표), 1이면 세로 이음새(x좌표)."""
    g = img.astype(np.int16)
    white = (img > 245).all(axis=2)
    if axis == 0:
        d = np.abs(np.diff(g, axis=0)).max(axis=2)
        valid = ~(white[:-1] | white[1:])
        red = 1
    else:
        d = np.abs(np.diff(g, axis=1)).max(axis=2)
        valid = ~(white[:, :-1] | white[:, 1:])
        red = 0

    n = valid.sum(axis=red)
    hit = ((d > jump) & valid).sum(axis=red)
    frac = np.divide(hit, n, out=np.zeros(len(n), float), where=n > 0)
    # 조각을 가로지르는 선만 본다. 유효 길이가 짧으면 조각 경계가 아니라 잡음이다.
    frac[n < 0.3 * valid.shape[red]] = 0

    cand = np.where(frac >= min_frac)[0]
    # 비최대 억제 — 같은 이음새가 여러 행에 걸쳐 잡히면 가장 강한 행만 남긴다
    lines: list[int] = []
    for i in sorted(cand, key=lambda k: -frac[k]):
        if all(abs(i - j) > 10 for j in lines):
            lines.append(int(i))
    return sorted(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--band", type=int, default=8, help="이음새 띠 두께(px, 선 양쪽으로 절반씩)")
    ap.add_argument("--min-frac", type=float, default=0.55, help="불연속 화소 비율 문턱")
    ap.add_argument("--jump", type=int, default=3, help="불연속으로 볼 화소값 차이")
    ap.add_argument(
        "--lines", nargs="*", default=None,
        help="이음새 좌표 직접 지정. 예: sample_2:h499 sample_3:h263,v420. "
             "지정하면 자동 검출을 쓰지 않는다 — 자동 검출은 가로 글자 줄을 "
             "이음새로 오인하므로 좌표를 아는 경우 반드시 이쪽을 쓸 것",
    )
    args = ap.parse_args()

    manual: dict[str, tuple[list[int], list[int]]] = {}
    for spec in args.lines or []:
        stem, _, coords = spec.partition(":")
        ys, xs = [], []
        for tok in coords.split(","):
            tok = tok.strip()
            if tok[:1] == "h":
                ys.append(int(tok[1:]))
            elif tok[:1] == "v":
                xs.append(int(tok[1:]))
        manual[Path(stem).stem] = (sorted(ys), sorted(xs))

    (OUT_DIR / "vis").mkdir(parents=True, exist_ok=True)
    half = max(1, args.band // 2)
    found = {}

    for name in args.images:
        stem = Path(name).stem
        path = find_source(stem)
        img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]

        if stem in manual:
            ys, xs = manual[stem]
            src_kind = "수동 지정"
        else:
            ys = seam_lines(img, 0, args.min_frac, args.jump)
            xs = seam_lines(img, 1, args.min_frac, args.jump)
            src_kind = "자동 검출"

        mask = np.zeros((h, w), np.uint8)
        vis = img.copy()
        white = (img > 245).all(axis=2)
        for y in ys:
            mask[max(0, y - half):min(h, y + half + 1), :] = 255
            cv2.line(vis, (0, y), (w, y), (0, 0, 255), 2)
        for x in xs:
            mask[:, max(0, x - half):min(w, x + half + 1)] = 255
            cv2.line(vis, (x, 0), (x, h), (0, 255, 255), 2)
        # 흰 캔버스 여백은 지울 대상이 아니다 — 조각 안쪽만 남긴다
        mask[white] = 0

        cv2.imwrite(str(OUT_DIR / f"{stem}.png"), mask)
        cv2.imwrite(str(OUT_DIR / "vis" / f"{stem}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 92])
        found[stem] = {
            "source": src_kind,
            "h_lines_y": ys,
            "v_lines_x": xs,
            "covered_pct": round(float((mask > 0).mean() * 100), 2),
        }
        print(f"  {stem:<12} [{src_kind}] 가로 {ys} 세로 {xs}  마스크 {found[stem]['covered_pct']}%")

    meta = {
        "band_px": args.band,
        "min_frac": args.min_frac,
        "jump": args.jump,
        "note": "실서비스에서는 A(리플로우)가 이음새 좌표를 제공해야 함. 검출은 PoC 한정 보조 수단",
        "images": found,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 → {OUT_DIR}")


if __name__ == "__main__":
    main()
