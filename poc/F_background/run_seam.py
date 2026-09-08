"""F. 배경 가공 — 조각 이음새 제거.

사용법
    python run_seam.py --variant all --images sample_2

입력
    data/images/{stem}.PNG                  조각을 이어붙인 결과
    results/seam_masks/{stem}.png           이음새 띠 (make_seam_mask.py 산출)

출력
    results/seam_{variant}/{stem}.jpg
    results/seam_{variant}/meta.json

E1 잔여 자국을 다루는 run.py와 분리했다. 입력이 E1 결과가 아니라 합성 이미지고,
마스크 출처와 기법이 달라 한 파일에 섞으면 조건이 헷갈린다.
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
RESULTS = HERE / "results"
MASKS = RESULTS / "seam_masks"
IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"

VARIANTS: dict[str, dict] = {
    # E1 재활용 — 이음새 띠를 지우고 LaMa가 양쪽을 이어 복원한다
    "lama": {"kind": "lama", "device": "cuda"},
    # 띠 안에서만 가우시안 블러. 선을 뭉개 없앤다
    "blur": {"kind": "blur", "ksize": 21},
    # 띠 위/아래 경계 행을 선형 보간해 채운다. 색이 매끄럽게 이어진다
    "blend": {"kind": "blend"},
}


def find_source(stem: str) -> Path:
    for ext in (".png", ".PNG", ".jpg", ".jpeg"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"원본 못 찾음: {stem}")


def apply_blur(img: np.ndarray, mask: np.ndarray, k: int) -> np.ndarray:
    k |= 1
    blurred = cv2.GaussianBlur(img, (k, k), 0)
    # 띠 경계에서 갑자기 바뀌지 않도록 마스크 자체를 흐려 알파로 쓴다
    alpha = (cv2.GaussianBlur(mask, (k, k), 0).astype(np.float32) / 255.0)[..., None]
    return (blurred * alpha + img * (1 - alpha)).astype(np.uint8)


def apply_blend(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """띠를 위/아래(또는 좌/우) 경계 화소의 선형 보간으로 채운다."""
    out = img.copy().astype(np.float32)
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if w >= h:  # 가로 띠 — 위아래를 잇는다
            top, bot = y - 1, y + h
            if top < 0 or bot >= img.shape[0]:
                continue
            a = img[top].astype(np.float32)
            b = img[bot].astype(np.float32)
            for r in range(h):
                t = (r + 1) / (h + 1)
                row = a * (1 - t) + b * t
                sel = labels[y + r] == i
                out[y + r][sel] = row[sel]
        else:      # 세로 띠 — 좌우를 잇는다
            left, right = x - 1, x + w
            if left < 0 or right >= img.shape[1]:
                continue
            a = img[:, left].astype(np.float32)
            b = img[:, right].astype(np.float32)
            for c in range(w):
                t = (c + 1) / (w + 1)
                col = a * (1 - t) + b * t
                sel = labels[:, x + c] == i
                out[:, x + c][sel] = col[sel]
    return out.astype(np.uint8)


def run_lama(spec: dict, jobs: list[tuple[str, np.ndarray, np.ndarray]], out_dir: Path) -> float:
    if not IOPAINT.exists():
        raise SystemExit(f"iopaint 없음: {IOPAINT}")
    tmp = Path(tempfile.mkdtemp(prefix="fseam_"))
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
        for p in sorted(res_dir.glob("*.*")):
            res = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out_dir / f"{p.stem}.jpg"), res, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  {p.stem:<12} 완료")
        return elapsed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_variant(name: str, stems: list[str]) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}, all")
    spec = VARIANTS[name]
    out_dir = RESULTS / f"seam_{name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[seam_{name}] {spec}")
    per_image, jobs = [], []
    for stem in stems:
        img = cv2.imdecode(np.fromfile(str(find_source(stem)), np.uint8), cv2.IMREAD_COLOR)
        mp = MASKS / f"{stem}.png"
        if not mp.exists():
            raise SystemExit(f"이음새 마스크 없음: {mp}. make_seam_mask.py 먼저 실행")
        mask = cv2.imdecode(np.fromfile(str(mp), np.uint8), cv2.IMREAD_GRAYSCALE)

        if spec["kind"] == "lama":
            jobs.append((stem, img, mask))
            continue

        t0 = time.perf_counter()
        out = apply_blur(img, mask, spec["ksize"]) if spec["kind"] == "blur" else apply_blend(img, mask)
        elapsed = time.perf_counter() - t0
        cv2.imwrite(str(out_dir / f"{stem}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        per_image.append({"image": stem, "sec": round(elapsed, 2)})
        print(f"  {stem:<12} {elapsed:>6.2f}s")

    if jobs:
        el = run_lama(spec, jobs, out_dir)
        per_image = [{"image": s, "sec": round(el / len(jobs), 2)} for s, _, _ in jobs]

    meta = {
        "variant": f"seam_{name}",
        "spec": spec,
        "mask_source": "results/seam_masks",
        "images": len(per_image),
        "total_sec": round(sum(p["sec"] for p in per_image), 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[seam_{name}] 완료 — {len(per_image)}장, {meta['total_sec']}s\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="+", required=True)
    args = ap.parse_args()
    stems = [Path(n).stem for n in args.images]
    for name in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        run_variant(name, stems)


if __name__ == "__main__":
    main()
