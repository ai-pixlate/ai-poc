"""E1 추가 검증 — OpenAI images.edit (마스크 기반 인페인팅 API).

나노바나나와 범주가 다르다. 나노바나나는 마스크를 못 받는 **지시형 편집**이라
"어디를 지울지" 지정할 수 없었다. 이쪽은 **마스크를 받는** 표준 인페인팅 API다.

목적 [2026-08-20]: LaMa가 C를 받은 큰 마스크 케이스(4.jpg 47%, 9.jpg 32%)를
상용 API가 구제할 수 있는지 확인. E1 채택(LaMa)을 덮어쓰지 않는 추가 검증이다.

마스크 규약 주의
    우리 d15 마스크: 흰색(255) = 지울 곳
    OpenAI 규약    : **투명(alpha=0) = 편집할 곳**
    → 알파를 반전해서 넘긴다.

좌표 보존
    지원 출력 규격이 1024x1024 / 1536x1024 / 1024x1536뿐이라 원본 크기가 안 맞는다.
    E1 방법 C와 같이 **원본 크기로 되돌린 뒤 마스크 안쪽만 합성**한다.
    이러면 마스크 밖 픽셀이 원본과 동일해진다.

사용법
    python run_openai.py --image 4.jpg --model gpt-image-2
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
MASKS = HERE / "results" / "masks" / "d15"
OUT_BASE = HERE / "results"

# 출력 토큰 단가 (per 1M) — developers.openai.com/api/docs/pricing, 2026-08-20 확인
PRICE_OUT = {"gpt-image-1": 40.0, "gpt-image-1.5": 32.0, "gpt-image-2": 30.0}
PRICE_IN = {"gpt-image-1": 10.0, "gpt-image-1.5": 8.0, "gpt-image-2": 8.0}

PROMPT = (
    "Remove the text from the masked areas. Fill them with the surrounding background — "
    "match its color, gradient, lighting, and texture so the result looks seamless. "
    "Do NOT add any text, letters, words, numbers, symbols, or new objects."
)


def load_env() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="4.jpg")
    ap.add_argument("--model", default="gpt-image-2", choices=list(PRICE_OUT))
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--feather", type=int, default=5)
    args = ap.parse_args()

    stem = Path(args.image).stem
    img = cv2.imdecode(np.fromfile(str(IMAGES / args.image), np.uint8), cv2.IMREAD_COLOR)
    mask = cv2.imdecode(np.fromfile(str(MASKS / f"{stem}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    H, W = img.shape[:2]

    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 없음")

    from openai import OpenAI

    # 원본 → PNG
    img_png = cv2.imencode(".png", img)[1].tobytes()
    # 마스크 → RGBA, 지울 곳을 투명(alpha=0)으로. OpenAI 규약이 우리와 반대다.
    rgba = np.dstack([img, 255 - mask])
    mask_png = cv2.imencode(".png", rgba)[1].tobytes()

    client = OpenAI()
    print(f"[openai-edit] {args.model} · {args.quality} ← {args.image} {W}x{H}")
    print(f"  마스크 면적 {(mask > 0).mean() * 100:.1f}%")

    t0 = time.perf_counter()
    res = client.images.edit(
        model=args.model,
        image=("image.png", img_png, "image/png"),
        mask=("mask.png", mask_png, "image/png"),
        prompt=PROMPT,
        quality=args.quality,
    )
    sec = time.perf_counter() - t0

    b64 = res.data[0].b64_json
    if not b64:
        raise SystemExit("이미지 없음 — 응답 확인 필요")
    from PIL import Image

    raw = np.array(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"))
    raw = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
    model_size = (raw.shape[1], raw.shape[0])
    resized = cv2.resize(raw, (W, H), interpolation=cv2.INTER_AREA)

    # 마스크 안쪽만 합성 — 바깥은 원본 픽셀 유지 (좌표·내용 보존)
    k = args.feather | 1
    alpha = (cv2.GaussianBlur(mask, (k, k), 0).astype(np.float32) / 255.0)[..., None]
    result = (resized * alpha + img * (1 - alpha)).astype(np.uint8)

    out_dir = OUT_BASE / f"openai_{args.model}_{args.quality}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_dir / f"{stem}.jpg"), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(str(out_dir / f"{stem}_raw.jpg"), resized, [cv2.IMWRITE_JPEG_QUALITY, 95])

    u = getattr(res, "usage", None)
    ti = getattr(u, "input_tokens", 0) if u else 0
    to = getattr(u, "output_tokens", 0) if u else 0
    cost = ti / 1e6 * PRICE_IN[args.model] + to / 1e6 * PRICE_OUT[args.model]

    meta = {"model": args.model, "quality": args.quality, "image": args.image,
            "src_size": [W, H], "model_output_size": list(model_size),
            "mask_pct": round(float((mask > 0).mean() * 100), 2),
            "input_tokens": ti, "output_tokens": to, "cost_usd": round(cost, 4),
            "sec": round(sec, 1), "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / f"{stem}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    print(f"  소요 {sec:.1f}s · 모델 출력 {model_size[0]}x{model_size[1]} → 리사이즈 {W}x{H}")
    print(f"  토큰 입력 {ti:,} 출력 {to:,} · 비용 {cost:.4f}$")
    print(f"  저장 {out_dir / f'{stem}.jpg'} (합성본) · {stem}_raw.jpg (모델 원출력)")


if __name__ == "__main__":
    main()
