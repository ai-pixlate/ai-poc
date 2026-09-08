"""E1 추가 검증 — 나노바나나(gemini-2.5-flash-image) 1장 시험.

목적은 품질 판정이 아니라 **배선·형태 확인**이다.
    - API 호출이 되는가
    - 출력 이미지 크기가 원본과 같은가  (E2 좌표 정합에 직결)
    - 사람이 있는 사진을 안전 필터가 거부하는가
    - 가짜 글자·내용을 만들어 넣는가  (SD 계열이 전부 여기서 탈락)

방법 A — 마스크 없이 전체 이미지 + 문장 지시.
나노바나나는 마스크를 받지 않으므로 기존 d15 마스크를 쓸 수 없다.

사용법
    python probe_nano.py --image 1.jpg
"""

from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
OUT_BASE = HERE / "results"

MODELS = {
    # 장당 단가 (ai.google.dev/gemini-api/docs/pricing, 2026-08-20 확인)
    "flash": ("gemini-2.5-flash-image", 0.039),
    "pro": ("gemini-3-pro-image", 0.134),   # 1K/2K 기준. 4K는 0.24$
}

# 지시문. E1의 판정 기준(문서 2.2)을 그대로 문장으로 옮겼다.
# 제품·인물 보존을 명시한 이유: 표본에 제품 인쇄 글자가 많아 그것까지 지우면
# 실서비스에서 쓸 수 없다(5.jpg는 38개 영역이 거의 전부 제품 글자).
PROMPT = (
    "Remove all Korean and English text overlays from this product detail page image. "
    "Fill the areas where text was removed so they blend naturally with the surrounding "
    "background — match the color, gradient, and texture. "
    "Do NOT add any new text, letters, words, or symbols. "
    "Do NOT change the products, people, objects, layout, or overall composition. "
    "Keep the image dimensions exactly the same. "
    "Text printed physically on product packaging should be left untouched."
)


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="1.jpg")
    ap.add_argument("--model", default="flash", choices=list(MODELS))
    args = ap.parse_args()
    model_id, price = MODELS[args.model]

    src = IMAGES / args.image
    if not src.exists():
        raise SystemExit(f"이미지 없음: {src}")

    load_env()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY 없음")

    from google import genai
    from PIL import Image

    before = Image.open(src).size
    data = base64.b64encode(src.read_bytes()).decode()

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    print(f"[nano] {model_id} ← {args.image} {before}  (장당 {price}$)")
    t0 = time.perf_counter()
    res = client.interactions.create(
        model=model_id,
        input=[
            {"type": "text", "text": PROMPT},
            {"type": "image", "data": data, "mime_type": "image/jpeg"},
        ],
    )
    sec = time.perf_counter() - t0

    img_out = getattr(res, "output_image", None)
    if img_out is None or not getattr(img_out, "data", None):
        print(f"  ⚠️ 이미지 없음 — 응답 필드: {[f for f in dir(res) if not f.startswith('_')][:20]}")
        txt = getattr(res, "output_text", None)
        if txt:
            print(f"  텍스트 응답: {txt[:400]}")
        raise SystemExit("이미지 출력 없음 — 거부되었거나 응답 형태가 다름")

    out_dir = OUT_BASE / f"nano_a_{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{Path(args.image).stem}.png"
    dst.write_bytes(base64.b64decode(img_out.data))
    after = Image.open(dst).size

    print(f"  소요 {sec:.1f}s")
    print(f"  원본 {before} → 출력 {after}" + ("  ✅ 동일" if before == after else "  ⚠️ 크기 변경됨"))
    print(f"  저장 {dst}")
    u = getattr(res, "usage", None)
    if u:
        print(f"  usage: {u}")


if __name__ == "__main__":
    main()
