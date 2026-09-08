"""줄·문단 병합 + 역할 분류 — 판정 보조 뷰 생성기.

variant 2종의 시각화를 가로로 붙여 한 화면에서 비교하게 만든다.
결과가 다른 이미지만 만든다 — 같은 이미지는 두 번 볼 필요가 없다.

출력
    results/_review/{stem}.jpg   왼쪽 variant | 오른쪽 variant
    results/_review/diff.md      차이 나는 블록의 텍스트 대조

등급을 매기지 않는다. 사람이 보기 쉽게 만드는 데까지가 이 코드의 역할이다.

사용법
    python review.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = RESULTS / "_review"

BAR = 46  # 상단 이름표 높이
GAP = 12  # 두 이미지 사이 여백


def variants() -> list[str]:
    return sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())


def blocks_of(variant: str, stem: str) -> list[dict]:
    path = RESULTS / variant / "blocks" / f"{stem}.json"
    return json.loads(path.read_text(encoding="utf-8"))["blocks"]


def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def side_by_side(a: str, b: str, stem: str) -> Path:
    ia = Image.open(RESULTS / a / "vis" / f"{stem}.jpg").convert("RGB")
    ib = Image.open(RESULTS / b / "vis" / f"{stem}.jpg").convert("RGB")
    h = max(ia.height, ib.height)
    canvas = Image.new("RGB", (ia.width + GAP + ib.width, h + BAR), (255, 255, 255))
    canvas.paste(ia, (0, BAR))
    canvas.paste(ib, (ia.width + GAP, BAR))

    draw = ImageDraw.Draw(canvas)
    font = _font(26)
    draw.rectangle([0, 0, canvas.width, BAR], fill=(30, 30, 30))
    draw.text((10, 10), a, fill=(255, 255, 255), font=font)
    draw.text((ia.width + GAP + 10, 10), b, fill=(255, 255, 255), font=font)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{stem}.jpg"
    canvas.save(path, quality=90)
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    names = variants()
    if len(names) < 2:
        raise SystemExit("variant가 2종 미만이라 비교 뷰를 만들 수 없음")
    a, b = names[0], names[1]

    stems = sorted(
        (p.stem for p in (RESULTS / a / "blocks").glob("*.json")),
        key=lambda s: (len(s), s),
    )

    lines = [f"# 판정 보조 — `{a}` vs `{b}`", "",
             "결과가 다른 이미지만 실음. 같은 이미지는 한 번만 보고 두 행에 같은 등급을 씀.", ""]
    same_all, made = [], []
    for stem in stems:
        ba, bb = blocks_of(a, stem), blocks_of(b, stem)
        sa = {tuple(x["regions"]): x for x in ba}
        sb = {tuple(x["regions"]): x for x in bb}
        only_a = [sa[k] for k in sa.keys() - sb.keys()]
        only_b = [sb[k] for k in sb.keys() - sa.keys()]
        if not only_a and not only_b:
            same_all.append(stem)
            continue

        path = side_by_side(a, b, stem)
        made.append(stem)
        lines.append(f"## {stem}.jpg — `{a}` {len(ba)}블록 / `{b}` {len(bb)}블록")
        lines.append("")
        lines.append(f"![]({path.name})")
        lines.append("")
        lines.append(f"| 쪽 | 블록 텍스트 | 역할 |")
        lines.append("|---|---|---|")
        for x in sorted(only_a, key=lambda x: x["bbox"][1]):
            t = x["text"].replace("\n", " / ").replace("|", "\\|")
            lines.append(f"| `{a}`만 | {t} | {x['role']} |")
        for x in sorted(only_b, key=lambda x: x["bbox"][1]):
            t = x["text"].replace("\n", " / ").replace("|", "\\|")
            lines.append(f"| `{b}`만 | {t} | {x['role']} |")
        lines.append("")

    lines.append("## 두 variant 결과가 같은 이미지")
    lines.append("")
    lines.append(", ".join(f"`{s}.jpg`" for s in same_all) if same_all else "_없음_")
    lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"비교 뷰 {len(made)}장: {', '.join(made)}")
    print(f"동일 {len(same_all)}장: {', '.join(same_all)}")
    print(f"작성: {OUT / 'diff.md'}")


if __name__ == "__main__":
    main()
