"""F. 배경 가공 — 나노바나나로 여백 채우기.

E1과 조건이 다르다. E1은 글자에 **가려진 원본 질감**을 복원하는 일이라 정답이
존재했고 생성 모델이 불리했다. 여백 채우기는 **없던 배경을 새로 만드는** 일이라
정답이 없고 그럴듯하면 되므로 생성 모델에 유리할 수 있다.

설계 — E1 방법 C의 아이디어를 전체 이미지에 적용
    1. 전체 이미지 + 문장 지시로 여백을 채우게 한다
    2. 출력(모델 자체 격자, 보통 1024)을 원본 크기로 리사이즈
    3. **여백 마스크 안쪽만 합성** — 조각 영역은 원본 픽셀을 그대로 둔다

3번이 핵심이다. 조각을 원본으로 유지하면 E1에서 문제였던 "전체 재생성"이
사라지고, 리사이즈 손실도 평탄한 여백에만 걸려 티가 덜 난다.

사용법
    python run_nano_gap.py --image sample_3 --model flash
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
MASKS = HERE / "results" / "gap_masks"
OUT_BASE = HERE / "results"

MODELS = {"flash": ("gemini-2.5-flash-image", 0.039),
          "pro": ("gemini-3-pro-image", 0.134)}

PROMPTS = {
    # v1 — 1차 시험(flash). 모델이 여백을 채우지 않고 조각만 다시 그렸다.
    "v1": (
        "This image is a product detail page composed of image fragments placed on a white canvas. "
        "Fill the empty white areas so they blend naturally with the background of the adjacent "
        "fragments — extend their color, gradient, and lighting outward. "
        "Make the boundary between the fragments and the filled areas seamless. "
        "Do NOT add any text, letters, words, logos, people, or new objects. "
        "Do NOT change the existing fragments — keep their content exactly as it is."
    ),
    # v2 — 과업을 outpainting으로 규정하고, 흰 영역의 위치와 채울 내용을 명시한다.
    # v1이 실패한 이유는 "여백을 채운다"를 편집 요청으로 읽고 조각을 손댄 것으로 보인다.
    "v2": (
        "This is a webpage screenshot. Several product photos (fragments) are placed on a plain "
        "WHITE background canvas, leaving large EMPTY WHITE REGIONS around and between them — "
        "along the left edge, the right edge, the top, the bottom, and in the gaps between fragments.\n\n"
        "Your task is OUTPAINTING. Extend the background of each fragment outward so that it fills "
        "ALL of those white regions. When you are done there must be NO white areas left anywhere "
        "on the canvas — the entire canvas should be one continuous background.\n\n"
        "Rules:\n"
        "- The fragments have soft pink and peach gradient backgrounds. Continue those exact colors "
        "and gradients outward into the white regions.\n"
        "- Make the seam between each fragment and the newly filled area invisible.\n"
        "- Do NOT add any text, letters, words, numbers, logos, people, or new objects anywhere.\n"
        "- Do NOT modify the fragments themselves. Their photos, products, and text must stay "
        "pixel-identical to the input."
    ),
}


def load_env() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def find_source(stem: str) -> Path:
    for ext in (".png", ".PNG", ".jpg", ".jpeg"):
        p = IMAGES / f"{stem}{ext}"
        if p.exists():
            return p
    raise SystemExit(f"원본 못 찾음: {stem}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="sample_3")
    ap.add_argument("--model", default="flash", choices=list(MODELS))
    ap.add_argument("--feather", type=int, default=9, help="합성 경계 페더링 px")
    ap.add_argument("--prompt", default="v2", choices=list(PROMPTS))
    args = ap.parse_args()
    model_id, price = MODELS[args.model]
    prompt = PROMPTS[args.prompt]

    stem = Path(args.image).stem
    src_path = find_source(stem)
    img = cv2.imdecode(np.fromfile(str(src_path), np.uint8), cv2.IMREAD_COLOR)
    mask = cv2.imdecode(np.fromfile(str(MASKS / f"{stem}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    H, W = img.shape[:2]

    load_env()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY 없음")

    from google import genai
    from PIL import Image

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    print(f"[nano-gap] {model_id} · 프롬프트 {args.prompt} ← {src_path.name} {W}x{H}  (장당 {price}$)")
    print(f"  마스크 면적 {(mask > 0).mean() * 100:.1f}%")

    buf = cv2.imencode(".png", img)[1].tobytes()
    t0 = time.perf_counter()
    res = client.interactions.create(
        model=model_id,
        input=[{"type": "text", "text": prompt},
               {"type": "image", "data": base64.b64encode(buf).decode(),
                "mime_type": "image/png"}],
    )
    sec = time.perf_counter() - t0

    out_img = getattr(res, "output_image", None)
    if out_img is None or not getattr(out_img, "data", None):
        txt = getattr(res, "output_text", None)
        raise SystemExit(f"이미지 출력 없음 — 거부 가능성. 텍스트: {str(txt)[:300]}")

    raw = np.array(Image.open(io.BytesIO(base64.b64decode(out_img.data))).convert("RGB"))
    raw = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
    model_size = (raw.shape[1], raw.shape[0])
    resized = cv2.resize(raw, (W, H), interpolation=cv2.INTER_AREA)

    # 여백 마스크 안쪽만 합성. 조각은 원본 픽셀을 그대로 둔다.
    k = args.feather | 1
    alpha = (cv2.GaussianBlur(mask, (k, k), 0).astype(np.float32) / 255.0)[..., None]
    result = (resized * alpha + img * (1 - alpha)).astype(np.uint8)

    out_dir = OUT_BASE / f"gap_nano_{args.model}_{args.prompt}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_dir / f"{stem}.jpg"), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    # 합성 전 모델 원출력도 남긴다 — 무엇이 합성으로 걸러졌는지 확인용
    cv2.imwrite(str(out_dir / f"{stem}_raw.jpg"), resized, [cv2.IMWRITE_JPEG_QUALITY, 95])

    meta = {"model_id": model_id, "prompt_version": args.prompt, "image": src_path.name,
            "src_size": [W, H], "model_output_size": list(model_size),
            "mask_pct": round(float((mask > 0).mean() * 100), 2),
            "feather_px": args.feather, "sec": round(sec, 1), "cost_usd": price,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / f"{stem}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    print(f"  소요 {sec:.1f}s · 모델 출력 {model_size[0]}x{model_size[1]} → 리사이즈 {W}x{H}")
    print(f"  저장 {out_dir / f'{stem}.jpg'} (합성본) · {stem}_raw.jpg (모델 원출력)")


if __name__ == "__main__":
    main()
