"""줄·문단 병합 + 역할 분류 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
등급 칸은 비워둔다. 채우는 건 사람 몫.

**정답 라벨을 만들지 않기로 함(2026-09-08).** 병합·역할의 정오는 사람이
육안 A/B/C로 판정한다. 대신 정답 없이도 계산되는 보조 지표 3종을 붙여
어느 이미지를 먼저 볼지 고르는 데 쓴다. 보조 지표는 **정오가 아니다.**

  겹침  — 블록 bbox끼리 겹치는 쌍의 수. 과병합에서도 늘지만 원래 겹쳐
          배치된 레이아웃(제품 패키지 사진 등)에서도 는다. 어느 쪽인지는
          vis를 봐야 갈린다.
  이질  — 한 블록 안에서 글자 높이가 1.5배 넘게 벌어진 블록 수.
          h_ratio가 직접 누르는 값이라 variant 간 차이는 설계상 당연하다.
          쓸모는 총수가 아니라 **어느 블록인지**에 있다.
  일치율 — variant 간 블록 경계가 같은 비율. 임계 민감도

**이미 채워진 등급은 재실행해도 보존한다.** 기존 summary.md의 판정표를
(이미지, variant) 키로 읽어 되돌려 넣는다.

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

# 기계 집계 열 — 코드가 채운다.
MACHINE_COLS = ["겹침", "이질"]
# 판정 열 — 전부 빈 칸으로 생성한다.
#   병합 / 역할 : 이미지 단위 A/B/C 육안 등급
#   과분할·과병합·오분류 : 사람이 vis/ 를 보고 센 건수
GRADE_COLS = ["병합", "역할", "과분할", "과병합", "오분류", "비고"]

# 한 블록 안에서 이 배수를 넘게 글자 높이가 벌어지면 이질로 센다.
HETERO_RATIO = 1.5

# 등급 산식 (2026-09-08 확정)
#   과병합에 2배 가중 — 과분할은 조각이 제자리에 남아 배치가 유지되지만,
#   과병합은 서로 다른 자리의 문단이 한 박스가 돼 되돌릴 수 없다.
OVER_MERGE_WEIGHT = 2
MERGE_A, MERGE_B = 0.10, 0.25     # 가중 오류율 상한
ROLE_A, ROLE_B = 0.10, 0.25       # 역할 오분류율 상한
SMALL_BLOCKS = 10                 # 블록이 이보다 적으면 1건까지 A로 봐준다


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


def grade_role(mis: int, blocks: int) -> str:
    """오분류 건수 → 역할 등급. 주의문구 미탐 상한은 사람이 비고에 적고 직접 내린다."""
    rate = mis / max(1, blocks)
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


# ---------------------------------------------------------------- 판정 보존

def read_existing() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 등급을 회수한다.

    행 형식: | 이미지 | `variant` | 영역 | 블록 | 기계 2칸 | 판정 6칸 | 시각화 |
    """
    if not OUT.exists():
        return {}
    width = 4 + len(MACHINE_COLS) + len(GRADE_COLS) + 1
    start = 4 + len(MACHINE_COLS)
    got: dict[tuple[str, str], list[str]] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != width:
            continue
        img, variant = cells[0], cells[1]
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[start : start + len(GRADE_COLS)]
        if any(vals):
            got[(img, variant.strip("`"))] = vals
    return got


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    names = variants()
    if not names:
        raise SystemExit(f"{RESULTS} 아래 실행 결과 없음 — run.py 를 먼저 돌릴 것")

    metas = {n: json.loads((RESULTS / n / "meta.json").read_text(encoding="utf-8")) for n in names}
    existing = read_existing()
    images = [p["image"] for p in metas[names[0]]["per_image"]]

    # 블록·영역 높이 적재
    blocks: dict[tuple[str, str], list[dict]] = {}
    heights: dict[str, dict[int, int]] = {}
    src = HERE.parents[1] / "poc" / "B_ocr" / "results" / "baseline" / "regions"
    for img in images:
        rs = json.loads((src / f"{Path(img).stem}.json").read_text(encoding="utf-8"))["regions"]
        heights[img] = {i: r["bbox"][3] - r["bbox"][1] for i, r in enumerate(rs)}
        for n in names:
            blocks[(n, img)] = load_blocks(n, img)

    L: list[str] = []
    L.append("# 줄·문단 병합 + 역할 분류 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **판정 칸은 사람이 채움.**")
    L.append("> 입력은 텍스트 인식 `baseline` 영역. 판정 기준·계획은 `PoC_추가검증_계획.md`.")
    L.append("> **정답 라벨 없음** — 병합·역할의 정오는 육안 A/B/C로 판정함.")
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
    per_var_machine: dict[tuple[str, str], tuple[int, int]] = {}
    for n in names:
        ov_total = het_total = 0
        dirty = []
        for img in images:
            ov = overlap_pairs(blocks[(n, img)])
            het = hetero_blocks(blocks[(n, img)], heights[img])
            per_var_machine[(n, img)] = (ov, het)
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

    # 4. 판정표
    L.append("## 4. 판정표")
    L.append("")
    L.append("`병합`·`역할`은 이미지 단위 A/B/C. 나머지는 건수. **겹침·이질은 코드가 채움.**")
    L.append("")
    L.append("- **과분할** = 한 문단이 여러 블록으로 쪼개진 건")
    L.append("- **과병합** = 서로 다른 문단이 한 블록으로 붙은 건")
    L.append("- **오분류** = 역할 5종을 잘못 준 블록 수")
    L.append("")
    L.append("**등급 기준** — 건수만 채우면 6장이 산식 등급을 계산함.")
    L.append("")
    L.append("| 축 | A | B | C |")
    L.append("|---|---|---|---|")
    L.append(
        f"| 병합 | 가중 오류율 ≤ {MERGE_A:.0%} **그리고 과병합 0** | ≤ {MERGE_B:.0%} | 그 외 |"
    )
    L.append(f"| 역할 | 오분류율 ≤ {ROLE_A:.0%} | ≤ {ROLE_B:.0%} | 그 외 |")
    L.append("")
    L.append(
        f"- 가중 오류 = 과분할 + 과병합 × {OVER_MERGE_WEIGHT}. "
        "**과병합이 더 무거움** — 과분할은 조각이 제자리에 남지만 과병합은 되돌릴 수 없음"
    )
    L.append(f"- 블록 {SMALL_BLOCKS}개 미만 이미지는 가중 오류 1건까지 A (과병합 0일 때만)")
    L.append(
        "- **주의문구를 다른 역할로 준 건(미탐)이 1건 있으면 역할은 최대 B, 2건 이상이면 C.** "
        "규제 판정이 통째로 빠지므로 산식보다 우선함 — 비고에 적고 사람이 직접 내릴 것"
    )
    L.append("")
    L.append(
        "| 이미지 | variant | 영역 | 블록 | "
        + " | ".join(MACHINE_COLS + GRADE_COLS)
        + " | 시각화 |"
    )
    L.append("|---|---|---|---|" + "---|" * (len(MACHINE_COLS) + len(GRADE_COLS)) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in names:
            per = next((p for p in metas[n]["per_image"] if p["image"] == img), None)
            if per is None:
                continue
            ov, het = per_var_machine[(n, img)]
            vals = existing.get((img, n), [""] * len(GRADE_COLS))
            L.append(
                f"| {img} | `{n}` | {per['regions']} | {per['blocks']} | {ov} | {het} | "
                + " | ".join(vals)
                + f" | `results/{n}/vis/{stem}.jpg` |"
            )
    L.append("")

    # 5. variant 간 블록 수 차이 — 볼 순서 정하는 용도
    if len(names) >= 2:
        a, b = names[0], names[1]
        L.append(f"## 5. `{a}` vs `{b}` — 블록 수 차이")
        L.append("")
        L.append("차이가 큰 이미지부터 보면 임계 변경의 효과를 빨리 판단할 수 있음.")
        L.append("")
        L.append(f"| 이미지 | `{a}` | `{b}` | 차이 |")
        L.append("|---|---|---|---|")
        rows = []
        for img in images:
            pa = next((p for p in metas[a]["per_image"] if p["image"] == img), None)
            pb = next((p for p in metas[b]["per_image"] if p["image"] == img), None)
            if pa and pb:
                rows.append((img, pa["blocks"], pb["blocks"], pb["blocks"] - pa["blocks"]))
        for img, x, y, d in sorted(rows, key=lambda r: -abs(r[3])):
            L.append(f"| {img} | {x} | {y} | {d:+d} |")
        L.append("")

    # 6. 집계 — 채워진 칸에서만
    L.append("## 6. 집계")
    L.append("")
    if not existing:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L.append(f"채워진 행 {len(existing)} / {len(images) * len(names)}. 빈 칸은 계산에서 뺌.")
        L.append("")
        L.append("| 이미지 | variant | 병합(입력) | 병합(산식) | 역할(입력) | 역할(산식) |")
        L.append("|---|---|---|---|---|---|")
        tally: dict[str, list[str]] = {n: [] for n in names}
        for (img, n), v in sorted(existing.items()):
            per = next((p for p in metas[n]["per_image"] if p["image"] == img), None)
            nb = per["blocks"] if per else 0
            try:
                osp, omg, mis = int(v[2]), int(v[3]), int(v[4])
            except ValueError:
                continue
            gm, gr = grade_merge(osp, omg, nb), grade_role(mis, nb)
            mark = lambda got, calc: f"{got or '—'}{'' if got in ('', calc) else ' ⚠'}"
            L.append(
                f"| {img} | `{n}` | {mark(v[0], gm)} | {gm} | {mark(v[1], gr)} | {gr} |"
            )
            tally[n].append(v[0] or gm)
        L.append("")
        L.append("⚠ = 입력 등급과 산식 등급이 다름. 사람 판단이 우선이며 사유를 비고에 적을 것.")
        L.append("")
        for n in names:
            g = tally[n]
            if g:
                ab = sum(1 for x in g if x in {"A", "B"})
                L.append(
                    f"- `{n}` 병합 — A {g.count('A')} / B {g.count('B')} / C {g.count('C')} · "
                    f"**A+B {ab}/{len(g)} ({ab / len(g):.0%})**"
                )
        L.append("")
        L.append("**채택 게이트 — 12장 A+B 70% 이상.** 텍스트 인식·인페인팅과 같은 기준.")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
