"""E1. 원문 지우기 — 인페인팅 실행기.

사용법
    python run.py --variant telea
    python run.py --variant all --images 1.jpg 5.jpg
    python run.py --variant telea --mask-tag d25

출력
    results/{variant}/{stem}.jpg        지운 결과
    results/{variant}/meta.json         실행 조건·소요시간

OpenCV 고전 인페인팅(Telea/NS)은 주변 화소를 확산시켜 메우는 방식이라
단색·완만한 그라데이션에는 통하지만 질감이 있는 사진은 뭉갠다.
문서상 단색 배경용 baseline 위치이며, 사진 배경 판정은 LaMa가 맡는다.
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

# LaMa는 별도 venv에 있다. iopaint가 numpy를 1.x로 내리고 opencv-python을 끌어와
# B(paddle) 환경과 충돌하므로 섞지 않는다. 여기서는 실행 파일만 호출한다.
IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"

# SD 계열 공통 네거티브 프롬프트. 1차 실행에서 가짜 글자·무늬가 생겨 억제 대상을 넓혔다.
_SD_NEG = (
    "text, letters, words, characters, typography, writing, watermark, "
    "signature, logo, label, symbols, pattern, texture"
)

# 1차 실행(guidance 7.5 / steps 50 / Crop)에서 SD 2종이 모두 가짜 글자를 생성했다.
# 보수적 설정의 근거:
#   sd_guidance_scale 낮춤  — 빈 프롬프트에서 guidance가 높으면 생성 욕구가 증폭된다
#   sd_steps 줄임           — 스텝이 많을수록 디테일을 정교하게 지어낸다. 지우기엔 뭉툭한 편이 낫다
#   sd_match_histograms     — 결과 색분포를 원본에 맞춰 톤 어긋남을 줄인다
_CONSERVATIVE = {
    "prompt": "",
    "negative_prompt": _SD_NEG,
    "sd_steps": 20,
    "sd_guidance_scale": 1.5,
    "sd_match_histograms": True,
    "sd_seed": 42,
}

VARIANTS: dict[str, dict] = {
    "telea": {"engine": "opencv", "flag": cv2.INPAINT_TELEA, "radius": 3},
    "ns": {"engine": "opencv", "flag": cv2.INPAINT_NS, "radius": 3},
    "lama": {"engine": "iopaint", "model": "lama", "device": "cpu"},
    # 마스크 팽창 폭만 바꾼 비교군. d15에서 LaMa가 C를 받은 4.jpg(마스크 47%)·9.jpg(32%)가
    # 마스크 과대 때문인지 확인한다. 나머지 조건은 lama와 동일.
    "lama_d10": {"engine": "iopaint", "model": "lama", "device": "cpu", "mask_tag": "d10"},
    # 장치만 바꾼 비교군. 결과는 lama와 같아야 하며 소요시간 측정이 목적.
    "lama_gpu": {"engine": "iopaint", "model": "lama", "device": "cuda"},
    # SD는 생성 모델이라 지운 자리에 없던 내용을 만들어 넣는다. 글자를 지우랬더니
    # 가짜 글자·무늬를 그리는 실패가 흔하므로 판정 때 그것도 같이 봐야 한다.
    # 빈 프롬프트로 두면 "주변과 이어지는 무언가"를 채우는 쪽으로 동작한다.
    "sd15": {
        "engine": "iopaint",
        "model": "runwayml/stable-diffusion-inpainting",
        "device": "cuda",
    },
    # PowerPaint는 과업을 지정할 수 있고 그중 object-remove가 "지우고 배경으로 메우기"에
    # 맞춰 학습돼 있다. sd15가 빈 프롬프트로 가짜 글자를 그려 넣은 실패를 겨냥한 후보.
    "powerpaint_remove": {
        "engine": "iopaint",
        "model": "Sanster/PowerPaint-V1-stable-diffusion-inpainting",
        "device": "cuda",
        "driver": True,  # iopaint run 배치 경로의 disable_nsfw 버그 우회
        "config": {
            "powerpaint_task": "object-remove",
            "prompt": "",
            "negative_prompt": "text, letters, watermark, writing, signature",
            "sd_steps": 50,
            "sd_guidance_scale": 7.5,
            "sd_seed": 42,
        },
    },
    # --- 2차: 보수적 설정 튜닝 ---
    "pp_conservative": {
        "engine": "iopaint",
        "model": "Sanster/PowerPaint-V1-stable-diffusion-inpainting",
        "device": "cuda",
        "driver": True,
        "config": {**_CONSERVATIVE, "powerpaint_task": "object-remove"},
    },
    # hd_strategy 기본값 Crop은 마스크 주변 128px만 잘라 모델에 넣는다. 마스크가 크면
    # 모델이 보는 것이 거의 전부 마스크라 채울 단서가 없어 지어낸다. Original은 자르지
    # 않고 이미지 전체를 한 번에 넣어 문맥을 준다.
    #
    # 주의: 처음에 Resize로 걸었더니 Crop과 결과가 바이트 단위로 같았다. Resize 분기는
    # 긴 변이 hd_strategy_resize_limit(1280)을 넘을 때만 발동하는데 표본이 1000~1280px라
    # 조건에 미달해 아무 일도 하지 않았다(base.py __call__). 문맥을 넓히려면 Original이다.
    "pp_fullctx": {
        "engine": "iopaint",
        "model": "Sanster/PowerPaint-V1-stable-diffusion-inpainting",
        "device": "cuda",
        "driver": True,
        "config": {**_CONSERVATIVE, "powerpaint_task": "object-remove", "hd_strategy": "Original"},
    },
    "sd15_conservative": {
        "engine": "iopaint",
        "model": "runwayml/stable-diffusion-inpainting",
        "device": "cuda",
        "config": {**_CONSERVATIVE, "hd_strategy": "Resize"},
    },
}


def find_source(stem: str) -> Path:
    for ext in (".jpg", ".jpeg", ".png"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"원본 못 찾음: {stem}")


def run_iopaint(spec: dict, masks: list[Path], out_dir: Path) -> list[dict]:
    """iopaint CLI를 별도 venv에서 호출한다. 원본·마스크를 임시 폴더에 모아 배치로 넘긴다."""
    if not IOPAINT.exists():
        raise SystemExit(f"iopaint 없음: {IOPAINT}\n  python -m venv .venv-e1 후 pip install iopaint")

    tmp = Path(tempfile.mkdtemp(prefix="e1_"))
    try:
        img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
        for d in (img_dir, msk_dir, res_dir):
            d.mkdir()
        for mp in masks:
            src = find_source(mp.stem)
            shutil.copy2(src, img_dir / f"{mp.stem}{src.suffix}")
            shutil.copy2(mp, msk_dir / f"{mp.stem}.png")

        # 세부 설정(powerpaint_task·프롬프트·steps 등)은 CLI 플래그가 없고 config JSON으로만 받는다.
        cfg = None
        if spec.get("config"):
            cfg = tmp / "config.json"
            cfg.write_text(json.dumps(spec["config"], ensure_ascii=False), encoding="utf-8")

        if spec.get("driver"):
            # iopaint run은 ModelManager에 disable_nsfw를 안 넘겨 PowerPaint가 죽는다.
            # 같은 일을 하는 최소 드라이버를 .venv-e1 인터프리터로 직접 돌린다.
            cmd = [str(IOPAINT.parent / "python.exe"), str(HERE / "_iopaint_driver.py"),
                   spec["model"], spec["device"], str(img_dir), str(msk_dir), str(res_dir)]
            if cfg:
                cmd.append(str(cfg))
        else:
            cmd = [
                str(IOPAINT), "run",
                f"--model={spec['model']}",
                f"--device={spec['device']}",
                f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}",
            ]
            if cfg:
                cmd.append(f"--config={cfg}")
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            raise SystemExit(f"iopaint 실패 (exit {proc.returncode})\n{proc.stderr[-2000:]}")

        # iopaint는 png로 내보낸다. 다른 variant와 맞추려고 jpg로 통일한다.
        per_image, produced = [], sorted(res_dir.glob("*.*"))
        if not produced:
            raise SystemExit(f"iopaint 산출물 없음\n{proc.stdout[-2000:]}")
        for p in produced:
            img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out_dir / f"{p.stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            per_image.append({"image": find_source(p.stem).name, "sec": round(elapsed / len(produced), 2)})
            print(f"  {p.stem:<10} 완료")
        print(f"  (배치 {len(produced)}장 총 {elapsed:.1f}s — 장당 시간은 평균값)")
        return per_image
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_variant(name: str, mask_tag: str, stems: list[str] | None) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}, all")

    spec = VARIANTS[name]
    # variant가 마스크를 못박아 두면 그쪽이 우선한다. 팽창 폭만 다른 비교군을
    # 별도 결과 폴더로 남기기 위한 것 — 같은 폴더에 쓰면 판정 근거가 덮어써진다.
    mask_tag = spec.get("mask_tag", mask_tag)
    mask_dir = RESULTS / "masks" / mask_tag
    if not (mask_dir / "meta.json").exists():
        raise SystemExit(f"마스크 없음: {mask_dir}. make_mask.py 먼저 실행")

    out_dir = RESULTS / name
    out_dir.mkdir(parents=True, exist_ok=True)

    masks = sorted(mask_dir.glob("*.png"), key=lambda p: (len(p.stem), p.stem))
    if stems:
        masks = [m for m in masks if m.stem in stems]
    if not masks:
        raise SystemExit(f"{mask_dir} 에 대상 마스크 없음")

    params = {k: v for k, v in spec.items() if k not in {"engine", "flag", "driver"}}
    print(f"[{name}] engine={spec['engine']} {params} mask={mask_tag}")

    if spec["engine"] == "iopaint":
        per_image = run_iopaint(spec, masks, out_dir)
    else:
        per_image = []
        for mp in masks:
            img_path = find_source(mp.stem)
            img = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_COLOR)
            mask = cv2.imdecode(np.fromfile(str(mp), np.uint8), cv2.IMREAD_GRAYSCALE)

            t0 = time.perf_counter()
            out = cv2.inpaint(img, mask, spec["radius"], spec["flag"])
            elapsed = time.perf_counter() - t0

            cv2.imwrite(str(out_dir / f"{mp.stem}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
            per_image.append({"image": img_path.name, "sec": round(elapsed, 2)})
            print(f"  {img_path.name:<10} {elapsed:>6.2f}s")

    meta = {
        "variant": name,
        "engine": spec["engine"],
        "mask_tag": mask_tag,
        "params": params,
        "images": len(masks),
        "total_sec": round(sum(p["sec"] for p in per_image), 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] 완료 — {len(masks)}장, {meta['total_sec']}s\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--mask-tag", default="d15")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    stems = [Path(n).stem for n in args.images] if args.images else None
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for name in names:
        run_variant(name, args.mask_tag, stems)


if __name__ == "__main__":
    main()
