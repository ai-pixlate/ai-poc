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
    python compare.py --sample golden   # 골든 샘플 섹션 — summary_golden.md · results/golden/llm_assist/board/

--sample golden
    heuristic_v2 · llm_assist 골든 결과를 읽어 섹션 단위 판정표를 만든다.
    판정 대상은 llm_assist. 산식·제외 관례는 12장과 같다.
    라벨 칸은 제품 라벨 판정(단계 3) 검토 확정 정답으로 채운다 — 채우기 전엔 역할 등급 계산 안 함.
    글자 없는 섹션(B_ocr summary_golden.md 텍스트·bbox `-`)은 분모에서 뺀다.
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
        # 역할까지 같아야 복사한다. 구성만 같고 역할이 다르면 오분류 건수가 달라진다.
        sig = {
            n: {(tuple(b["regions"]), b["role"]) for b in blocks[(n, img)]} for n in names
        }
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


def main_default() -> None:
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


# ---------------------------------------------------------------- 골든 샘플 — 섹션 단위

GOLDEN = RESULTS / "golden"
GOLDEN_OUT = HERE / "summary_golden.md"
GOLDEN_NAMES = ("heuristic_v2", "llm_assist")
JUDGED = "llm_assist"  # 판정 대상 — 채택 파이프라인
GOLDEN_REGIONS = HERE.parents[1] / "poc" / "B_ocr" / "results" / "golden" / "baseline" / "regions"
OCR_SUMMARY = HERE.parents[1] / "poc" / "B_ocr" / "summary_golden.md"  # 단계 1 판정 — 글자 없는 섹션
BOARD_PANEL_W = 640

import re  # noqa: E402

SID = re.compile(r"^A\d+_\d{3}_\d{3}$")
PIPE = re.compile(r"(?<!\\)\|")


def g_cells(line: str) -> list[str]:
    return [c.strip() for c in PIPE.split(line.strip().strip("|"))]


def g_esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " / ").strip()


def no_text_sections() -> set[str]:
    """단계 1 판정표에서 텍스트·bbox가 모두 `-`인 섹션 — 글자 없는 섹션, 분모 제외."""
    if not OCR_SUMMARY.exists():
        return set()
    out = set()
    for line in OCR_SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.startswith("|"):
            c = g_cells(line)
            if len(c) == 9 and SID.match(c[0]) and c[3] == "-" and c[4] == "-":
                out.add(c[0])
    return out


def read_golden_tables() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """채워진 건수(11열 행)·덮어쓰기(4열 행)를 섹션 id 키로 회수."""
    counts: dict[str, list[str]] = {}
    overrides: dict[str, list[str]] = {}
    if not GOLDEN_OUT.exists():
        return counts, overrides
    for line in GOLDEN_OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = g_cells(line)
        if not c or not SID.match(c[0]):
            continue
        if len(c) == 5 + len(COUNT_COLS) + 1:
            vals = c[5 : 5 + len(COUNT_COLS)]
            if any(vals):
                counts[c[0]] = vals
        elif len(c) == 1 + len(OVERRIDE_COLS):
            vals = c[1:]
            if any(vals):
                overrides[c[0]] = vals
    return counts, overrides


def make_board(sid: str, blocks: list[dict], out: Path) -> None:
    """판정 대지 — 왼쪽 llm_assist vis, 오른쪽 블록 번호·역할·텍스트·출처 휴리스틱 블록."""
    from PIL import Image, ImageDraw

    sys.path.insert(0, str(HERE))
    import run as H  # noqa: E402 — 폰트·색만 쓴다

    vis = Image.open(GOLDEN / JUDGED / "vis" / f"{sid}.jpg").convert("RGB")
    font = H._font(15)
    lh = 21
    probe = ImageDraw.Draw(vis)
    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"{sid}  {JUDGED}  블록 {len(blocks)}", (0, 0, 0)),
        ("번호 = 왼쪽 라벨 번호 · ← h = heuristic_v2 블록 번호", (110, 110, 110)),
        ("", (0, 0, 0)),
    ]
    for i, b in enumerate(blocks, 1):
        text = f"{i} [{b['role']}] " + b["text"].replace("\n", " / ") + f"   ← h{','.join(map(str, b.get('from', [])))}"
        cur = ""
        for ch in text:
            if cur and probe.textlength(cur + ch, font=font) > BOARD_PANEL_W - 24:
                lines.append((cur, H.ROLE_COLOR[b["role"]]))
                cur = "    " + ch
            else:
                cur += ch
        lines.append((cur, H.ROLE_COLOR[b["role"]]))
    h = max(vis.height, 12 + lh * len(lines) + 12)
    board = Image.new("RGB", (vis.width + BOARD_PANEL_W, h), (255, 255, 255))
    board.paste(vis, (0, 0))
    d = ImageDraw.Draw(board)
    d.line([(vis.width, 0), (vis.width, h)], fill=(180, 180, 180), width=2)
    y = 12
    for seg, col in lines:
        d.text((vis.width + 12, y), seg, fill=col, font=font)
        y += lh
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out, quality=90)


