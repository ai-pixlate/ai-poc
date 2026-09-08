"""B. 텍스트 추출 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
등급 칸은 비워둔다. 채우는 건 사람 몫.

**이미 채워진 등급은 재실행해도 보존한다.** 기존 summary.md의 판정표를
(이미지, variant) 키로 읽어 되돌려 넣는다. variant를 추가하고 다시 돌려도
앞서 매긴 등급이 날아가지 않는다.

집계표는 채워진 등급에서 계산한다. 사람이 넣은 값의 산술 결과일 뿐,
비어 있는 칸을 추정하지 않는다.

사용법
    python compare.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

# 판정 열 — 전부 빈 칸으로 생성한다.
GRADE_COLS = ["텍스트", "bbox", "사진영역 텍스트", "사진영역 bbox", "비고"]

# 채택 후보에서 제외된 variant. 실행 결과는 근거로 남기되 판정표에서는 뺀다.
# 1·3장에는 그대로 나오므로 baseline을 판정할 때 참고용으로 볼 수 있다.
EXCLUDED: dict[str, str] = {
    "det_side_1280": "baseline과 인식 결과 완전 동일 — 판정 불필요 (2026-08-20)",
    "vl_spotting": "12장 1042초로 baseline의 약 300배 — 속도상 채택 제외 (2026-08-20)",
}


def esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def read_existing_grades() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 등급을 회수한다.

    행 형식: | {이미지} | `{variant}` | {영역수} | 등급 4칸 | 비고 | 시각화 |
    """
    if not OUT.exists():
        return {}
    grades: dict[tuple[str, str], list[str]] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # 이미지 + variant + 영역수 + 등급열 + 시각화 = GRADE_COLS + 4
        if len(cells) != len(GRADE_COLS) + 4:
            continue
        img, variant = cells[0], cells[1]
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[3 : 3 + len(GRADE_COLS)]
        if any(vals):
            grades[(img, variant.strip("`"))] = vals
    return grades


def ratio(values: list[str]) -> str:
    """A+B 비율. `-`(해당 영역 없음)는 분모에서 뺀다. 미판정이 있으면 진행률만 표시."""
    graded = [v.upper() for v in values if v.upper() in {"A", "B", "C"}]
    skipped = sum(1 for v in values if v == "-")
    total = len(values) - skipped
    if total == 0:
        return "-"
    if len(graded) < total:
        return f"판정 {len(graded)}/{total}"
    ab = sum(1 for v in graded if v in {"A", "B"})
    return f"{ab}/{total} ({ab / total * 100:.0f}%)"


def load() -> tuple[list[str], dict[str, dict], dict[str, dict[str, list[dict]]]]:
    variants = sorted(p.name for p in RESULTS.iterdir() if (p / "meta.json").exists())
    metas, regions = {}, {}
    for v in variants:
        metas[v] = json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8"))
        regions[v] = {}
        for f in sorted((RESULTS / v / "regions").glob("*.json")):
            payload = json.loads(f.read_text(encoding="utf-8"))
            regions[v][payload["image"]] = payload["regions"]
    return variants, metas, regions


