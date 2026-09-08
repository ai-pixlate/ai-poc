"""G. 제품컷 누끼 — variant 실행기.

사용법
    python run.py --variant rembg_u2net --images 12.jpg
    python run.py --variant all

출력
    results/{variant}/rgba/{stem}.png    투명 PNG (알파 채널)
    results/{variant}/mask/{stem}.png    마스크 (흑백)
    results/{variant}/vis/{stem}.jpg     체크무늬 배경에 얹은 확인용
    results/{variant}/meta.json

투명 PNG와 마스크를 **둘 다** 저장한다 (2026-08-20 결정).
    투명 PNG — 재배치·합성에 바로 사용
    마스크   — 다른 단계 입력으로 전달

⚠️ 이 과업의 대상은 **제품컷만**이다. 범용 배경제거 모델은 인물·소품까지
   전경 전체를 따내므로, 결과에 제품 외의 것이 섞이는지 반드시 확인할 것.
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
RESULTS = HERE / "results"

VARIANTS: dict[str, dict] = {
    # rembg 기본 모델. salient object detection 계열 — "가장 눈에 띄는 물체 하나"를
    # 찾도록 학습됐다. 12.jpg에서 인물만 따고 제품을 통째로 놓쳤다(2026-08-20).
    "rembg_u2net": {"engine": "rembg", "model": "u2net"},
    # 다중 객체·복잡 장면에 u2net보다 낫다고 알려진 모델
    "rembg_isnet": {"engine": "rembg", "model": "isnet-general-use"},
    # 최신 계열. 경계 정밀도가 높다고 알려짐. 12장 실행 결과 제품이 있고 인물이
    # 없는 이미지에서는 우수했으나, 인물이 있으면 인물이 지배하고 제품이 없으면
    # 텍스트를 전경으로 잡았다(2026-08-20).
    "rembg_birefnet": {"engine": "rembg", "model": "birefnet-general"},
    # DIS(dichotomous image segmentation) 특화. 인물보다 **사물** 분리에 초점이
    # 맞춰진 계열이라 "인물이 지배한다" 문제에 직접 대응할 여지가 있다.
    "rembg_birefnet_dis": {"engine": "rembg", "model": "birefnet-dis"},
}


def image_paths(names: list[str] | None) -> list[Path]:
    if names:
        return [IMAGES / n for n in names]
    return sorted(
        (p for p in IMAGES.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}),
        key=lambda p: (len(p.stem), p.stem),
    )


def checkerboard(h: int, w: int, size: int = 16) -> np.ndarray:
    """투명 영역을 눈으로 확인하기 위한 체크무늬 배경."""
    board = np.zeros((h, w, 3), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    board[...] = np.where((((yy // size) + (xx // size)) % 2)[..., None], 210, 245)
    return board


def visualize(rgba: np.ndarray) -> np.ndarray:
    """알파를 체크무늬에 합성. 경계 품질과 잔여 배경이 드러난다."""
    h, w = rgba.shape[:2]
    bg = checkerboard(h, w)
    a = (rgba[:, :, 3:4].astype(np.float32) / 255.0)
    return (rgba[:, :, :3] * a + bg * (1 - a)).astype(np.uint8)


def run_rembg(spec: dict, paths: list[Path], out: Path) -> list[dict]:
    from rembg import new_session, remove
    from PIL import Image
    import io

    session = new_session(spec["model"])
    rows = []
    for p in paths:
        raw = p.read_bytes()
        t0 = time.perf_counter()
        out_bytes = remove(raw, session=session)
        elapsed = time.perf_counter() - t0

        rgba = np.array(Image.open(io.BytesIO(out_bytes)).convert("RGBA"))
        rgba = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        alpha = rgba[:, :, 3]

        cv2.imwrite(str(out / "rgba" / f"{p.stem}.png"), rgba)
        cv2.imwrite(str(out / "mask" / f"{p.stem}.png"), alpha)
        cv2.imwrite(str(out / "vis" / f"{p.stem}.jpg"), visualize(rgba),
                    [cv2.IMWRITE_JPEG_QUALITY, 92])

        cover = float((alpha > 127).mean() * 100)
        n_comp = cv2.connectedComponents((alpha > 127).astype(np.uint8))[0] - 1
        rows.append({"image": p.name, "sec": round(elapsed, 2),
                     "foreground_pct": round(cover, 1), "components": n_comp})
        print(f"  {p.name:<10} {elapsed:>6.2f}s  전경 {cover:>5.1f}%  덩어리 {n_comp}개")
    return rows


def run_variant(name: str, paths: list[Path]) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}, all")
    spec = VARIANTS[name]
    out = RESULTS / name
    for sub in ("rgba", "mask", "vis"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    print(f"[{name}] {spec}")
    rows = run_rembg(spec, paths, out)

    meta = {"variant": name, "spec": spec, "images": len(rows),
            "total_sec": round(sum(r["sec"] for r in rows), 2),
            "per_image": rows, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] 완료 — {len(rows)}장, {meta['total_sec']}s\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    paths = image_paths(args.images)
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"이미지 없음: {missing}")

    for name in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        run_variant(name, paths)


if __name__ == "__main__":
    main()
