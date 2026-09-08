"""줄·문단 병합 + 역할 분류 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
사람이 채우는 건 4장 판정표의 건수 4칸뿐이다.

  과분할 / 과병합 / 오분류 / 라벨

등급(A/B/C)은 그 건수에서 산식으로 나온다. 산식과 다르게 볼 때만
5장 덮어쓰기 표에 등급을 적는다. 적으면 사람 판단이 최종이다.

**정답 라벨을 만들지 않기로 함(2026-09-08).** 병합·역할의 정오는 사람이
육안으로 본다. 대신 정답 없이도 계산되는 보조 지표를 붙여 어느 이미지를
먼저 볼지 고르는 데 쓴다. 보조 지표는 **정오가 아니다.**

  겹침  — 블록 bbox끼리 겹치는 쌍의 수. 과병합에서도 늘지만 원래 겹쳐
          배치된 레이아웃(제품 패키지 사진 등)에서도 는다.
  이질  — 한 블록 안에서 글자 높이가 1.5배 넘게 벌어진 블록 수.
          h_ratio가 직접 누르는 값이라 variant 간 차이는 설계상 당연하다.
  일치율 — variant 간 블록 경계가 같은 비율. 임계 민감도.

**이미 채워진 값은 재실행해도 보존한다.** 두 표를 (이미지, variant) 키로
읽어 되돌려 넣는다.

사용법
    python compare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

ROLES = ["제목", "본문", "캡션", "가격", "주의문구"]

# 4장 판정표 — 기계 열과 사람 열.
MACHINE_COLS = ["겹침", "이질"]
COUNT_COLS = ["과분할", "과병합", "오분류", "라벨", "비고"]
# 5장 덮어쓰기 표 — 산식과 다르게 볼 때만 채운다.
OVERRIDE_COLS = ["병합", "역할", "사유"]

# 한 블록 안에서 이 배수를 넘게 글자 높이가 벌어지면 이질로 센다.
HETERO_RATIO = 1.5

# 등급 산식 (2026-09-08 확정)
#   과병합에 2배 가중 — 과분할은 조각이 제자리에 남아 배치가 유지되지만,
#   과병합은 서로 다른 자리의 문단이 한 박스가 돼 되돌릴 수 없다.
OVER_MERGE_WEIGHT = 2
MERGE_A, MERGE_B = 0.10, 0.25     # 가중 오류율 상한
ROLE_A, ROLE_B = 0.10, 0.25       # 역할 오분류율 상한
SMALL_BLOCKS = 10                 # 블록이 이보다 적으면 1건까지 A로 봐준다
GATE = 0.70                       # 채택 게이트 — 12장 A+B 비율


def grade_merge(over_split: int, over_merge: int, blocks: int) -> str:
    """과분할·과병합 건수 → 병합 등급. 사람이 넣은 값의 산술 결과일 뿐이다."""
    w = over_split + over_merge * OVER_MERGE_WEIGHT
    if blocks < SMALL_BLOCKS and w <= 1 and over_merge == 0:
        return "A"
    rate = w / max(1, blocks)
    if rate <= MERGE_A and over_merge == 0:
        return "A"
    if rate <= MERGE_B:
        return "B"
    return "C"


def grade_role(mis: int, blocks: int, labels: int = 0) -> str:
    """오분류 건수 → 역할 등급.

    제품 인쇄 글자(라벨) 블록은 5종 어디에도 해당하지 않으므로 분모에서 뺀다.
    주의문구 미탐 상한은 산식이 모른다 — 사람이 덮어쓰기 표에서 내린다.
    """
    judged = blocks - labels
    if judged <= 0:
        return "—"  # 전부 라벨이라 역할을 판정할 대상이 없다
    rate = mis / judged
    if rate <= ROLE_A:
        return "A"
    if rate <= ROLE_B:
        return "B"
    return "C"


def variants() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())


def load_blocks(variant: str, image: str) -> list[dict]:
    path = RESULTS / variant / "blocks" / f"{Path(image).stem}.json"
    return json.loads(path.read_text(encoding="utf-8"))["blocks"]


# ---------------------------------------------------------------- 보조 지표

def overlap_pairs(blocks: list[dict]) -> int:
    """bbox가 겹치거나 한쪽이 다른쪽을 품는 블록 쌍의 수.

    과병합이면 늘지만, 제품 패키지 사진처럼 글자가 원래 겹쳐 배치된
    이미지에서도 는다. 어느 쪽인지는 vis를 봐야 갈린다. 정오 판정이 아니다.
    """
    n = 0
    for i in range(len(blocks)):
        a = blocks[i]["bbox"]
        for j in range(i + 1, len(blocks)):
            b = blocks[j]["bbox"]
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                n += 1
    return n


def hetero_blocks(blocks: list[dict], regions_h: dict[int, int]) -> int:
    """한 블록 안에서 글자 높이가 HETERO_RATIO 배를 넘게 벌어진 블록 수."""
    n = 0
    for b in blocks:
        hs = [regions_h[i] for i in b["regions"] if i in regions_h]
        if len(hs) >= 2 and max(hs) / max(1, min(hs)) > HETERO_RATIO:
            n += 1
    return n


def agreement(a: list[dict], b: list[dict]) -> tuple[int, float]:
    """두 variant에서 구성 영역이 완전히 같은 블록 수와 비율."""
    sa = {tuple(x["regions"]) for x in a}
    sb = {tuple(x["regions"]) for x in b}
    same = len(sa & sb)
    denom = max(1, (len(sa) + len(sb)) / 2)
    return same, same / denom


# ---------------------------------------------------------------- 입력 보존

Table = dict[tuple[str, str], list[str]]


def read_table(cols: list[str], lead: int) -> Table:
    """summary.md의 표에서 채워진 행을 회수한다.

    lead = 이미지·variant 뒤에 오는 자동 생성 열의 수.
    끝에 시각화 열이 붙는 표도 있어 너비를 두 가지로 허용한다.
    """
    if not OUT.exists():
        return {}
    got: Table = {}
    widths = {2 + lead + len(cols), 2 + lead + len(cols) + 1}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) not in widths:
            continue
        img, variant = cells[0], cells[1]
        if not img.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[2 + lead : 2 + lead + len(cols)]
        if any(vals):
            got[(img, variant.strip("`"))] = vals
    return got


def propagate(
    table: Table,
    blocks: dict[tuple[str, str], list[dict]],
    images: list[str],
    names: list[str],
    label: str,
) -> list[str]:
    """블록 구성이 완전히 같은 variant끼리 입력을 복사한다.

    구성 region이 하나도 다르지 않으면 건수가 정의상 같은 값이다.
    사람이 넣은 값을 옮길 뿐 새로 만들지 않는다. 한쪽만 채워져 있을 때만
    복사하고, 양쪽이 다르게 채워져 있으면 손대지 않는다.
    """
    notes = []
    for img in images:
        sig = {n: {tuple(b["regions"]) for b in blocks[(n, img)]} for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                if sig[a] != sig[b]:
                    continue
                fa, fb = table.get((img, a)), table.get((img, b))
                if fa and fb and fa[:-1] != fb[:-1]:
                    notes.append(
                        f"  ! {img} {label} — `{a}`·`{b}` 블록이 같은데 값이 다름. 그대로 둠"
                    )
                    continue
                if fa and not fb:
                    table[(img, b)] = fa[:-1] + [f"`{a}`에서 자동 복사"]
                    notes.append(f"  = {img} {label} — `{a}` → `{b}` 복사")
                elif fb and not fa:
                    table[(img, a)] = fb[:-1] + [f"`{b}`에서 자동 복사"]
                    notes.append(f"  = {img} {label} — `{b}` → `{a}` 복사")
    return notes


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    names = variants()
    if not names:
        raise SystemExit(f"{RESULTS} 아래 실행 결과 없음 — run.py 를 먼저 돌릴 것")

    metas = {n: json.loads((RESULTS / n / "meta.json").read_text(encoding="utf-8")) for n in names}
    images = [p["image"] for p in metas[names[0]]["per_image"]]

    counts = read_table(COUNT_COLS, lead=4)       # 영역·블록·겹침·이질 뒤
    overrides = read_table(OVERRIDE_COLS, lead=0)

    blocks: dict[tuple[str, str], list[dict]] = {}
    heights: dict[str, dict[int, int]] = {}
    src = HERE.parents[1] / "poc" / "B_ocr" / "results" / "baseline" / "regions"
    for img in images:
        rs = json.loads((src / f"{Path(img).stem}.json").read_text(encoding="utf-8"))["regions"]
        heights[img] = {i: r["bbox"][3] - r["bbox"][1] for i, r in enumerate(rs)}
        for n in names:
            blocks[(n, img)] = load_blocks(n, img)

    for line in propagate(counts, blocks, images, names, "건수"):
        print(line)
    for line in propagate(overrides, blocks, images, names, "덮어쓰기"):
        print(line)

    L: list[str] = []
    L.append("# 줄·문단 병합 + 역할 분류 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **4장 건수 4칸이 사람이 채우는 전부임.**")
    L.append("> 입력은 텍스트 인식 `baseline` 영역. 판정 기준·계획은 `PoC_추가검증_계획.md`.")
    L.append("> **정답 라벨 없음** — 병합·역할의 정오는 육안으로 봄.")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| variant | 조건 | 이미지 | 영역 | 블록 | 소요 |")
    L.append("|---|---|---|---|---|---|")
    for n in names:
        m = metas[n]
        cfg = " ".join(f"`{k}={v}`" for k, v in m["cfg"].items())
        L.append(
            f"| `{n}` | {cfg} | {m['images']} | {m['total_regions']} | "
            f"{m['total_blocks']} | {m['total_sec']}s |"
        )
    L.append("")

    # 2. 역할 분포
    L.append("## 2. 역할 분포 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("| variant | " + " | ".join(ROLES) + " |")
    L.append("|---|" + "---|" * len(ROLES))
    for n in names:
        r = metas[n]["roles"]
        L.append(f"| `{n}` | " + " | ".join(str(r.get(x, 0)) for x in ROLES) + " |")
    L.append("")

    # 3. 보조 지표
    L.append("## 3. 보조 지표 (정답 없이 계산 — 정오 아님)")
    L.append("")
    L.append("- **겹침** = 블록 bbox가 서로 겹치는 쌍의 수. 과병합에서도 늘지만"
             " **원래 겹쳐 배치된 레이아웃**(제품 패키지 사진 등)에서도 늚 — vis로 갈라야 함")
    L.append(f"- **이질** = 한 블록 안에서 글자 높이가 {HETERO_RATIO}배 넘게 벌어진 블록 수."
             " `h_ratio`가 직접 누르는 값이라 **variant 간 차이는 설계상 당연** — 총수보다"
             " 어느 블록인지가 정보")
    L.append("")
    L.append("| variant | 겹침 | 이질 | 겹침 있는 이미지 |")
    L.append("|---|---|---|---|")
    machine: dict[tuple[str, str], tuple[int, int]] = {}
    for n in names:
        ov_total = het_total = 0
        dirty = []
        for img in images:
            ov = overlap_pairs(blocks[(n, img)])
            het = hetero_blocks(blocks[(n, img)], heights[img])
            machine[(n, img)] = (ov, het)
            ov_total += ov
            het_total += het
            if ov:
                dirty.append(f"{img}({ov})")
        L.append(f"| `{n}` | {ov_total} | {het_total} | {', '.join(dirty) or '—'} |")
    L.append("")

    if len(names) >= 2:
        a, b = names[0], names[1]
        L.append(f"**`{a}` ↔ `{b}` 블록 경계 일치율** — 구성 영역이 완전히 같은 블록 기준.")
        L.append("")
        L.append("| 이미지 | 일치 블록 | 일치율 |")
        L.append("|---|---|---|")
        tot_same = tot_rate = 0.0
        for img in images:
            same, rate = agreement(blocks[(a, img)], blocks[(b, img)])
            tot_same += same
            tot_rate += rate
            L.append(f"| {img} | {same} | {rate:.0%} |")
        L.append(f"| **전체** | **{int(tot_same)}** | **{tot_rate / len(images):.0%}** |")
        L.append("")

    # 4. 판정표 — 건수
    L.append("## 4. 판정표 — 건수")
    L.append("")
    L.append("**여기 채우는 칸은 4개뿐.** `겹침`·`이질`은 코드가 채움. 등급은 6장이 계산함.")
    L.append("")
    L.append("- **과분할** = 한 문단이 여러 블록으로 쪼개진 건")
    L.append("- **과병합** = 서로 다른 문단이 한 블록으로 붙은 건")
    L.append("- **오분류** = 역할 5종을 잘못 준 블록 수")
    L.append("- **라벨** = 제품 인쇄 글자 블록 수. 역할 오분류율 분모에서 빠짐")
    L.append("")
    L.append("**블록 구성이 완전히 같은 variant는 한쪽만 채우면 됨** — 나머지 행은"
             " `compare.py`가 복사하고 비고에 출처를 적음. 양쪽을 다르게 채우면 복사하지 않음.")
    L.append("")
    L.append("**제외 관례 — 제품 인쇄 글자(라벨)**")
    L.append("")
    L.append("| 축 | 처리 |")
    L.append("|---|---|")
    L.append("| 역할 오분류 | **세지 않음.** 블록 수를 `라벨` 칸에 적을 것 |")
    L.append("| 과분할·과병합 | **그대로 셈** — 라벨이든 아니든 블록 경계는 맞아야 함 |")
    L.append("| 역할 오분류율 분모 | **블록 수 − 라벨.** 전부 라벨이면 역할 등급은 `—` |")
    L.append("")
    L.append("제품 용기·패키지에 인쇄된 글자는 5종 중 무엇으로 불러도 의미가 없음."
             " **제품 라벨 판정 과업에서 별도로 판정함.**"
             " 인페인팅 판정 관례와 같음(`PoC_검증_계획_및_기록.md` 2.2).")
    L.append("")
    L.append(
        "| 이미지 | variant | 영역 | 블록 | "
        + " | ".join(MACHINE_COLS + COUNT_COLS)
        + " | 시각화 |"
    )
    L.append("|---|---|---|---|" + "---|" * (len(MACHINE_COLS) + len(COUNT_COLS)) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in names:
            per = next((p for p in metas[n]["per_image"] if p["image"] == img), None)
            if per is None:
                continue
            ov, het = machine[(n, img)]
            vals = counts.get((img, n), [""] * len(COUNT_COLS))
            L.append(
                f"| {img} | `{n}` | {per['regions']} | {per['blocks']} | {ov} | {het} | "
                + " | ".join(vals)
                + f" | `results/{n}/vis/{stem}.jpg` |"
            )
    L.append("")

    # 5. 덮어쓰기
    L.append("## 5. 등급 덮어쓰기 — 산식과 다르게 볼 때만")
    L.append("")
    L.append("**기본은 비워둠.** 비워두면 6장의 산식 등급이 최종임."
             " 여기 적으면 **사람 판단이 최종**이 되고 6장에 `⚠`로 표시됨.")
    L.append("")
    L.append("적어야 하는 경우")
    L.append("")
    L.append("- **주의문구 미탐** — 산식이 모르는 상한 규칙. 1건이면 역할 최대 B, 2건 이상이면 C")
    L.append("- **한 건이 치명적일 때** — 문단 여러 개가 통째로 뭉친 과병합 등."
             " 건수는 적어도 등급을 내려야 함")
    L.append("")
    L.append("| 이미지 | variant | " + " | ".join(OVERRIDE_COLS) + " |")
    L.append("|---|---|" + "---|" * len(OVERRIDE_COLS))
    for img in images:
        for n in names:
            vals = overrides.get((img, n), [""] * len(OVERRIDE_COLS))
            L.append(f"| {img} | `{n}` | " + " | ".join(vals) + " |")
    L.append("")

    # 6. 집계
    L.append("## 6. 집계")
    L.append("")
    if not counts:
        L.append("_판정 전_ — 4장에 채워진 건수 없음.")
    else:
        L.append(
            f"건수가 채워진 행 {len(counts)} / {len(images) * len(names)}. 빈 행은 계산에서 뺌."
        )
        L.append("")
        L.append("| 이미지 | variant | 판정 블록 | 병합(산식) | 병합(최종) | "
                 "역할(산식) | 역할(최종) |")
        L.append("|---|---|---|---|---|---|---|")
        tally: dict[str, dict[str, list[str]]] = {n: {"병합": [], "역할": []} for n in names}
        for (img, n), v in sorted(counts.items()):
            per = next((p for p in metas[n]["per_image"] if p["image"] == img), None)
            nb = per["blocks"] if per else 0
            try:
                osp, omg, mis = int(v[0]), int(v[1]), int(v[2])
                lab = int(v[3]) if v[3] else 0
            except ValueError:
                continue
            calc = {"병합": grade_merge(osp, omg, nb), "역할": grade_role(mis, nb, lab)}
            ov = overrides.get((img, n), ["", "", ""])
            final = {k: (ov[i] or calc[k]) for i, k in enumerate(("병합", "역할"))}
            cells = []
            for k in ("병합", "역할"):
                mark = " ⚠" if final[k] != calc[k] else ""
                cells += [calc[k], f"{final[k]}{mark}"]
                tally[n][k].append(final[k])
            L.append(f"| {img} | `{n}` | {nb - lab}/{nb} | " + " | ".join(cells) + " |")
        L.append("")
        L.append("⚠ = 5장에서 사람이 덮어씀. 사유는 5장에 있음.")
        L.append("")
        for n in names:
            for k in ("병합", "역할"):
                g = [x for x in tally[n][k] if x in {"A", "B", "C"}]
                if not g:
                    continue
                ab = sum(1 for x in g if x in {"A", "B"})
                gate = "통과" if ab / len(g) >= GATE else "미달"
                L.append(
                    f"- `{n}` {k} — A {g.count('A')} / B {g.count('B')} / C {g.count('C')} · "
                    f"**A+B {ab}/{len(g)} ({ab / len(g):.0%}) {gate}**"
                )
        L.append("")
        L.append(f"**채택 게이트 — 12장 A+B {GATE:.0%} 이상.** 텍스트 인식·인페인팅과 같은 기준."
                 " 병합·역할 두 축 모두 통과해야 채택.")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
