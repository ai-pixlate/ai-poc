"""제품 라벨 판정 — 합의도 뷰 생성기.

variant를 이미지 여러 장으로 나눠 보면 갈리는 지점이 안 보인다.
**한 장에 전부 겹쳐** 블록마다 몇 종이 라벨로 봤는지 표시한다.

색 = 표수. 라벨 옆 글자 = 라벨로 본 variant의 머리글자.

    M mask_overlap   T bg_texture   S poly_skew   R role_ext   V vlm_relation

출력
    results/_review/{stem}.jpg   합의도 시각화
    results/_review/votes.md     블록별 표 — 텍스트와 각 variant 판정

`vlm_opus`는 기본 제외한다 — `vlm_relation`과 110블록 전부 같은 판정이라
겹쳐 그리면 표수만 부풀린다. `--include`로 넣을 수 있다.

사용법
    python review.py
    python review.py --include vlm_opus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
RESULTS = HERE / "results"
OUT = RESULTS / "_review"

# 머리글자 — 시각화 라벨에 쓴다. 여기 없는 variant는 첫 글자를 대문자로 쓴다.
INITIAL = {
    "mask_overlap": "M",
    "bg_texture": "T",
    "poly_skew": "S",
    "role_ext": "R",
    "vlm_relation": "V",
    "vlm_opus": "O",
}
# 기본 제외 — vlm_relation과 판정이 동일해 표수만 부풀린다.
EXCLUDE_DEFAULT = {"vlm_opus"}


def variants(include: set[str]) -> list[str]:
    names = sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())
    return [n for n in names if n not in (EXCLUDE_DEFAULT - include)]


def initial(name: str) -> str:
    return INITIAL.get(name, name[:1].upper())


def color_for(votes: int, total: int) -> tuple[int, int, int]:
    """전원 라벨은 빨강, 전원 배경은 파랑, 갈리면 주황."""
    if votes == total:
        return (220, 30, 30)
    if votes == 0:
        return (30, 90, 220)
    return (235, 140, 0)


def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_image(stem: str, names: list[str], votes: list[list[str]], boxes: list[list[int]]) -> Path:
    img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(13, min(img.width, img.height) // 55)
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    for i, (box, yes) in enumerate(zip(boxes, votes), 1):
        color = color_for(len(yes), len(names))
        draw.rectangle(box, outline=color, width=3)
        x1, y1, x2, _ = box
        mark = "".join(initial(n) for n in names if n in yes) or "—"
        text = f"{i} {len(yes)}/{len(names)} {mark}"
        box_w = int(draw.textlength(text, font=font)) + 2 * pad

        if y1 - box_h >= 0:
            left, top = x1, y1 - box_h
        elif x1 - box_w >= 0:
            left, top = x1 - box_w, y1
        else:
            left, top = min(x2, img.width - box_w), y1
        left = max(0, min(left, img.width - box_w))
        top = max(0, min(top, img.height - box_h))
        draw.rectangle([left, top, left + box_w, top + box_h], fill=color)
        draw.text((left + pad, top + pad // 2), text, fill=(255, 255, 255), font=font)

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{stem}.jpg"
    img.save(out, quality=92)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--include", nargs="*", default=[], help="기본 제외 variant를 다시 넣는다")
    args = ap.parse_args()

    names = variants(set(args.include))
    if not names:
        raise SystemExit(f"{RESULTS} 아래 실행 결과 없음")

    stems = sorted(
        (p.stem for p in (RESULTS / names[0] / "blocks").glob("*.json")),
        key=lambda s: (len(s), s),
    )

    L = [f"# 라벨 판정 합의도 — variant {len(names)}종", "",
         "표수 = 라벨로 본 variant 수. **갈리는 블록이 판정 대상임.**", "",
         "| 머리글자 | variant |", "|---|---|"]
    for n in names:
        L.append(f"| **{initial(n)}** | `{n}` |")
    L.append("")

    total_split = 0
    for stem in stems:
        blocks = {
            n: json.loads(
                (RESULTS / n / "blocks" / f"{stem}.json").read_text(encoding="utf-8")
            )["blocks"]
            for n in names
        }
        base = blocks[names[0]]
        boxes = [b["bbox"] for b in base]
        votes = [
            [n for n in names if blocks[n][i]["is_product_label"]] for i in range(len(base))
        ]
        path = draw_image(stem, names, votes, boxes)
        split = sum(1 for v in votes if 0 < len(v) < len(names))
        total_split += split

        L.append(f"## {stem}.jpg — 블록 {len(base)}, 갈림 **{split}**")
        L.append("")
        L.append(f"![]({path.name})")
        L.append("")
        L.append("| # | 표 | " + " | ".join(initial(n) for n in names) + " | 텍스트 |")
        L.append("|---|---|" + "---|" * len(names) + "---|")
        for i, (b, yes) in enumerate(zip(base, votes), 1):
            marks = " | ".join("O" if n in yes else "·" for n in names)
            t = b["text"].replace("\n", " / ").replace("|", "\\|")[:40]
            flag = "**" if 0 < len(yes) < len(names) else ""
            L.append(f"| {flag}{i}{flag} | {len(yes)}/{len(names)} | {marks} | {t} |")
        L.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "votes.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"합의도 뷰 {len(stems)}장 · 갈림 총 {total_split}블록")
    print(f"작성: {OUT / 'votes.md'}")


if __name__ == "__main__":
    main()
