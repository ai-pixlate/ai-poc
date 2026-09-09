"""번역 길이 팽창률 — 요약표 생성기.

이 과업은 육안 판정이 아니라 **측정**이다. 등급 칸을 만들지 않는다.
사람이 정할 것은 통과 임계 하나뿐이며, 그것은 아직 _미정_ 이다.

summary.md에 담는 것
    1. 측정 조건 — 폰트·em·줄간격 가정과 번역 프롬프트
    2. variant별 초과율
    3. 필요 축소율 분포 — 얼마나 줄이면 들어가는가
    4. em 가정 민감도 — 결론이 가정에 의존하는지
    5. role별 분해 (block 입력)
    6. 초과가 큰 사례

사용법
    python compare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R  # noqa: E402  — 측정 함수를 그대로 쓴다(같은 과업)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
TRANS = HERE / "translations"
OUT = HERE / "summary.md"

INPUT_DESC = {
    "block": "채택 파이프라인 — `vlm_relation` 블록 중 라벨 아님 + 한글 포함. bbox는 블록 박스",
    "region": "인식 영역 단위 — 라벨 섞임. 단위 차이를 보려고 함께 잼",
}
THRESHOLDS = (1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5)
EM_SENSITIVITY = (1.0, 1.15, 1.35)


def variants() -> list[str]:
    return [n for n in ("nowrap", "wrap_allowed", "wrap_and_shrink") if (RESULTS / n).exists()]


def load(variant: str, inp: str) -> list[dict]:
    return json.loads((RESULTS / variant / f"{inp}.json").read_text(encoding="utf-8"))["segments"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    names = variants()
    if not names:
        raise SystemExit(f"{RESULTS} 아래 결과 없음 — run.py 를 먼저 돌릴 것")
    inputs = sorted(p.stem for p in TRANS.glob("*.json") if ".meta" not in p.name)
    metas = {n: json.loads((RESULTS / n / "meta.json").read_text(encoding="utf-8")) for n in names}
    tmeta = {
        i: json.loads((TRANS / f"{i}.meta.json").read_text(encoding="utf-8")) for i in inputs
    }

    L: list[str] = []
    L.append("# 번역 길이 팽창률 — 측정 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **육안 판정 없음 — 측정 과업임.**")
    L.append("> 사람이 정할 것은 통과 임계 하나이며 아직 `_미정_`.")
    L.append("")

    # 1. 측정 조건
    a = metas[names[0]]["assumptions"]
    L.append("## 1. 측정 조건")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|---|---|")
    L.append(f"| 대상 언어 | 영어 (ko → en) |")
    L.append(f"| 번역 모델 | `{tmeta[inputs[0]]['model']}` · `temperature=0` |")
    L.append("| 번역 프롬프트 | `prompt.py` — C 과업 `v6_principle` 사본. "
             "**규칙 4에 길이 제약 지시 포함** |")
    L.append("| 규제 표 | **테스트용 더미 15항목** — 대체표현 길이가 결과에 섞임 |")
    L.append(f"| 폰트 | `{a['font']}` · 자간 {a['letter_spacing']} |")
    L.append(f"| em 크기 | 줄 높이 × **{a['em_ratio']}** (OCR bbox는 글자 획 높이라 em보다 작음) |")
    L.append(f"| 줄 높이 | 원본 = bbox 높이 ÷ 원문 줄 수 · 렌더 = em × {a['line_gap']} |")
    L.append("")
    L.append("**이 가정이 바뀌면 수치가 통째로 움직임.** 4장에 민감도를 실었음.")
    L.append("")
    L.append("| 입력 | 설명 | 세그먼트 | 번역 비용 |")
    L.append("|---|---|---|---|")
    for i in inputs:
        L.append(f"| `{i}` | {INPUT_DESC.get(i, '')} | {tmeta[i]['segments']} | "
                 f"${tmeta[i]['cost_usd']} |")
    L.append("")

    # 2. variant별 초과율
    L.append("## 2. 초과율")
    L.append("")
    L.append("| variant | 조판이 허용하는 것 | " + " | ".join(f"`{i}`" for i in inputs) + " |")
    L.append("|---|---|" + "---|" * len(inputs))
    desc = {"nowrap": "없음 (한 줄 고정)", "wrap_allowed": "줄바꿈",
            "wrap_and_shrink": "줄바꿈 + 폰트 축소 80%까지"}
    for n in names:
        cells = []
        for i in inputs:
            v = metas[n]["inputs"][i]
            cells.append(f"**{v['overflow_rate']:.0%}** ({v['overflow']}/{v['segments']})")
        L.append(f"| `{n}` | {desc.get(n, '')} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("**판정 대상은 `wrap_and_shrink` 행** — 조정 상한으로도 흡수되지 않는 비율임.")
    L.append("")

    # 3. 필요 축소율 분포
    L.append("## 3. 필요 축소율 — 얼마나 줄이면 들어가는가")
    L.append("")
    L.append("줄바꿈을 허용한 상태에서 박스에 들어가는 **최소 폰트 배율**을 세그먼트마다 찾음."
             " 아래는 그 배율 이상으로 들어가는 누적 비율.")
    L.append("")
    L.append("| 입력 | " + " | ".join(f"≥{int(t * 100)}%" for t in THRESHOLDS) + " | 30%에도 불가 |")
    L.append("|---|" + "---|" * (len(THRESHOLDS) + 1))
    for i in inputs:
        v = metas["wrap_and_shrink"]["inputs"][i]
        cum = v["absorb_cum_by_min_scale"]
        cells = [f"{cum[f'{int(t * 100)}%']:.0%}" for t in THRESHOLDS]
        L.append(f"| `{i}` | " + " | ".join(cells) + f" | {v['unfittable_even_at_30pct']} |")
    L.append("")
    L.append("| 입력 | 폭 배율 중앙 | 최대 |")
    L.append("|---|---|---|")
    for i in inputs:
        v = metas["wrap_and_shrink"]["inputs"][i]
        L.append(f"| `{i}` | **{v['ratio_median']}배** | {v['ratio_max']}배 |")
    L.append("")
    L.append("폭 배율 = 번역문 한 줄 폭 ÷ (박스 폭 × 원문 줄 수). 박스가 담을 수 있는 총 길이 대비임.")
    L.append("")

    # 4. em 가정 민감도
    L.append("## 4. em 가정 민감도")
    L.append("")
    L.append("em 크기 가정을 바꿔 다시 계산함. **결론이 가정에 의존하는지 보는 것.**")
    L.append("")
    L.append("| em 배수 | 입력 | 100% 내 | ≥90% | ≥80% | ≥50% |")
    L.append("|---|---|---|---|---|---|")
    lines_map = R.block_line_counts()
    keep = R.EM_RATIO
    for em in EM_SENSITIVITY:
        R.EM_RATIO = em
        for i in inputs:
            segs = json.loads((TRANS / f"{i}.json").read_text(encoding="utf-8"))["segments"]
            rows = [
                R.measure(s, R.VARIANTS["wrap_and_shrink"],
                          R.source_lines(s, lines_map) if i == "block" else 1)
                for s in segs
            ]
            need = [r["need_scale"] for r in rows]
            f = lambda t: sum(1 for x in need if x is not None and x >= t) / len(rows)
            mark = " ←현행" if em == keep else ""
            L.append(f"| {em}{mark} | `{i}` | {f(1.0):.0%} | {f(0.9):.0%} | {f(0.8):.0%} | "
                     f"{f(0.5):.0%} |")
    R.EM_RATIO = keep
    L.append("")

    # 5. role별 분해
    rows = load("wrap_and_shrink", "block")
    roles = sorted({r["role"] for r in rows if r["role"]})
    if roles:
        L.append("## 5. role별 분해 (`block` 입력)")
        L.append("")
        L.append("| role | 세그먼트 | 초과 | 폭 배율 중앙 |")
        L.append("|---|---|---|---|")
        for role in roles:
            sub = [r for r in rows if r["role"] == role]
            over = sum(1 for r in sub if r["overflow"])
            med = sorted(r["ratio"] for r in sub)[len(sub) // 2]
            L.append(f"| {role} | {len(sub)} | {over} ({over / len(sub):.0%}) | {med}배 |")
        L.append("")

    # 6. 초과가 큰 사례
    L.append("## 6. 폭 배율 상위 10건 (`block`)")
    L.append("")
    L.append("| 배율 | 박스 | 원문 | 번역문 |")
    L.append("|---|---|---|---|")
    for r in sorted(rows, key=lambda r: -r["ratio"])[:10]:
        src = r["source"].replace("|", "\\|")[:24]
        tgt = r["target"].replace("|", "\\|")[:52]
        L.append(f"| {r['ratio']}배 | {r['box'][0]}×{r['box'][1]} | {src} | {tgt} |")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}  (variant {len(names)}종, 입력 {len(inputs)}종)")


if __name__ == "__main__":
    main()
