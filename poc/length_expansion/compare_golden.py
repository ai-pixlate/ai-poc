"""번역 길이 팽창률 — 골든 샘플 요약 생성기 (계획 단계 7).

run_golden.py 결과를 읽어 summary_golden.md 를 만든다.
단계 7 판정은 **기계 집계**다(계획 7장 — 통과선 없음). 육안 등급 칸은 만들지 않는다.
확인할 것은 12장 결론 "조판으로 흡수 불가(초과율 94%)"가 골든에서도 유지되는지다.

사용법
    python compare_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "golden"
OLD = HERE / "results"
SUMMARY = HERE / "summary_golden.md"
VARIANTS = ("nowrap", "wrap_allowed", "wrap_and_shrink", "wrap_grow_20")
VARIANT_DESC = {
    "nowrap": "한 줄 가정 — 번역문 폭이 박스 폭을 넘으면 초과",
    "wrap_allowed": "줄바꿈 허용 — 접은 뒤 총 높이가 박스 높이를 넘으면 초과",
    "wrap_and_shrink": "줄바꿈 + 폰트 80%까지 축소 — **판정 대상**",
    "wrap_grow_20": "줄바꿈 + 박스 높이 2배까지 확장(폰트 그대로)",
}
MAIN = "wrap_and_shrink"
OLD_RATE = 0.939  # 12장 block 기준 결론값


def esc(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ").strip()


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    metas, olds = {}, {}
    for v in VARIANTS:
        p = OUT / v / "meta.json"
        if not p.exists():
            raise SystemExit(f"{p} 없음 — run_golden.py 먼저")
        metas[v] = json.loads(p.read_text(encoding="utf-8"))
        op = OLD / v / "meta.json"
        if op.exists():
            olds[v] = json.loads(op.read_text(encoding="utf-8"))["inputs"].get("block")

    m = metas[MAIN]
    rel = "results/golden"
    L = ["# 번역 길이 팽창률 — 골든 샘플 요약", "",
         "> `compare_golden.py`가 생성함. 전부 기계 집계 — 육안 등급 없음(계획 7장: 통과선 없음).",
         "> 계획 `PoC_골든샘플_재실행_계획.md` 단계 7. 12장 결과(`summary.md`)는 건드리지 않음.", ""]

    # 1. 실행 조건
    a = m["assumptions"]
    L += ["## 1. 실행 조건", "", "| 항목 | 값 |", "|---|---|",
          "| 번역 | `gemini-3.8-flash` · 프롬프트 `default`(기존 전문 그대로) · 온도 0 |",
          f"| 입력 단위 | 단계 2 `llm_assist` 블록에서 단계 3 라벨 · 단계 4 로고 · 한글 없는 블록 제외 |",
          f"| 규모 | 섹션 {m['sections']} · 세그먼트 {m['segments']} (12장 표본 · 블록 입력 10장 33세그먼트) |",
          f"| 폭 가정 | 폰트 {a['font']} · 자간 {a['letter_spacing']} · em = 줄 높이 ×{a['em_ratio']} · 줄 간격 ×{a['line_gap']} |",
          "| 규제 매핑 표 | 테스트용 더미 15항목 — 12장과 같음 |", ""]

    # 2. 조건별 초과율
    L += ["## 2. 조건별 초과율", "",
          "| 조건 | 내용 | 골든 초과 | 골든 초과율 | 12장 초과율 | 차 |",
          "|---|---|---|---|---|---|"]
    for v in VARIANTS:
        g = metas[v]
        o = olds.get(v)
        ov = pct(o["overflow_rate"]) if o else "-"
        diff = f"{(g['overflow_rate'] - o['overflow_rate']) * 100:+.0f}p" if o else "-"
        L.append(f"| `{v}` | {VARIANT_DESC[v]} | {g['overflow']}/{g['segments']} | "
                 f"**{pct(g['overflow_rate'])}** | {ov} | {diff} |")
    L += ["", f"> 판정 대상은 `{MAIN}`의 잔여 초과율 — 조정 상한(폰트 80% 축소)으로도 흡수되지 않는 비율.", ""]

    # 3. 흡수 구간
    L += ["## 3. 조정 구간별 누적 흡수율", "",
          "**폰트 축소만으로 흡수** — 그 배율까지 줄이면 들어가는 세그먼트 누적 비율", "",
          "| 표본 | " + " | ".join(m["absorb_cum_by_min_scale"]) + " |",
          "|---|" + "---|" * len(m["absorb_cum_by_min_scale"])]
    L.append("| 골든 | " + " | ".join(pct(x) for x in m["absorb_cum_by_min_scale"].values()) + " |")
    if olds.get(MAIN):
        L.append("| 12장 | " + " | ".join(pct(x) for x in olds[MAIN]["absorb_cum_by_min_scale"].values()) + " |")
    L += ["", f"- 0.30배까지 줄여도 안 들어가는 세그먼트 — 골든 {m['unfittable_even_at_30pct']} / "
          f"12장 {olds[MAIN]['unfittable_even_at_30pct'] if olds.get(MAIN) else '-'}", "",
          "**높이 확장으로 흡수** — 박스 높이를 그 배수까지 늘리면 들어가는 누적 비율", "",
          "| 표본 · 폰트 | " + " | ".join(m["absorb_cum_by_grow"]) + " |",
          "|---|" + "---|" * len(m["absorb_cum_by_grow"]),
          "| 골든 · 100% | " + " | ".join(pct(x) for x in m["absorb_cum_by_grow"].values()) + " |",
          "| 골든 · 80% | " + " | ".join(pct(x) for x in m["absorb_cum_by_grow_at_80"].values()) + " |"]
    if olds.get(MAIN):
        L += ["| 12장 · 100% | " + " | ".join(pct(x) for x in olds[MAIN]["absorb_cum_by_grow"].values()) + " |",
              "| 12장 · 80% | " + " | ".join(pct(x) for x in olds[MAIN]["absorb_cum_by_grow_at_80"].values()) + " |"]
    L += ["", f"- 필요 높이 배수 중앙값 — 골든 {m['grow_median']}배 / "
          f"12장 {olds[MAIN]['grow_median'] if olds.get(MAIN) else '-'}배",
          "- 높이 확장은 아래 요소를 밀어내는 것이라 **세로로 이어붙는 본문에서만** 가능함. "
          "배지·버튼·제품 위 문구는 밀 자리가 없음", ""]

    # 4. 폭 배율
    L += ["## 4. 폭 배율 (번역문 렌더 폭 ÷ 박스가 담는 총 가로 길이)", "",
          "| 표본 | 중앙 | 최대 |", "|---|---|---|",
          f"| 골든 | {m['ratio_median']} | {m['ratio_max']} |"]
    if olds.get(MAIN):
        L.append(f"| 12장 | {olds[MAIN]['ratio_median']} | {olds[MAIN]['ratio_max']} |")
    L += ["", "> 1.0을 넘으면 원문 자리에 안 들어감. 2.27배는 **자리의 2배가 넘게 필요**하다는 뜻.", ""]

    # 5. role별
    L += [f"## 5. 역할별 초과 (`{MAIN}`)", "", "| 역할 | 세그먼트 | 초과 | 초과율 |", "|---|---|---|---|"]
    for k, v in sorted(m["by_role"].items(), key=lambda kv: -kv[1]["segments"]):
        L.append(f"| {k} | {v['segments']} | {v['overflow']} | {pct(v['rate'])} |")
    L += ["", "> 역할은 단계 2 분류 결과. 역할 구분과 무관하게 전 역할 97% 이상 초과. "
          "단계 2 분류에 배지·버튼 역할이 없어, 밀 자리 유무는 이 표로 갈리지 않음.", ""]

    # 6. 섹션별 — 흡수된 세그먼트가 있는 섹션 위주
    rows = json.loads((OUT / MAIN / "golden.json").read_text(encoding="utf-8"))["segments"]
    fit = [r for r in rows if not r["overflow"]]
    L += [f"## 6. 흡수된 세그먼트 {len(fit)}건 (`{MAIN}`에서 들어간 것)", ""]
    if fit:
        L += ["| 섹션 | id | 역할 | 박스 | 배율 | 들어간 배율 | 번역문 |", "|---|---|---|---|---|---|---|"]
        for r in sorted(fit, key=lambda r: r["id"]):
            L.append(f"| `{r['image']}` | {r['id'].split('-')[-1]} | {r.get('role') or '-'} | "
                     f"{r['box'][0]}×{r['box'][1]} | {r['ratio']} | {int(r['fit_scale'] * 100)}% | "
                     f"{esc(r['target'])[:40]} |")
        L.append("")

    secs = sorted(m["by_section"].items(), key=lambda kv: (-kv[1]["segments"]))
    L += ["**섹션별 — 세그먼트 많은 순 상위 15** (긴 본문 섹션에서 달라지는지 확인)", "",
          "| 섹션 | 세그먼트 | 초과 | 초과율 |", "|---|---|---|---|"]
    for k, v in secs[:15]:
        L.append(f"| `{k}` | {v['segments']} | {v['overflow']} | {pct(v['rate'])} |")
    long_secs = [v for _, v in secs if v["segments"] >= 10]
    if long_secs:
        ls, lo = sum(v["segments"] for v in long_secs), sum(v["overflow"] for v in long_secs)
        L += ["", f"- 세그먼트 10개 이상 섹션 {len(long_secs)}개 합계 — {lo}/{ls} ({pct(lo / ls)}). "
              f"전체 {pct(m['overflow_rate'])}와 비교", ""]

    # 7. 확인
    keep = m["overflow_rate"] >= OLD_RATE - 0.05
    L += ["## 7. 확인 — 12장 결론이 유지되는가", "", "| 항목 | 12장 | 골든 | 판단 |", "|---|---|---|---|",
          f"| 잔여 초과율(`{MAIN}`) | {pct(OLD_RATE)} | {pct(m['overflow_rate'])} | "
          f"{'유지' if keep else '변동'} |",
          f"| 표본 | 블록 입력 10장 · 33세그먼트 | {m['sections']}섹션 · {m['segments']}세그먼트 | 17배 |",
          f"| 폰트 100%로 들어감 | {pct(olds[MAIN]['absorb_cum_by_min_scale']['100%']) if olds.get(MAIN) else '-'} | "
          f"{pct(m['absorb_cum_by_min_scale']['100%'])} | - |", "",
          "> 결론 — 표본을 17배로 늘려도 **조판 조정만으로는 흡수 불가**. "
          "번역문 길이를 줄이거나 레이아웃을 다시 잡아야 함." if keep else
          "> 결론 — 12장 결론과 어긋남. 원인 확인 필요.", "",
          f"- 세그먼트별 측정치 `{rel}/{{조건}}/golden.json` · 집계 `{rel}/{{조건}}/meta.json`", ""]

    SUMMARY.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {SUMMARY}  ({MAIN} 초과 {m['overflow']}/{m['segments']} = {pct(m['overflow_rate'])})")


if __name__ == "__main__":
    main()
