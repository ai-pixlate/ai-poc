"""섹션 분해 — 판정용 대지 생성기.

초장축 페이지는 세로로 길어 그대로 보기 어렵다. 섹션을 **가로로 눕혀**
한 장에 늘어놓아 문맥 단위가 맞게 갈렸는지 눈으로 보게 한다.

출력
    results/{variant}/contact/{stem}.jpg   섹션을 가로로 나열한 대지

각 칸 위에 `번호 · 원본 y범위 · 높이 · 절단 출처`를 적는다. 제목 띠 색이 출처다.
    검정 여백·시작  빨강 배경색 전환  파랑 보조 분해(여백+병합)  보라 보조 분해(VLM)
    주황 강제 분할

사용법
    python review.py --variant gap_major
    python review.py --variant gap_major --images A000000219554_002.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

PANEL_W = 220     # 칸 하나의 가로 폭
BAR = 34          # 칸 제목 높이
GAP = 8


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet(variant: str, stem: str) -> Path | None:
    meta = json.loads(
        (RESULTS / variant / "sections" / f"{stem}.json").read_text(encoding="utf-8")
    )
    secs = meta["sections"]
    if not secs:
        return None

    panels = []
    for s in secs:
        im = Image.open(RESULTS / variant / s["crop"]).convert("RGB")
        r = PANEL_W / im.width
        panels.append(im.resize((PANEL_W, max(1, round(im.height * r))), Image.BILINEAR))

    h = max(p.height for p in panels)
    w = PANEL_W * len(panels) + GAP * (len(panels) - 1)
    canvas = Image.new("RGB", (w, h + BAR), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    font = _font(15)

    fills = {"color": (200, 40, 40), "aux_ws": (40, 100, 210), "aux_vlm": (130, 60, 180)}
    tags = {"color": "색", "aux_ws": "보조", "aux_vlm": "VLM"}
    for i, (s, im) in enumerate(zip(secs, panels)):
        x = i * (PANEL_W + GAP)
        canvas.paste(im, (x, BAR))
        src = s.get("cut_source", "")
        fill = (255, 150, 0) if s["forced"] else fills.get(src, (30, 30, 30))
        draw.rectangle([x, 0, x + PANEL_W, BAR], fill=fill)
        tag = tags.get(src, "")
        draw.text((x + 6, 8), f"{s['index']} {tag} y{s['range'][0]}~{s['range'][1]} "
                              f"{s['height']}px", fill=(255, 255, 255), font=font)

    out = RESULTS / variant / "contact" / f"{stem}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=85)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    src = RESULTS / args.variant / "sections"
    if not src.exists():
        raise SystemExit(f"{src} 없음 — run.py 를 먼저 돌릴 것")
    stems = ([Path(n).stem for n in args.images] if args.images
             else sorted(p.stem for p in src.glob("*.json")))

    for stem in stems:
        out = contact_sheet(args.variant, stem)
        if out:
            im = Image.open(out)
            print(f"  {stem:<26} {im.width}x{im.height}  {out}")


if __name__ == "__main__":
    main()
