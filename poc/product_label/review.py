"""제품 라벨 판정 — 비교 뷰 생성기.

variant별 시각화를 **가로로 나란히** 붙여 한 화면에서 비교한다.
각 판에서 빨강이 라벨 판정, 파랑이 배경 판정이다.

출력
    results/_review/{stem}.jpg   variant를 나란히 붙인 비교 뷰
    results/_review/votes.md     블록별 표 — 텍스트와 각 variant 판정

머리글자는 votes.md 표의 열 이름으로만 쓴다.

    M mask_overlap   T bg_texture   S poly_skew   R role_ext   V vlm_relation

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


def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# 판 하나의 가로 폭. 5종이면 합쳐서 약 3,600px가 된다.
PANEL_W = 700
BAR = 42   # 상단 이름표 높이
GAP = 10   # 판 사이 여백


def side_by_side(stem: str, names: list[str], counts: dict[str, int]) -> Path:
    """variant별 vis를 가로로 붙인다. 각 판 위에 이름과 라벨 수를 적는다."""
    panels = []
    for n in names:
        im = Image.open(RESULTS / n / "vis" / f"{stem}.jpg").convert("RGB")
        r = PANEL_W / im.width
        panels.append(im.resize((PANEL_W, round(im.height * r)), Image.LANCZOS))

    h = max(p.height for p in panels)
    w = PANEL_W * len(panels) + GAP * (len(panels) - 1)
    canvas = Image.new("RGB", (w, h + BAR), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = _font(24)

    for i, (n, im) in enumerate(zip(names, panels)):
        x = i * (PANEL_W + GAP)
        canvas.paste(im, (x, BAR))
        draw.rectangle([x, 0, x + PANEL_W, BAR], fill=(30, 30, 30))
        draw.text((x + 10, 9), f"{initial(n)}  {n}  라벨 {counts[n]}",
                  fill=(255, 255, 255), font=font)

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{stem}.jpg"
    canvas.save(out, quality=88)
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

    L = [f"# 라벨 판정 비교 — variant {len(names)}종", "",
         "각 뷰는 variant를 가로로 나란히 붙인 것. **빨강 = 라벨 판정 · 파랑 = 배경 판정.**",
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
        counts = {n: sum(1 for b in blocks[n] if b["is_product_label"]) for n in names}
        path = side_by_side(stem, names, counts)
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
    print(f"비교 뷰 {len(stems)}장 · 갈림 총 {total_split}블록")
    print(f"작성: {OUT / 'votes.md'}")


if __name__ == "__main__":
    main()
