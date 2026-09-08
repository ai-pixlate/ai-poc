"""E1 추가 검증 — 나노바나나 방법 C: 영역별 크롭 후 되붙이기.

방법 A(전체 이미지 + 문장 지시)의 문제 두 가지를 우회한다.
    ① 출력 크기가 1024 격자로 고정됨  → 크롭 단위로 처리하고 원본 좌표에 되붙인다
    ② 이미지 전체를 다시 그림          → 마스크 안쪽만 합성하고 바깥은 원본 픽셀 유지

되붙이기가 핵심이다. 마스크 밖을 원본 그대로 두면 LaMa와 같은 보장
("마스크 밖은 손대지 않는다")이 생긴다. 모델 출력을 통째로 쓰면 그 보장이 없다.

입력
    data/images/{stem}.jpg                     원본
    poc/B_ocr/results/baseline/regions/*.json  영역 좌표
    results/masks/d15/{stem}.png               합성 범위 (E1 채택 마스크)

사용법
    python run_nano_crop.py --image 1.jpg --model flash
    python run_nano_crop.py --image 1.jpg --model flash --limit 3   # 일부만
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
B_REGIONS = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"
MASKS = HERE / "results" / "masks" / "d15"
OUT_BASE = HERE / "results"

MODELS = {"flash": ("gemini-2.5-flash-image", 0.039),
          "pro": ("gemini-3-pro-image", 0.134)}

# 크롭 한 조각에만 적용되는 지시. 전체 이미지용보다 짧고 구체적이다.
PROMPT = (
    "Remove the text from this image patch. "
    "Fill the area where the text was with the surrounding background — "
    "match its color, gradient, and texture so the patch looks seamless. "
    "Do NOT add any text, letters, words, numbers, or symbols. "
    "Do NOT add new objects. Keep everything else exactly as it is."
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
    ap.add_argument("--image", default="1.jpg")
    ap.add_argument("--model", default="flash", choices=list(MODELS))
    ap.add_argument("--margin", type=float, default=0.6,
                    help="크롭 여백 — 영역 높이 대비 비율. 모델이 채울 배경 문맥이 된다")
    ap.add_argument("--limit", type=int, default=None, help="앞 N개 영역만 처리")
    ap.add_argument("--feather", type=int, default=5, help="합성 경계 페더링 px")
    args = ap.parse_args()
    model_id, price = MODELS[args.model]

    stem = Path(args.image).stem
    src_path = IMAGES / args.image
    img = cv2.imdecode(np.fromfile(str(src_path), np.uint8), cv2.IMREAD_COLOR)
    mask = cv2.imdecode(np.fromfile(str(MASKS / f"{stem}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    regions = json.loads((B_REGIONS / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
    if args.limit:
        regions = regions[: args.limit]

    load_env()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY 없음")

    from google import genai
    from PIL import Image

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    out_dir = OUT_BASE / f"nano_c_{args.model}"
    (out_dir / "crops").mkdir(parents=True, exist_ok=True)

    H, W = img.shape[:2]
    result = img.copy()
    print(f"[nano-C] {model_id} ← {args.image} · 영역 {len(regions)}개 · 예상 {len(regions) * price:.3f}$")

    ok = 0
    t_all = time.perf_counter()
    for i, r in enumerate(regions, 1):
        x1, y1, x2, y2 = r["bbox"]
        m = max(20, int((y2 - y1) * args.margin))
        cx1, cy1 = max(0, x1 - m), max(0, y1 - m)
        cx2, cy2 = min(W, x2 + m), min(H, y2 + m)
        crop = img[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            continue

        buf = cv2.imencode(".png", crop)[1].tobytes()
        try:
            res = client.interactions.create(
                model=model_id,
                input=[{"type": "text", "text": PROMPT},
                       {"type": "image", "data": base64.b64encode(buf).decode(),
                        "mime_type": "image/png"}],
            )
        except Exception as e:
            print(f"  {i:>3}. 호출 실패 {type(e).__name__}: {str(e)[:90]}")
            continue

        out_img = getattr(res, "output_image", None)
        if out_img is None or not getattr(out_img, "data", None):
            print(f"  {i:>3}. 이미지 없음 (거부 가능성)")
            continue

        edited = np.array(Image.open(io.BytesIO(base64.b64decode(out_img.data))).convert("RGB"))
        edited = cv2.cvtColor(edited, cv2.COLOR_RGB2BGR)
        # 모델은 자체 격자(보통 1024)로 돌려준다. 크롭 크기로 되돌린다.
        edited = cv2.resize(edited, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out_dir / "crops" / f"{stem}_{i:02d}.png"), edited)

        # 되붙이기 — 마스크 안쪽만. 바깥은 원본 픽셀을 그대로 둔다.
        sub_mask = mask[cy1:cy2, cx1:cx2]
        k = args.feather | 1
        alpha = (cv2.GaussianBlur(sub_mask, (k, k), 0).astype(np.float32) / 255.0)[..., None]
        region_now = result[cy1:cy2, cx1:cx2].astype(np.float32)
        result[cy1:cy2, cx1:cx2] = (edited * alpha + region_now * (1 - alpha)).astype(np.uint8)
        ok += 1
        print(f"  {i:>3}. 완료  crop {crop.shape[1]}x{crop.shape[0]}")

    elapsed = time.perf_counter() - t_all
    cv2.imwrite(str(out_dir / f"{stem}.jpg"), result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    meta = {"model_id": model_id, "image": args.image, "regions": len(regions),
            "succeeded": ok, "margin_ratio": args.margin, "feather_px": args.feather,
            "total_sec": round(elapsed, 1), "cost_usd": round(ok * price, 4),
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / f"{stem}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    print(f"\n성공 {ok}/{len(regions)} · 소요 {elapsed:.0f}s · 비용 {ok * price:.3f}$")
    print(f"저장 {out_dir / f'{stem}.jpg'}")
    print(f"출력 크기 {result.shape[1]}x{result.shape[0]} — 원본과 동일 (되붙이기 방식)")


if __name__ == "__main__":
    main()
