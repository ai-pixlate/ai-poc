"""줄·문단 병합 + 역할 분류 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
등급·건수 칸은 비워둔다. 채우는 건 사람 몫.

**이미 채워진 판정은 재실행해도 보존한다.** 기존 summary.md의 판정표를
(이미지, variant) 키로 읽어 되돌려 넣는다.

집계는 채워진 칸에서만 계산한다. 빈 칸을 추정하지 않는다.

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

# 판정 열 — 전부 빈 칸으로 생성한다.
#   병합 / 역할 : 이미지 단위 A/B/C 육안 등급
#   과분할·과병합·오분류 : 사람이 vis/ 를 보고 센 건수
GRADE_COLS = ["병합", "역할", "과분할", "과병합", "오분류", "비고"]


def variants() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(
        (d.name for d in RESULTS.iterdir() if (d / "meta.json").exists()),
        key=lambda n: n,
    )


def read_existing() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 칸을 회수한다.

    행 형식: | {이미지} | `{variant}` | {영역} | {블록} | 판정 6칸 | 시각화 |
    """
    if not OUT.exists():
        return {}
    got: dict[tuple[str, str], list[str]] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(GRADE_COLS) + 5:  # 이미지 variant 영역 블록 + 판정 + 시각화
            continue
        img, variant = cells[0], cells[1]
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
    existing = read_existing()

    L: list[str] = []
    L.append("# 줄·문단 병합 + 역할 분류 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **판정 칸은 사람이 채움.**")
    L.append("> 입력은 텍스트 인식 `baseline` 영역. 판정 기준·계획은 `PoC_추가검증_계획.md`.")
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

    # 2. 역할 분포 — 기계 집계. 정오는 아님
    L.append("## 2. 역할 분포 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("| variant | " + " | ".join(ROLES) + " |")
    L.append("|---|" + "---|" * len(ROLES))
    for n in names:
        r = metas[n]["roles"]
        L.append(f"| `{n}` | " + " | ".join(str(r.get(x, 0)) for x in ROLES) + " |")
    L.append("")

    # 3. 판정표
    L.append("## 3. 판정표")
    L.append("")
    L.append("`병합`·`역할`은 이미지 단위 A/B/C. 나머지는 건수.")
    L.append("")
    L.append("- **과분할** = 한 문단이 여러 블록으로 쪼개진 건")
    L.append("- **과병합** = 서로 다른 문단이 한 블록으로 붙은 건")
    L.append("- **오분류** = 역할 5종을 잘못 준 블록 수")
    L.append("")
    header = "| 이미지 | variant | 영역 | 블록 | " + " | ".join(GRADE_COLS) + " | 시각화 |"
    L.append(header)
    L.append("|---|---|---|---|" + "---|" * len(GRADE_COLS) + "---|")

    images = [p["image"] for p in metas[names[0]]["per_image"]]
    for img in images:
        stem = Path(img).stem
        for n in names:
            per = next((p for p in metas[n]["per_image"] if p["image"] == img), None)
            if per is None:
                continue
            vals = existing.get((img, n), [""] * len(GRADE_COLS))
            L.append(
                f"| {img} | `{n}` | {per['regions']} | {per['blocks']} | "
                + " | ".join(vals)
                + f" | `results/{n}/vis/{stem}.jpg` |"
            )
    L.append("")

    # 4. variant 간 차이 — 어느 이미지를 먼저 볼지 고르는 용도
    if len(names) >= 2:
        a, b = names[0], names[1]
        L.append(f"## 4. `{a}` vs `{b}` — 블록 수 차이")
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

    # 5. 집계 — 채워진 칸에서만
    filled = [v for v in existing.values()]
    L.append("## 5. 집계")
    L.append("")
    if not filled:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L.append(f"채워진 행 {len(filled)} / {len(images) * len(names)}. 빈 칸은 계산에서 뺌.")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
