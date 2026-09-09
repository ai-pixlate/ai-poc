"""제품 라벨 판정 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
사람이 채우는 건 판정표의 **미탐·오탐** 두 칸이다.

  미탐 = 제품 라벨인데 `배경`으로 본 블록 수 — **복구 불가**
  오탐 = 배경 텍스트인데 `라벨`로 본 블록 수 — 번역 누락, 검수 복구 가능

**등급 산식을 두지 않는다.** 미탐 1건으로 탈락시킬지가 아직 미정이라
(`PoC_추가검증_계획.md` 미결 8) 임의로 정하지 않는다. 건수만 모은다.

**이미 채워진 값은 재실행해도 보존한다.**

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

COUNT_COLS = ["미탐", "오탐", "비고"]

# 판정에서 뺀 variant. 실행 결과는 1·2장에 근거로 남기되 판정표·합의도에서는 뺀다.
EXCLUDED: dict[str, str] = {
    "vlm_opus": "`vlm_relation`과 110블록 전부 동일 판정 — 판정 불필요 (2026-09-09)",
}


def variants() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())


def load_blocks(variant: str, image: str) -> list[dict]:
    return json.loads(
        (RESULTS / variant / "blocks" / f"{Path(image).stem}.json").read_text(encoding="utf-8")
    )["blocks"]


def read_table() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 행을 회수한다.

    행 형식: | 이미지 | `variant` | 블록 | 라벨 | 미탐 | 오탐 | 비고 | 시각화 |
    """
    if not OUT.exists():
        return {}
    got: dict[tuple[str, str], list[str]] = {}
    width = 2 + 2 + len(COUNT_COLS) + 1
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
        vals = cells[4 : 4 + len(COUNT_COLS)]
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
    filled = read_table()

    blocks = {(n, img): load_blocks(n, img) for n in names for img in images}
    judged = [n for n in names if n not in EXCLUDED]   # 판정 대상 variant

    L: list[str] = []
    L.append("# 제품 라벨 판정 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **미탐·오탐 두 칸이 사람이 채우는 전부임.**")
    L.append("> 입력은 `block_role`의 `llm_assist` 블록. 계획은 `PoC_추가검증_계획.md`.")
    L.append("> **등급 산식 없음** — 미탐 1건 탈락 여부가 미결(계획 문서 미결 8)이라 두지 않음.")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| variant | 조건 | 블록 | 라벨 판정 | 비율 | 소요 | 비용 |")
    L.append("|---|---|---|---|---|---|---|")
    for n in names:
        m = metas[n]
        cfg = " ".join(f"`{k}={v}`" for k, v in m["cfg"].items())
        rate = m["total_labels"] / max(1, m["total_blocks"])
        cost = f"${m['cost_usd']}" if m.get("cost_usd") else "0"
        L.append(
            f"| `{n}` | {cfg} | {m['total_blocks']} | {m['total_labels']} | "
            f"{rate:.0%} | {m['total_sec']}s | {cost} |"
        )
    L.append("")
    if EXCLUDED:
        L.append("**판정 제외** — 실행 결과는 1·2장에 남기되 판정표에서는 뺌.")
        L.append("")
        for n, why in EXCLUDED.items():
            if n in names:
                L.append(f"- `{n}` — {why}")
        L.append("")

    # 2. 이미지별 라벨 판정 수
    L.append("## 2. 이미지별 라벨 판정 수 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("| 이미지 | 블록 | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|---|" + "---|" * len(names))
    for img in images:
        nb = len(blocks[(names[0], img)])
        cells = []
        for n in names:
            cells.append(str(sum(1 for b in blocks[(n, img)] if b["is_product_label"])))
        L.append(f"| {img} | {nb} | " + " | ".join(cells) + " |")
    L.append("")

    # 3. 합의도 — 어느 블록을 먼저 볼지 고르는 용도
    if len(judged) >= 2:
        L.append("## 3. 합의도")
        L.append("")
        L.append("블록마다 몇 개 variant가 `라벨`로 봤는지 센다. **갈리는 블록이 판정 대상임.**")
        L.append("")
        L.append("| 이미지 | 전원 라벨 | 전원 배경 | **갈림** |")
        L.append("|---|---|---|---|")
        tot = [0, 0, 0]
        for img in images:
            n_all = n_none = n_split = 0
            for i in range(len(blocks[(judged[0], img)])):
                votes = sum(1 for n in judged if blocks[(n, img)][i]["is_product_label"])
                if votes == len(judged):
                    n_all += 1
                elif votes == 0:
                    n_none += 1
                else:
                    n_split += 1
            tot = [tot[0] + n_all, tot[1] + n_none, tot[2] + n_split]
            L.append(f"| {img} | {n_all} | {n_none} | **{n_split}** |")
        L.append(f"| **합계** | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** |")
        L.append("")

    # 4. 판정표
    L.append("## 4. 판정표")
    L.append("")
    L.append("**채울 칸은 `미탐`·`오탐` 2개.** 블록·라벨 수는 코드가 채움.")
    L.append("")
    L.append("- **미탐** = 제품 라벨인데 `배경`으로 본 블록 수. **복구 불가**")
    L.append("- **오탐** = 배경 텍스트인데 `라벨`로 본 블록 수. 번역 누락이나 검수 복구 가능")
    L.append("")
    L.append("`vis/`에서 **빨강 = 라벨 판정 · 파랑 = 배경 판정**. 라벨 옆 숫자는 판정에 쓴 값임.")
    L.append("")
    L.append("| 이미지 | variant | 블록 | 라벨 | " + " | ".join(COUNT_COLS) + " | 시각화 |")
    L.append("|---|---|---|---|" + "---|" * len(COUNT_COLS) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in judged:
            nb = len(blocks[(n, img)])
            nl = sum(1 for b in blocks[(n, img)] if b["is_product_label"])
            vals = filled.get((img, n), [""] * len(COUNT_COLS))
            L.append(
                f"| {img} | `{n}` | {nb} | {nl} | " + " | ".join(vals)
                + f" | `results/{n}/vis/{stem}.jpg` |"
            )
    L.append("")

    # 5. 집계 — 채워진 칸에서만
    L.append("## 5. 집계")
    L.append("")
    if not filled:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L.append(f"채워진 행 {len(filled)} / {len(images) * len(judged)}. 빈 행은 계산에서 뺌.")
        L.append("")
        L.append("| variant | 판정 이미지 | 미탐 | 오탐 | 라벨 판정 | 오탐률 |")
        L.append("|---|---|---|---|---|---|")
        for n in judged:
            rows = [(img, v) for (img, var), v in filled.items() if var == n]
            miss = fp = lab = 0
            ok = 0
            for img, v in rows:
                try:
                    miss += int(v[0])
                    fp += int(v[1])
                except ValueError:
                    continue
                lab += sum(1 for b in blocks[(n, img)] if b["is_product_label"])
                ok += 1
            if not ok:
                continue
            L.append(
                f"| `{n}` | {ok} | **{miss}** | {fp} | {lab} | "
                f"{fp / max(1, lab):.0%} |"
            )
        L.append("")
        L.append("**미탐이 0인 variant만 채택 후보임.** 오탐률은 검수 부담의 크기임.")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종 중 판정 {len(judged)}종, "
          f"이미지 {len(images)}장)")


if __name__ == "__main__":
    main()
