"""F. 배경 가공 — 여백 채우기.

사용법
    python run_gap.py --variant all --images sample_1 sample_2 sample_3

입력
    data/images/{stem}.PNG            조각을 이어붙인 결과
    results/gap_masks/{stem}.png      채울 영역 (make_gap_mask.py 산출)

출력
    results/gap_{variant}/{stem}.jpg

마스크가 화면의 절반 가까이 된다. E1(원문 지우기)에서 LaMa가 무너졌던 조건이지만
성격이 다르다 — 여기서 채울 것은 잃어버린 질감이 아니라 **조각 가장자리 배경의
연장**이다. 그래서 주변 색을 퍼뜨리는 고전 기법이 오히려 유리할 수 있다.
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
MASKS = RESULTS / "gap_masks"
IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"

# SD 공통 설정. E1 2차 튜닝에서 쓴 보수적 값 그대로 — guidance를 낮추고 스텝을
# 줄여 생성 욕구를 억제한다. 글자 생성을 네거티브로 막는다.
_SD_BASE = {
    "prompt": "",
    "negative_prompt": ("text, letters, words, characters, typography, writing, "
                        "watermark, signature, logo, label, symbols"),
    "sd_steps": 20,
    "sd_guidance_scale": 1.5,
    "sd_match_histograms": True,
    "sd_seed": 42,
}

VARIANTS: dict[str, dict] = {
    "lama": {"kind": "lama", "device": "cuda"},
    "telea": {"kind": "cv2", "flag": cv2.INPAINT_TELEA, "radius": 7},
    "ns": {"kind": "cv2", "flag": cv2.INPAINT_NS, "radius": 7},
    # 가장 가까운 조각 화소로 채운 뒤 크게 흐린다. 질감은 못 살리지만
    # 배경이 단색·완만한 그라데이션이면 경계가 가장 매끄럽게 이어진다.
    "extend": {"kind": "extend", "blur": 61},
    # SD 계열. E1에서는 주변이 온통 글자라 가짜 글자를 생성해 탈락했지만,
    # 여백 채우기는 경계가 대부분 민민한 배경이라 조건이 다르다.
    "sd15": {
        "kind": "iopaint", "model": "runwayml/stable-diffusion-inpainting", "device": "cuda",
        "config": {**_SD_BASE},
    },
    # context-aware = 프롬프트 없이 주변 문맥으로 채우는 모드. 배경 연장에 맞다.
    "pp_context": {
        "kind": "iopaint", "model": "Sanster/PowerPaint-V1-stable-diffusion-inpainting",
        "device": "cuda", "driver": True,
        "config": {**_SD_BASE, "powerpaint_task": "context-aware"},
    },
}


def find_source(stem: str) -> Path:
    for ext in (".png", ".PNG", ".jpg", ".jpeg"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"원본 못 찾음: {stem}")


def apply_extend(img: np.ndarray, mask: np.ndarray, blur: int) -> np.ndarray:
    """마스크 안을 가장 가까운 조각 화소로 채우고 흐려서 이음을 지운다."""
    src = (mask > 0).astype(np.uint8)          # 0 = 조각(채우기 기준), 1 = 채울 곳
    _, labels = cv2.distanceTransformWithLabels(
        src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    # 라벨 → 좌표 대응표. 라벨은 가장 가까운 0화소마다 붙는다.
    ys, xs = np.where(src == 0)
    lut_y = np.zeros(labels.max() + 1, np.int32)
    lut_x = np.zeros(labels.max() + 1, np.int32)
    lut_y[labels[ys, xs]] = ys
    lut_x[labels[ys, xs]] = xs

    filled = img.copy()
    m = mask > 0
    filled[m] = img[lut_y[labels[m]], lut_x[labels[m]]]

    k = blur | 1
    smooth = cv2.GaussianBlur(filled, (k, k), 0)
    # 조각은 원본 그대로 두고, 채운 영역만 흐린 값으로. 경계는 알파로 이어붙인다.
    alpha = (cv2.GaussianBlur((m * 255).astype(np.uint8), (k, k), 0).astype(np.float32) / 255.0)[..., None]
    return (smooth * alpha + img * (1 - alpha)).astype(np.uint8)


def run_iopaint(spec: dict, jobs: list[tuple[str, np.ndarray, np.ndarray]], out_dir: Path) -> float:
    if not IOPAINT.exists():
        raise SystemExit(f"iopaint 없음: {IOPAINT}")
    tmp = Path(tempfile.mkdtemp(prefix="fgap_"))
    try:
        img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
        for d in (img_dir, msk_dir, res_dir):
            d.mkdir()
        for stem, img, msk in jobs:
            cv2.imwrite(str(img_dir / f"{stem}.png"), img)
            cv2.imwrite(str(msk_dir / f"{stem}.png"), msk)

        cfg = None
        if spec.get("config"):
            cfg = tmp / "config.json"
            cfg.write_text(json.dumps(spec["config"], ensure_ascii=False), encoding="utf-8")

        model = spec.get("model", "lama")
        if spec.get("driver"):
            # iopaint run이 ModelManager에 disable_nsfw를 안 넘겨 PowerPaint가 죽는다.
            # E1에서 만든 드라이버를 재사용한다.
            driver = ROOT / "poc" / "E1_inpaint" / "_iopaint_driver.py"
            cmd = [str(IOPAINT.parent / "python.exe"), str(driver),
                   model, spec["device"], str(img_dir), str(msk_dir), str(res_dir)]
            if cfg:
                cmd.append(str(cfg))
        else:
            cmd = [str(IOPAINT), "run", f"--model={model}", f"--device={spec['device']}",
                   f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}"]
            if cfg:
                cmd.append(f"--config={cfg}")

        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
    out_dir = RESULTS / f"gap_{name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[gap_{name}] {spec}")
    per_image, jobs = [], []
    for stem in stems:
        img = cv2.imdecode(np.fromfile(str(find_source(stem)), np.uint8), cv2.IMREAD_COLOR)
        mp = MASKS / f"{stem}.png"
        if not mp.exists():
            raise SystemExit(f"여백 마스크 없음: {mp}. make_gap_mask.py 먼저 실행")
        mask = cv2.imdecode(np.fromfile(str(mp), np.uint8), cv2.IMREAD_GRAYSCALE)

        if spec["kind"] in ("lama", "iopaint"):
            jobs.append((stem, img, mask))
            continue

        t0 = time.perf_counter()
        if spec["kind"] == "cv2":
            out = cv2.inpaint(img, mask, spec["radius"], spec["flag"])
        else:
            out = apply_extend(img, mask, spec["blur"])
        elapsed = time.perf_counter() - t0

        cv2.imwrite(str(out_dir / f"{stem}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        per_image.append({"image": stem, "sec": round(elapsed, 2)})
        print(f"  {stem:<12} {elapsed:>6.2f}s")

    if jobs:
        el = run_iopaint(spec, jobs, out_dir)
        per_image = [{"image": s, "sec": round(el / len(jobs), 2)} for s, _, _ in jobs]

    meta = {"variant": f"gap_{name}", "spec": {k: v for k, v in spec.items() if k != "flag"},
            "mask_source": "results/gap_masks", "images": len(per_image),
            "total_sec": round(sum(p["sec"] for p in per_image), 2),
            "per_image": per_image, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[gap_{name}] 완료 — {len(per_image)}장, {meta['total_sec']}s\n")


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