def main() -> None:
    if not RESULTS.exists():
        raise SystemExit("results/ 없음. run.py 먼저 실행.")
    variants, metas, regions = load()
    if not variants:
        raise SystemExit("완료된 variant 없음.")
    kept = read_existing_grades()

    images = sorted(
        {img for v in variants for img in regions[v]},
        key=lambda n: (len(Path(n).stem), Path(n).stem),
    )

    L: list[str] = []
    L.append("# B. 텍스트 추출 — variant 비교")
    L.append("")
    L.append("> 자동 생성 파일. `compare.py` 재실행 시 덮어씀 — 등급은 여기 말고 PoC 문서에 옮겨 적을 것.")
    L.append("")

    # 1. 실행 요약
    L.append("## 1. 실행 요약")
    L.append("")
    L.append("| variant | 이미지 | 검출 영역 | 이미지당 평균 | 초기화(s) | 인식(s) | 조건 |")
    L.append("|---|---|---|---|---|---|---|")
    for v in variants:
        m = metas[v]
        avg = m["total_regions"] / m["images"] if m["images"] else 0
        cond = ", ".join(f"{k}={val}" for k, val in m["kwargs"].items() if not k.startswith("use_"))
        mark = " *(제외)*" if v in EXCLUDED else ""
        L.append(
            f"| `{v}`{mark} | {m['images']} | {m['total_regions']} | {avg:.1f} | "
            f"{m['init_sec']} | {m['total_sec']} | {esc(cond)} |"
        )
    L.append("")
    L.append("> 검출 영역 수는 많다고 좋은 게 아님. 과분할·오검출도 같이 늘어남. 시각화로 확인 필요.")
    L.append("")

    # 2. 판정표
    graded = [v for v in variants if v not in EXCLUDED]

    L.append("## 2. 판정표 (육안 A/B/C — 빈 칸 채울 것)")
    L.append("")
    L.append("- `사진영역` 열: 사진·그라데이션 배경 위 글자만 따로 본 등급. 해당 영역이 없으면 `-`")
    L.append("- 시각화 이미지를 띄워놓고 3장 텍스트와 대조하며 매길 것")
    L.append("")
    L.append("**등급 기준** (PoC 문서 2.1)")
    L.append("")
    L.append("| 등급 | 텍스트 열 | bbox 열 |")
    L.append("|---|---|---|")
    L.append("| **A** | 대부분 정확, 오탈자 거의 없음 — 그대로 번역에 넘겨도 됨 | 텍스트 영역을 정확히 감쌈 |")
    L.append("| **B** | 일부 오탈자 있으나 1차 검수로 고칠 수 있는 수준 | 약간 어긋나지만 마스크 확장으로 흡수 가능 |")
    L.append("| **C** | 오탈자 과다하거나 인식 실패 — 사용 불가 | 크게 빗나가거나 영역 누락 |")
    L.append("| **-** | 사진·그라데이션 배경 위 글자가 없는 이미지 (`사진영역` 두 열 전용) | 〃 |")
    L.append("")
    L.append("> A와 B를 가르는 선은 **1차 검수로 고칠 수 있는가**. C는 손보느니 다시 뽑는 게 빠른 상태.")
    L.append("> 집계는 A+B를 묶어 세므로 A/B 구분보다 **B와 C의 경계**가 결과를 좌우한다.")
    if EXCLUDED:
        L.append("")
        L.append("**판정 대상에서 제외된 variant** — 실행 결과는 1·3장에 남아 있으니 참고용으로 볼 것")
        L.append("")
        L.append("| variant | 제외 사유 |")
        L.append("|---|---|")
        for v, why in EXCLUDED.items():
            if v in variants:
                L.append(f"| `{v}` | {why} |")
    L.append("")
    L.append("| 이미지 | variant | 영역 | " + " | ".join(GRADE_COLS) + " | 시각화 |")
    L.append("|---|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for img in images:
        stem = Path(img).stem
        for v in graded:
            n = len(regions[v].get(img, []))
            link = f"[보기](results/{v}/vis/{stem}.jpg)"
            vals = kept.get((img, v), [" "] * len(GRADE_COLS))
            L.append(f"| {img} | `{v}` | {n} | " + " | ".join(vals) + f" | {link} |")
    L.append("")
    L.append("**집계** — 위 판정표에서 자동 계산됨. 직접 채우지 말 것")
    L.append("")
    L.append("| variant | 텍스트 | bbox | 사진영역 텍스트 | 사진영역 bbox | 70% 통과 |")
    L.append("|---|---|---|---|---|---|")
    for v in graded:
        cols = [[kept.get((img, v), [""] * len(GRADE_COLS))[i] for img in images] for i in range(4)]
        cells = [ratio(c) for c in cols]
        done = all("판정" not in c for c in cells)
        pct = [c for c in cells if c not in {"-"} and "판정" not in c]
        if not done or not pct:
            gate = "판정 미완"
        else:
            gate = "O" if all(int(c.split("(")[1].rstrip("%)")) >= 70 for c in pct) else "X"
        L.append(f"| `{v}` | " + " | ".join(cells) + f" | {gate} |")
    L.append("")
    L.append("> `70% 통과`는 네 열이 **모두** 70% 이상일 때만 O. 한 열이라도 미달이면 X — 어느 축이 걸렸는지는 왼쪽 칸으로 확인할 것.")
    L.append("")

    # 3. 인식 텍스트 나란히 보기
    L.append("## 3. 인식 텍스트 나란히 보기")
    L.append("")
    L.append("괄호 안은 인식 신뢰도. 행 번호는 시각화 이미지의 빨간 번호와 같다.")
    L.append("**variant마다 검출 영역이 다르므로 같은 행이 같은 위치를 뜻하지는 않는다.** 세로로 훑어 읽을 것.")
    L.append("")
    for img in images:
        stem = Path(img).stem
        L.append(f"### {img}")
        L.append("")
        L.append(" · ".join(f"[{v} 시각화](results/{v}/vis/{stem}.jpg)" for v in variants))
        L.append("")
        rows = max((len(regions[v].get(img, [])) for v in variants), default=0)
        L.append("| # | " + " | ".join(f"`{v}`" for v in variants) + " |")
        L.append("|---|" + "---|" * len(variants))
        for i in range(rows):
            cells = []
            for v in variants:
                rs = regions[v].get(img, [])
                if i < len(rs):
                    r = rs[i]
                    score = f" ({r['score']:.2f})" if r.get("score") is not None else ""
                    cells.append(esc(r["text"]) + score)
                else:
                    cells.append("")
            L.append(f"| {i + 1} | " + " | ".join(cells) + " |")
        L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"작성 완료: {OUT}")
    print(f"  variant {len(variants)}종, 이미지 {len(images)}장")
    excluded = [v for v in variants if v in EXCLUDED]
    if excluded:
        print(f"  판정 제외: {', '.join(excluded)}")
    filled = sum(1 for (_, v) in kept if v in graded)
    total = len(images) * len(graded)
    print(f"  판정 {filled}/{total}행" + (" (기존 등급 보존됨)" if filled else ""))


if __name__ == "__main__":
    main()