def main_golden() -> None:
    metas = {}
    for n in GOLDEN_NAMES:
        p = GOLDEN / n / "meta.json"
        if not p.exists():
            raise SystemExit(f"{p} 없음 — run.py / run_llm.py --sample golden 먼저")
        metas[n] = json.loads(p.read_text(encoding="utf-8"))
    sids = [p["section"] for p in metas[JUDGED]["per_section"]]
    blocks = {(n, s): json.loads((GOLDEN / n / "blocks" / f"{s}.json").read_text(encoding="utf-8"))["blocks"]
              for n in GOLDEN_NAMES for s in sids}
    heights = {}
    for s in sids:
        rs = json.loads((GOLDEN_REGIONS / f"{s}.json").read_text(encoding="utf-8"))["regions"]
        heights[s] = {i: r["bbox"][3] - r["bbox"][1] for i, r in enumerate(rs)}
    per = {p["section"]: p for p in metas[JUDGED]["per_section"]}
    empty = no_text_sections()
    counts, overrides = read_golden_tables()
    rel = f"results/golden/{JUDGED}"

    for s in sids:
        make_board(s, blocks[(JUDGED, s)], GOLDEN / JUDGED / "board" / f"{s}.jpg")

    L: list[str] = []
    L.append("# 줄·문단 병합 + 역할 분류 — 골든 샘플 섹션 판정")
    L.append("")
    L.append("> `compare.py --sample golden`이 생성함. 재실행해도 **채운 건수·덮어쓰기는 보존함.**")
    L.append("> 계획 `PoC_골든샘플_재실행_계획.md` 단계 2. 입력은 단계 1 섹션 영역(`B_ocr` golden). 12장 결과(`summary.md`)는 건드리지 않음.")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| variant | 조건 | 섹션 | 영역 | 블록 | 토큰 in / out | 비용 | 소요 | 응답 적용 실패 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for n in GOLDEN_NAMES:
        m = metas[n]
        cfg = " ".join(f"`{k}={v}`" for k, v in m["cfg"].items())
        tok = f"{m['tokens']['in']:,} / {m['tokens']['out']:,}" if "tokens" in m else "—"
        cost = f"${m['cost_usd']:.4f}" if "cost_usd" in m else "0"
        errs = len(m.get("errors", [])) if n == JUDGED else "—"
        L.append(f"| `{n}` | {cfg} | {m['sections']} | {m['total_regions']:,} | {m['total_blocks']:,} | "
                 f"{tok} | {cost} | {m['total_sec']}s | {errs} |")
    L.append("")
    for e in metas[JUDGED].get("errors", []):
        L.append(f"- 적용 실패 `{e['section']}` — {g_esc(e['error'])}")
    if metas[JUDGED].get("errors"):
        L.append("")

    # 2. 역할 분포
    L.append("## 2. 역할 분포 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("| 표본 | variant | " + " | ".join(ROLES) + " | 블록 |")
    L.append("|---|---|" + "---|" * (len(ROLES) + 1))
    for n in GOLDEN_NAMES:
        r = metas[n]["roles"]
        L.append(f"| 골든 102섹션 | `{n}` | " + " | ".join(str(r.get(x, 0)) for x in ROLES) + f" | {metas[n]['total_blocks']:,} |")
    old = RESULTS / JUDGED / "meta.json"
    if old.exists():
        m12 = json.loads(old.read_text(encoding="utf-8"))
        L.append(f"| 12장 | `{JUDGED}` | " + " | ".join(str(m12["roles"].get(x, 0)) for x in ROLES) + f" | {m12['total_blocks']} |")
    L.append("")

    # 3. 가격·주의문구
    L.append("## 3. 가격 · 주의문구 블록 (확인 항목 — 12장에 각 1·4건뿐이던 한계)")
    L.append("")
    L.append(f"`{JUDGED}`가 가격·주의문구로 매긴 블록 전부. 정오는 5장 판정에서 봄. 미탐은 대지에서 찾아야 함.")
    L.append("")
    L.append("| 섹션 | 블록 | 역할 | 텍스트 |")
    L.append("|---|---|---|---|")
    hit = 0
    for s in sids:
        for i, b in enumerate(blocks[(JUDGED, s)], 1):
            if b["role"] in ("가격", "주의문구"):
                hit += 1
                t = g_esc(b["text"])
                L.append(f"| `{s}` | {i} | {b['role']} | {t[:120] + ('…' if len(t) > 120 else '')} |")
    if not hit:
        L.append("| — | — | — | 없음 |")
    L.append("")

    # 4. 보조 지표
    L.append("## 4. 보조 지표 (정답 없이 계산 — 정오 아님)")
    L.append("")
    L.append("| variant | 겹침 | 이질 | 겹침 상위 섹션 |")
    L.append("|---|---|---|---|")
    machine = {}
    for n in GOLDEN_NAMES:
        ov_t = het_t = 0
        dirty = []
        for s in sids:
            ov = overlap_pairs(blocks[(n, s)])
            het = hetero_blocks(blocks[(n, s)], heights[s])
            machine[(n, s)] = (ov, het)
            ov_t += ov
            het_t += het
            if ov:
                dirty.append((ov, s))
        top = ", ".join(f"`{s}`({ov})" for ov, s in sorted(dirty, reverse=True)[:5]) or "—"
        L.append(f"| `{n}` | {ov_t} | {het_t} | {top} |")
    L.append("")
    same_t = rate_t = 0.0
    changed = []
    for s in sids:
        same, rate = agreement(blocks[("heuristic_v2", s)], blocks[(JUDGED, s)])
        same_t += same
        rate_t += rate
        if rate < 1:
            changed.append(s)
    L.append(f"**`heuristic_v2` ↔ `{JUDGED}` 블록 경계 일치** — 일치 블록 {int(same_t):,} · 섹션 평균 {rate_t / len(sids):.0%} · "
             f"LLM이 경계를 바꾼 섹션 {len(changed)}/{len(sids)}")
    L.append("")

    # 5. 판정표
    L.append("## 5. 판정표 — 건수 (섹션 단위)")
    L.append("")
    L.append(f"판정 대상 `{JUDGED}`. 대지 `{rel}/board/{{섹션}}.jpg` — 왼쪽 블록 박스·역할 색(회색 = 원본 영역), 오른쪽 블록별 역할·텍스트·출처 휴리스틱 블록.")
    L.append("")
    L.append("- **과분할** = 한 문단이 여러 블록으로 쪼개진 건 · **과병합** = 서로 다른 문단이 한 블록으로 붙은 건")
    L.append("- **오분류** = 역할 5종을 잘못 준 블록 수 — **라벨 블록은 세지 않음**")
    L.append("- **라벨** = 제품 인쇄 글자 블록 수. **단계 3 검토 확정 정답 기준으로 채움** — 채우기 전엔 역할 등급 계산 안 함")
    L.append("- 등급 산식(12장 확정): 병합 = (과분할 + 과병합×2) ÷ 블록 ≤10% & 과병합 0 → A, ≤25% → B, 그 외 C (블록 10개 미만은 1건까지 A) · 역할 = 오분류 ÷ (블록 − 라벨) ≤10% A, ≤25% B")
    if empty:
        L.append(f"- **글자 없는 섹션(단계 1 판정 `-`) — 분모 제외:** " + ", ".join(f"`{s}`" for s in sorted(empty)))
    L.append("- 판정 주체: Claude 1차 판정(비고에 \"Claude 육안 판정\") → 예람님 검토")
    L.append("")
    L.append("| 섹션 | 영역 | 블록 | " + " | ".join(MACHINE_COLS + COUNT_COLS) + " | 대지 |")
    L.append("|---|---|---|" + "---|" * (len(MACHINE_COLS) + len(COUNT_COLS)) + "---|")
    for s in sids:
        ov, het = machine[(JUDGED, s)]
        vals = counts.get(s, [" "] * len(COUNT_COLS))
        L.append(f"| {s} | {per[s]['regions']} | {per[s]['blocks']} | {ov} | {het} | " + " | ".join(vals)
                 + f" | [보기]({rel}/board/{s}.jpg) |")
    L.append("")

    # 6. 덮어쓰기
    L.append("## 6. 등급 덮어쓰기 — 산식과 다르게 볼 때만")
    L.append("")
    L.append("- **주의문구 미탐** — 1건이면 역할 최대 B, 2건 이상이면 C (산식이 모르는 상한)")
    L.append("- **한 건이 치명적일 때** — 문단 여러 개가 통째로 뭉친 과병합 등")
    L.append("- 채울 행만 추가: `| {섹션} | 병합 | 역할 | 사유 |`")
    L.append("")
    L.append("| 섹션 | " + " | ".join(OVERRIDE_COLS) + " |")
    L.append("|---|" + "---|" * len(OVERRIDE_COLS))
    for s in sids:
        if s in overrides:
            L.append(f"| {s} | " + " | ".join(overrides[s]) + " |")
    L.append("")

    # 7. 집계
    L.append("## 7. 집계")
    L.append("")
    judged = [s for s in sids if s not in empty]
    if not any(s in counts for s in judged):
        L.append("_판정 전_ — 5장에 채워진 건수 없음.")
    else:
        L.append("| 섹션 | 판정 블록 | 병합(산식) | 병합(최종) | 역할(산식) | 역할(최종) |")
        L.append("|---|---|---|---|---|---|")
        tally = {"병합": [], "역할": []}
        for s in judged:
            v = counts.get(s)
            if not v:
                continue
            nb = per[s]["blocks"]
            try:
                osp, omg = int(v[0]), int(v[1])
            except ValueError:
                continue
            calc = {"병합": grade_merge(osp, omg, nb), "역할": "라벨 미정"}
            lab_ok = v[3] != "" and v[2] != ""
            if lab_ok:
                try:
                    calc["역할"] = grade_role(int(v[2]), nb, int(v[3]))
                except ValueError:
                    lab_ok = False
            ov = overrides.get(s, ["", "", ""])
            final = {k: (ov[i] or calc[k]) for i, k in enumerate(("병합", "역할"))}
            cells = []
            for k in ("병합", "역할"):
                mark = " ⚠" if final[k] != calc[k] else ""
                cells += [calc[k], f"{final[k]}{mark}"]
                tally[k].append(final[k])
            lab = int(v[3]) if lab_ok else 0
            L.append(f"| {s} | {nb - lab}/{nb} | " + " | ".join(cells) + " |")
        L.append("")
        L.append("⚠ = 6장에서 덮어씀.")
        L.append("")
        for k in ("병합", "역할"):
            g = [x for x in tally[k] if x in {"A", "B", "C"}]
            pending = len(judged) - len(g)
            if not g:
                L.append(f"- {k} — 판정 전 (대상 {len(judged)}섹션)")
                continue
            ab = sum(1 for x in g if x in {"A", "B"})
            gate = "통과" if ab / len(g) >= GATE else "미달"
            L.append(f"- {k} — A {g.count('A')} / B {g.count('B')} / C {g.count('C')} · **A+B {ab}/{len(g)} ({ab / len(g):.0%}) {gate}**"
                     + (f" · 미판정 {pending}" if pending else ""))
        L.append("")
        L.append(f"**게이트 — 섹션 A+B {GATE:.0%}.** 병합·역할 두 축 모두. 글자 없는 섹션 분모 제외.")
    L.append("")

    GOLDEN_OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {GOLDEN_OUT}  (섹션 {len(sids)} · 대지 {rel}/board/ · 건수 채움 {len(counts)})")


def main() -> None:
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", choices=("default", "golden"), default="default")
    args = ap.parse_args()
    if args.sample == "golden":
        main_golden()
    else:
        main_default()


if __name__ == "__main__":
    main()
