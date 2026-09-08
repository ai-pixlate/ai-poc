"""F. 배경 가공 — E1 결과의 잔여 자국·경계 이음새·색 불연속 보정.

사용법
    python run.py --variant all
    python run.py --variant seamless --images 4.jpg 9.jpg

입력 (E1 종료 산출물을 그대로 받는다)
    data/images/{stem}.jpg                          원본
    poc/E1_inpaint/results/lama/{stem}.jpg          E1 결과 = F의 입력
    poc/E1_inpaint/results/masks/d15/{stem}.png     E1이 지운 영역

출력
    results/{variant}/{stem}.jpg
    results/{variant}/meta.json

변형 3종은 PoC 문서 2.5의 처리 유형 3가지에 1:1로 대응한다.
    ring_lama — 지운 자국 보정 (LaMa 재적용)
    seamless  — 색상·톤 정합 (OpenCV 색보정)
    feather   — 이음새 제거 (블러·블렌딩)

문서의 "조각 이음새"는 A(리플로우)로 조각을 이어붙인 결과가 있어야 하는데 A가
미착수라 입력이 없다. 대신 인페인팅 경계의 이음새를 대상으로 같은 기법을 본다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
E1 = ROOT / "poc" / "E1_inpaint" / "results"
SRC_VARIANT = "lama"      # E1 채택 기술
MASK_TAG = "d15"          # E1 판정이 이뤄진 마스크 조건
RESULTS = HERE / "results"

IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"

VARIANTS: dict[str, dict] = {
    # 1차 인페인팅 경계에 남은 띠를 2차로 지운다. 같은 마스크로 다시 돌리면 결과가
    # 같으므로(결정적), 경계만 남긴 링 마스크를 새 입력으로 준다 — 문서 6.7의
    # "E1 재활용을 다른 입력에 적용" 방침 그대로다.
    "ring_lama": {"kind": "lama_ring", "ring_px": 6, "device": "cuda"},
    # 포아송 블렌딩. 채워 넣은 영역의 색·톤을 주변에 맞춰 다시 이어붙인다.
    "seamless": {"kind": "seamless"},
    # 마스크 경계를 흐려 알파 혼합. 팽창 여유분 덕에 경계 바깥은 이미 배경이라
    # 원본을 되살려도 글자가 돌아오지 않는다.
    "feather": {"kind": "feather", "blur_px": 15},
}


def imread(p: Path, flag=cv2.IMREAD_COLOR):
    if not p.exists():
        return None
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def ring_mask(mask: np.ndarray, px: int) -> np.ndarray:
    """마스크 경계를 감싸는 띠. 안팎으로 px씩 넓힌 뒤 가운데를 뺀다."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.subtract(cv2.dilate(mask, k), cv2.erode(mask, k))


