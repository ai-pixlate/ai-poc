"""스타일 추출 — variant 비교표 생성기.

사람이 채우는 건 판정표의 **색·크기·정렬 3칸**이다. 전부 육안 A/B/C.
등급 산식을 두지 않는다 — 정답 색이 없고, 육안 대조가 곧 판정이다.

기계가 채우는 것
    대비    추출한 글자색·배경색의 WCAG 명도 대비 중앙값.
            1.0에 가까우면 두 색이 갈리지 않은 것 — **추출 실패 신호**
    정렬    좌·중앙·우·단일행·불명 분포. `불명`이 많으면 규칙이 안 먹은 것

**이미 채워진 값은 재실행해도 보존한다.**

사용법
    python compare.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

GRADE_COLS = ["색", "크기", "정렬", "비고"]
ALIGN_ORDER = ["left", "center", "right", "단일행", "불명"]
# 대비가 이 값 미만이면 글자색과 배경색이 사실상 같은 색으로 나온 것이다.
CONTRAST_FLOOR = 1.5


def variants() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())


def load(variant: str, stem: str) -> list[dict]:
    return json.loads(
        (RESULTS / variant / "styles" / f"{stem}.json").read_text(encoding="utf-8")
    )["styles"]


def read_existing() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 등급을 회수한다."""
    if not OUT.exists():
        return {}
    got: dict[tuple[str, str], list[str]] = {}
    width = 2 + 2 + len(GRADE_COLS) + 1   # 이미지 variant 영역 저대비 + 판정 + 시각화
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != width:
            continue
        img, variant = cells[0], cells[1]
        if not img.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[4 : 4 + len(GRADE_COLS)]
        if any(vals):
            got[(img, variant.strip("`"))] = vals
    return got


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    names = variants()
    if not names:
        raise SystemExit(f"{RESULTS} 아래 실행 결과 없음 — run.py 를 먼저 돌릴 것")
    metas = {n: json.loads((RESULTS / n / "meta.json").read_text(encoding="utf-8")) for n in names}
    images = [p["image"] for p in metas[names[0]]["per_image"]]
    filled = read_existing()
    rows = {(n, img): load(n, Path(img).stem) for n in names for img in images}

    L: list[str] = []
    L.append("# 스타일 추출 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **색·크기·정렬 3칸이 사람이 채우는 전부임.**")
    L.append("> 입력은 텍스트 인식 `baseline` 영역 + `vlm_relation` 블록(정렬·역할·라벨).")
    L.append("> **굵기 추정·폰트 패밀리 식별은 범위 밖(12월).**")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| variant | 색 추출 방식 | 이미지 | 영역 | 소요 |")
    L.append("|---|---|---|---|---|")
    how = {"dominant_color": "bbox 화소를 2색 군집(k-means). 적은 쪽을 글자로",
           "contrast_split": "밝기 Otsu 이진화. 적은 쪽을 글자로"}
    for n in names:
        m = metas[n]
        L.append(f"| `{n}` | {how.get(n, '')} | {m['images']} | {m['total_regions']} | "
                 f"{m['total_sec']}s |")
    L.append("")
    cfg = metas[names[0]]["cfg"]
    L.append(f"크기는 bbox 높이(글자 획 높이), em 환산 × **{cfg['em_ratio']}**. "
             f"정렬 허용 오차는 블록 폭의 **{cfg['align_tol']:.0%}**. 두 variant가 같음 — "
             "**변인은 색 추출 방식뿐임.**")
    L.append("")

    # 2. 색 추출 — 기계 지표
    L.append("## 2. 색 추출 (기계 집계 — 정오 아님)")
    L.append("")
    L.append(f"**저대비** = 글자색·배경색 대비가 {CONTRAST_FLOOR} 미만인 영역."
             " 두 색이 갈리지 않았다는 뜻이라 **추출 실패 신호**임.")
    L.append("")
    L.append("| variant | 대비 중앙 | 저대비 영역 | 저대비 비율 |")
    L.append("|---|---|---|---|")
    for n in names:
        allrows = [r for img in images for r in rows[(n, img)]]
        cs = sorted(r["contrast"] for r in allrows)
        low = sum(1 for r in allrows if r["contrast"] < CONTRAST_FLOOR)
        L.append(f"| `{n}` | {cs[len(cs) // 2]} | {low} / {len(allrows)} | "
                 f"{low / len(allrows):.0%} |")
    L.append("")

    # variant 간 색 차이
    if len(names) >= 2:
        a, b = names[0], names[1]
        same = diff = 0
        for img in images:
            for x, y in zip(rows[(a, img)], rows[(b, img)]):
                if x["font_color"] == y["font_color"]:
                    same += 1
                else:
                    diff += 1
        L.append(f"**`{a}` ↔ `{b}` 글자색 일치** — 완전 동일 {same} / 다름 {diff} "
                 f"({same / max(1, same + diff):.0%} 일치)")
        L.append("")

    # 3. 정렬 분포
    L.append("## 3. 정렬 분포 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("블록 안 행들의 좌·중앙·우 좌표 분산으로 판정함. **`불명`은 어느 축도 고르지 않은 것.**")
    L.append("")
    L.append("| 구분 | " + " | ".join(ALIGN_ORDER) + " | 합 |")
    L.append("|---|" + "---|" * (len(ALIGN_ORDER) + 1))
    base = names[0]
    for tag, pick in (("라벨 아님 (조판 대상)", False), ("제품 라벨", True)):
        c = Counter(r["align"] for img in images for r in rows[(base, img)]
                    if bool(r["is_product_label"]) is pick)
        tot = sum(c.values())
        L.append(f"| {tag} | " + " | ".join(str(c.get(k, 0)) for k in ALIGN_ORDER)
                 + f" | {tot} |")
    L.append("")
    L.append("**라벨은 하류에서 제외되므로 `라벨 아님` 행만 실사용에 해당함.**")
    L.append("")

    # 4. 판정표
    L.append("## 4. 판정표")
    L.append("")
    L.append("**채울 칸은 `색`·`크기`·`정렬` 3개.** 이미지 단위 A/B/C. `영역`·`저대비`는 코드가 채움.")
    L.append("")
    L.append("`vis/`는 원본 오른쪽에 **추출한 글자색·배경색 스와치**를 영역 번호 순으로 붙인 것."
             " 원본 글자와 스와치를 나란히 놓고 대조하면 됨.")
    L.append("")
    L.append("| 이미지 | variant | 영역 | 저대비 | " + " | ".join(GRADE_COLS) + " | 시각화 |")
    L.append("|---|---|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in names:
            rs = rows[(n, img)]
            low = sum(1 for r in rs if r["contrast"] < CONTRAST_FLOOR)
            vals = filled.get((img, n), [""] * len(GRADE_COLS))
            L.append(f"| {img} | `{n}` | {len(rs)} | {low} | " + " | ".join(vals)
                     + f" | `results/{n}/vis/{stem}.jpg` |")
    L.append("")

    # 5. 집계
    L.append("## 5. 집계")
    L.append("")
    if not filled:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L.append(f"채워진 행 {len(filled)} / {len(images) * len(names)}. 빈 행은 계산에서 뺌.")
        L.append("")
        L.append("| variant | 축 | A | B | C | A+B |")
        L.append("|---|---|---|---|---|---|")
        for n in names:
            got = [v for (img, var), v in filled.items() if var == n]
            for i, axis in enumerate(GRADE_COLS[:3]):
                g = [v[i] for v in got if v[i] in {"A", "B", "C"}]
                if not g:
                    continue
                ab = sum(1 for x in g if x in {"A", "B"})
                L.append(f"| `{n}` | {axis} | {g.count('A')} | {g.count('B')} | "
                         f"{g.count('C')} | **{ab}/{len(g)} ({ab / len(g):.0%})** |")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
