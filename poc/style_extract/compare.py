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
RESULTS_FONT = HERE / "results_font"
OUT = HERE / "summary.md"

# 굵기·계열은 계획서상 범위 밖(12월)이었으나 되는지만 보려고 붙인 축이다.
FONT_VARIANT = "font_match"       # 판정 대상. stroke_ratio는 이 안에 포함됨
FONT_GRADE_COLS = ["굵기", "계열", "비고"]

GRADE_COLS = ["색", "크기", "정렬", "비고"]
ALIGN_ORDER = ["left", "center", "right", "단일행", "무관", "불명"]
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


def read_font_table() -> dict[str, list[str]]:
    """굵기·계열 판정표에서 채워진 행을 회수한다. 행 폭이 색 판정표와 다르다."""
    if not OUT.exists():
        return {}
    got: dict[str, list[str]] = {}
    width = 2 + 2 + len(FONT_GRADE_COLS) + 1
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != width or not cells[0].lower().endswith(".jpg"):
            continue
        if cells[1] != f"`{FONT_VARIANT}`":
            continue
        vals = cells[4 : 4 + len(FONT_GRADE_COLS)]
        if any(vals):
            got[cells[0]] = vals
    return got


def font_section(images: list[str], L: list[str]) -> None:
    """굵기·계열 — 실행됐을 때만 붙인다."""
    meta_path = RESULTS_FONT / FONT_VARIANT / "meta.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = {}
    for img in images:
        f = RESULTS_FONT / FONT_VARIANT / "fonts" / f"{Path(img).stem}.json"
        rows[img] = json.loads(f.read_text(encoding="utf-8"))["regions"] if f.exists() else []
    allrows = [r for img in images for r in rows[img]]
    matched = [r for r in allrows if r.get("font_score") is not None]
    filled = read_font_table()

    L.append("## 6. 굵기·폰트 계열 (추가 축)")
    L.append("")
    L.append("계획서에는 **범위 밖(12월)**으로 적힌 항목임. 되는지만 보려고 붙였음."
             " 대상은 **조판 대상 영역 중 높이 18px 이상**만.")
    L.append("")
    L.append("| 측정 | 방법 |")
    L.append("|---|---|")
    L.append("| 굵기 | 글자 획 두께 ÷ 글자 높이. 거리 변환 상위 20% 평균 × 2. "
             f"**{meta['cfg']['bold_at']} 이상이면 bold** |")
    L.append(f"| 계열 | 설치 폰트 **{meta['candidates']}종**으로 같은 글자를 렌더해 겹침(IoU) 비교 |")
    L.append("")
    L.append(f"- 대상 **{meta['total_regions']}영역** · 폰트 대조 성공 **{len(matched)}건** "
             "(한글 2자 이상만 대조함)")
    wd = meta["weight_dist"]
    L.append(f"- 획 두께 기준 굵기 — regular {wd.get('regular', 0)} / bold {wd.get('bold', 0)}")
    L.append("- 계열 판정 — " + " / ".join(f"{k} {v}" for k, v in meta["family_dist"].items()))
    L.append("")

    if matched:
        L.append("**글자 수별 대조 신뢰도** — IoU 중앙값. 길수록 무너짐.")
        L.append("")
        L.append("| 글자 수 | 건수 | IoU 중앙 |")
        L.append("|---|---|---|")
        for lo, hi, tag in ((2, 3, "2~3자"), (4, 6, "4~6자"), (7, 12, "7~12자"),
                            (13, 999, "13자 이상")):
            sub = sorted(r["font_score"] for r in matched
                         if lo <= len(r["text"].strip()) <= hi)
            if sub:
                L.append(f"| {tag} | {len(sub)} | {sub[len(sub) // 2]:.3f} |")
        L.append("")
        agree = sum(1 for r in matched if r.get("font_weight") == r.get("weight_est"))
        L.append(f"> ⚠️ **굵기 신호 두 개가 어긋남.** 획 두께는 regular 우세인데 폰트 대조는 "
                 f"bold를 고름 — 일치 {agree}/{len(matched)} ({agree / len(matched):.0%}). "
                 "겹침 비교가 획이 두꺼운 후보에 유리해 생기는 편향으로 보임. "
                 "**굵기는 획 두께 쪽을 볼 것.**")
        L.append("")
        gaps = sorted(r["family_gap"] for r in matched)
        flat = sum(1 for g in gaps if g < 0.05)
        L.append(f"> 계열 점수차(고딕 최고점 − 명조 최고점) 중앙 **{gaps[len(gaps) // 2]:.3f}**, "
                 f"0.05 미만이라 사실상 판별 불가인 건이 **{flat}/{len(gaps)}**임.")
        L.append("")

    L.append("### 판정 결과 — 굵기 **불가** / 계열 **미검증**")
    L.append("")
    L.append("**굵기 — 방법 수준에서 실패.** 굵기를 아는 표본으로 추정식 3안을 대조했는데"
             " bold와 regular가 역전됨.")
    L.append("")
    L.append("| 표본 | 육안 | top20 평균 | top5 평균 | 최대 |")
    L.append("|---|---|---|---|---|")
    for t, truth, a, b, c in (("`6.jpg` 더블", "bold", 0.089, 0.102, 0.118),
                              ("`8.jpg` BIODANCE'S", "regular", 0.100, 0.106, 0.165),
                              ("`8.jpg` 無", "bold", 0.084, 0.101, 0.126),
                              ("`8.jpg` 테스트 완료", "regular", 0.076, 0.098, 0.098),
                              ("`9.jpg` 역대최대", "bold", 0.216, 0.306, 0.394)):
        L.append(f"| {t} | {truth} | {a} | {b} | {c} |")
    L.append("")
    L.append("`더블`(bold)이 `BIODANCE'S`(regular)보다 낮게 나옴. **어떤 추정식·임계로도"
             " 갈리지 않음** — 임계 조정으로 풀 문제가 아님. 획 두께를 bbox 높이로 나누는"
             " 방식 자체가 한글 글꼴에서 변별력이 없음.")
    L.append("")
    L.append("**계열 — 전부 고딕이라 변별 기회가 없었음.** 70건 중 69건 고딕, 1건 명조"
             "(`7.jpg` `1억장*`, 계열차 0.019로 사실상 오판). 표본에 명조 문구가 없어"
             " **맞았다기보다 틀릴 기회가 없었음.**")
    L.append("")
    L.append("### 판정표 — 굵기·계열")
    L.append("")
    L.append("**채울 칸은 `굵기`·`계열` 2개.** 이미지 단위 A/B/C."
             " `vis/`의 띠에 `번호 크기 획비율 굵기 계열/굵기 IoU 텍스트` 순으로 찍혀 있음.")
    L.append("")
    L.append("| 이미지 | variant | 대상 | IoU 중앙 | " + " | ".join(FONT_GRADE_COLS)
             + " | 시각화 |")
    L.append("|---|---|---|---|" + "---|" * len(FONT_GRADE_COLS) + "---|")
    for img in images:
        rs = rows[img]
        ms = sorted(r["font_score"] for r in rs if r.get("font_score") is not None)
        med = f"{ms[len(ms) // 2]:.3f}" if ms else "—"
        vals = filled.get(img, [""] * len(FONT_GRADE_COLS))
        L.append(f"| {img} | `{FONT_VARIANT}` | {len(rs)} | {med} | " + " | ".join(vals)
                 + f" | `results_font/{FONT_VARIANT}/vis/{Path(img).stem}.jpg` |")
    L.append("")


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
    L.append("> 굵기·폰트 계열은 계획서상 범위 밖이나 **되는지만 시험함** — 6장.")
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

    # variant 간 색 차이 — 완전 일치 여부가 아니라 **눈에 보이는 차이**로 잰다
    if len(names) >= 2:
        a, b = names[0], names[1]
        def rgb(h):
            return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
        gaps = []
        for img in images:
            for x, y in zip(rows[(a, img)], rows[(b, img)]):
                gaps.append(max(abs(p - q) for p, q in zip(rgb(x["font_color"]),
                                                           rgb(y["font_color"]))))
        gaps.sort()
        big = sum(1 for g in gaps if g > 16)
        L.append(f"**`{a}` ↔ `{b}` 글자색 차이** — 채널 최대차 중앙 **{gaps[len(gaps) // 2]}**, "
                 f"평균 {sum(gaps) / len(gaps):.1f}. 눈에 보일 만한 차이(16 초과)는 "
                 f"**{big}/{len(gaps)}건**뿐임.")
        L.append("")
        L.append("→ **두 방식은 사실상 같은 답을 냄.** 색 판정은 두 variant가 같은 등급을 받음.")
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
    L.append("**시각화는 `vis_target/` — 제품 라벨을 뺀 조판 대상만 그림.** 원본 오른쪽에"
             " 추출한 글자색·배경색 스와치를 붙였음. 번호는 전체 뷰(`vis/`)와 같음.")
    L.append("")
    L.append("`영역`·`저대비`도 **조판 대상 기준**임. 라벨 포함 전체는 2장에 있음.")
    L.append("")
    L.append("| 이미지 | variant | 영역 | 저대비 | " + " | ".join(GRADE_COLS) + " | 시각화 |")
    L.append("|---|---|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in names:
            rs = [r for r in rows[(n, img)] if not r["is_product_label"]]
            low = sum(1 for r in rs if r["contrast"] < CONTRAST_FLOOR)
            vals = filled.get((img, n), [""] * len(GRADE_COLS))
            L.append(f"| {img} | `{n}` | {len(rs)} | {low} | " + " | ".join(vals)
                     + f" | `results/{n}/vis_target/{stem}.jpg` |")
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

    font_section(images, L)

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