def apply_seamless(src: np.ndarray, base: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """E1이 채운 영역을 원본 위에 포아송 블렌딩으로 다시 얹는다.

    연결 요소마다 따로 처리한다. 전체를 한 번에 넘기면 중심점이 하나뿐이라
    떨어져 있는 영역들의 색 보정이 서로 끌려간다.
    """
    out = base.copy()
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 50 or w < 5 or h < 5:
            continue
        # seamlessClone은 ROI가 이미지 경계에 닿으면 실패한다. 1px 여유를 확인.
        if x < 1 or y < 1 or x + w > base.shape[1] - 1 or y + h > base.shape[0] - 1:
            continue
        comp = np.where(labels == i, 255, 0).astype(np.uint8)
        center = (x + w // 2, y + h // 2)
        try:
            out = cv2.seamlessClone(src, out, comp, center, cv2.NORMAL_CLONE)
        except cv2.error:
            continue  # 실패한 영역은 보정 없이 둔다
    return out


def apply_feather(src: np.ndarray, base: np.ndarray, mask: np.ndarray, blur_px: int) -> np.ndarray:
    k = blur_px | 1  # 홀수여야 한다
    alpha = (cv2.GaussianBlur(mask, (k, k), 0).astype(np.float32) / 255.0)[..., None]
    return (src * alpha + base * (1 - alpha)).astype(np.uint8)


def run_lama_ring(spec: dict, jobs: list[tuple[str, np.ndarray, np.ndarray]], out_dir: Path) -> list[dict]:
    """E1 결과 + 링 마스크를 LaMa에 다시 넣는다."""
    if not IOPAINT.exists():
        raise SystemExit(f"iopaint 없음: {IOPAINT}")
    tmp = Path(tempfile.mkdtemp(prefix="f_"))
    try:
        img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
        for d in (img_dir, msk_dir, res_dir):
            d.mkdir()
        for stem, img, msk in jobs:
            cv2.imwrite(str(img_dir / f"{stem}.png"), img)
            cv2.imwrite(str(msk_dir / f"{stem}.png"), msk)

        t0 = time.perf_counter()
        proc = subprocess.run(
            [str(IOPAINT), "run", "--model=lama", f"--device={spec['device']}",
             f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            raise SystemExit(f"iopaint 실패 (exit {proc.returncode})\n{proc.stderr[-2000:]}")

        produced = sorted(res_dir.glob("*.*"))
        per_image = []
        for p in produced:
            res = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out_dir / f"{p.stem}.jpg"), res, [cv2.IMWRITE_JPEG_QUALITY, 95])
            per_image.append({"image": f"{p.stem}.jpg", "sec": round(elapsed / max(len(produced), 1), 2)})
            print(f"  {p.stem:<10} 완료")
        print(f"  (배치 {len(produced)}장 총 {elapsed:.1f}s)")
        return per_image
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_variant(name: str, stems: list[str] | None) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}, all")
    spec = VARIANTS[name]
    out_dir = RESULTS / name
    out_dir.mkdir(parents=True, exist_ok=True)

    src_dir = E1 / SRC_VARIANT
    mask_dir = E1 / "masks" / MASK_TAG
    if not src_dir.exists():
        raise SystemExit(f"E1 결과 없음: {src_dir}")

    targets = sorted((p.stem for p in src_dir.glob("*.jpg")), key=lambda s: (len(s), s))
    if stems:
        targets = [t for t in targets if t in stems]
    if not targets:
        raise SystemExit("대상 없음")

    print(f"[{name}] {spec} — 입력 E1/{SRC_VARIANT}, 마스크 {MASK_TAG}")
    per_image, jobs = [], []
    for stem in targets:
        base = imread(IMAGES / f"{stem}.jpg")
        src = imread(src_dir / f"{stem}.jpg")
        mask = imread(mask_dir / f"{stem}.png", cv2.IMREAD_GRAYSCALE)
        if base is None or src is None or mask is None:
            print(f"  {stem}: 입력 누락, 건너뜀")
            continue

        if spec["kind"] == "lama_ring":
            jobs.append((stem, src, ring_mask(mask, spec["ring_px"])))
            continue

        t0 = time.perf_counter()
        if spec["kind"] == "seamless":
            out = apply_seamless(src, base, mask)
        else:
            out = apply_feather(src, base, mask, spec["blur_px"])
        elapsed = time.perf_counter() - t0

        cv2.imwrite(str(out_dir / f"{stem}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        per_image.append({"image": f"{stem}.jpg", "sec": round(elapsed, 2)})
        print(f"  {stem:<10} {elapsed:>6.2f}s")

    if jobs:
        per_image = run_lama_ring(spec, jobs, out_dir)

    meta = {
        "variant": name,
        "spec": spec,
        "source": f"poc/E1_inpaint/results/{SRC_VARIANT}",
        "mask_tag": MASK_TAG,
        "images": len(per_image),
        "total_sec": round(sum(p["sec"] for p in per_image), 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] 완료 — {len(per_image)}장, {meta['total_sec']}s\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()
    stems = [Path(n).stem for n in args.images] if args.images else None
    for name in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        run_variant(name, stems)


if __name__ == "__main__":
    main()
