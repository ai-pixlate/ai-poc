"""섹션 단위 규제·현지 부적합 판정 — 요약·판정표 생성.

results/ 아래 있는 variant 결과를 모두 읽어 summary.md를 다시 쓴다.
판정표에 사람이 채운 칸(정답 항목 · 전체/일부 · 비고)은 **기존 summary.md에서 회수**해 유지한다.

맥락 효과 — 정답 없이 계산되는 값만 낸다. variant 쌍마다 `all` 결정이 바뀐 섹션 수와
목록. 맞게 바뀐 것인지는 판정표가 채워진 뒤 따로 센다.

사용법
    python compare.py
"""

from __future__ import annotations

import json
import sys

import run as base

HERE = base.HERE
RESULTS = base.RESULTS
ORDER = ("rule_kw", "sec_only", "sec_adj", "sec_outline")
SHORT = {"rule_kw": "kw", "sec_only": "only", "sec_adj": "adj", "sec_outline": "outl"}
FILL = ("정답 항목", "전체/일부", "비고")


def load(variant: str) -> dict[str, dict]:
    d = RESULTS / variant / "decisions"
    if not d.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.json")}


def meta_of(variant: str) -> dict | None:
    p = RESULTS / variant / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def filled() -> dict[str, list[str]]:
    """기존 판정표에서 사람이 채운 칸 회수. 행 id → FILL 순서 값."""
    p = HERE / "summary.md"
    if not p.exists():
        return {}
    out, cols = {}, None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 섹션 |"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            continue
        if cols and line.startswith("| `A"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != len(cols):
                continue
            sid = cells[0].strip("`")
            out[sid] = [cells[cols.index(c)] if c in cols else "" for c in FILL]
        elif cols and not line.startswith("|"):
            cols = None
    return out


def hit_cell(doc: dict) -> str:
    if not doc["hits"]:
        return "—"
    parts = []
    for h in doc["hits"]:
        mark = "●" if h["decision"] == "제외" else "○"
        rel = f"→{','.join(r[-14:] for r in h.get('related_sections') or [])}" if h.get("related_sections") else ""
        parts.append(f"{mark}`{h['item']}`{rel}")
    return " ".join(parts)


def build() -> None:
    data = {v: load(v) for v in ORDER}
    have = [v for v in ORDER if data[v]]
    secs = base.load_sections()
    keep = filled()

    L = ["# 섹션 단위 규제·현지 부적합 판정", "",
         "> 계획 `PoC_추가검증_계획.md` 2장. 입력 골든 섹션 102개(`color_snap_vlm2`) · 블록 `llm_assist`.",
         "> **사이트 정책은 미정** — `all`(8항목 전부 금지)·`review_ban`(사용자 리뷰만 금지, 사이트 A 예시)은 가정.",
         "> `compare.py`가 생성함. 판정표의 채울 칸은 재생성 시 회수됨.", "",
         "## 상태", "",
         "| variant | 상태 | 호출 · 캐시 | 토큰 in / out | 비용 | 소요 | 오류 |",
         "|---|---|---|---|---|---|---|"]
    for v in ORDER:
        m = meta_of(v)
        if v == "rule_kw":
            L.append(f"| `rule_kw` | {'실행' if m else '미실행'} | — | — | 0 | {m['sec'] if m else '—'}s | — |")
        elif m:
            L.append(f"| `{v}` | 실행 ({m['run_at']}) | {m['calls']} · {m['cache_hits']} | "
                     f"{m['tokens']['in']:,} / {m['tokens']['out']:,} | ${m['cost_usd']} | "
                     f"벽시계 {m['wall_sec']}s · 동시 {m['concurrency']} | {len(m['errors'])} |")
        else:
            L.append(f"| `{v}` | 미실행 | | | | | |")
    o = sorted((RESULTS / "outline").glob("*.json")) if (RESULTS / "outline").exists() else []
    L += ["", f"페이지 개요 — {len(o)}/34페이지 생성 (`results/outline/`).", ""]

    L += ["## 정책별 결정 수", "", "| variant | 정책 | 유지 | 확인 필요 | 제외 |", "|---|---|---|---|---|"]
    for v in have:
        for p in base.POLICIES:
            c = {k: sum(1 for d in data[v].values() if d["decisions"][p] == k) for k in base.RANK}
            L.append(f"| `{v}` | `{p}` | {c['유지']} | {c['확인 필요']} | {c['제외']} |")

    L += ["", "## 항목별 적중 섹션 수 (제외 / 확인 필요)", "",
          "| 항목 | " + " | ".join(f"`{v}`" for v in have) + " |",
          "|---|" + "---|" * len(have)]
    for k, n, _ in base.ITEMS:
        cells = []
        for v in have:
            ex = sum(1 for d in data[v].values() for h in d["hits"] if h["item"] == k and h["decision"] == "제외")
            ch = sum(1 for d in data[v].values() for h in d["hits"] if h["item"] == k and h["decision"] == "확인 필요")
            cells.append(f"{ex} / {ch}")
        L.append(f"| {n} | " + " | ".join(cells) + " |")

    vlm = [v for v in have if v != "rule_kw"]
    if len(vlm) >= 2:
        L += ["", "## 맥락 효과 — 결정 변경 (정답 대조 전)", "",
              "`all` 정책 결정이 바뀐 섹션. 맞게 바뀐 것인지는 판정표 작성 후 셈.", "",
              "| 비교 | 바뀐 섹션 수 | 섹션 (앞 → 뒤) |", "|---|---|---|"]
        for a, b in zip(vlm, vlm[1:]):
            common = sorted(set(data[a]) & set(data[b]))
            ch = [s for s in common if data[a][s]["decisions"]["all"] != data[b][s]["decisions"]["all"]]
            lst = " · ".join(f"`{s[-14:]}` {data[a][s]['decisions']['all']}→{data[b][s]['decisions']['all']}"
                             for s in ch) or "—"
            L.append(f"| `{a}` → `{b}` | {len(ch)} / {len(common)} | {lst} |")

    L += ["", "## rule_kw — 키워드 기준선", "",
          "| 항목 | 내용 |", "|---|---|",
          "| 규칙 | 항목별 **서로 다른 키워드 2개 이상 → 제외 · 1개 → 확인 필요 · 0개 → 유지**. 전후 비교는 `사용 전`·`사용 후` 동시 적중 |",
          "| 키워드 | 항목별 일반 어휘 + **골든 102섹션 텍스트를 읽고 본 표현** 추가 — 가린 이름+님(`한기*님`) · `실사용`·`찐사용` · `N명이 인정` · OCR 오타 `금정 답변` · `페이백`·`기프트카드` · `올리브영`·`아마존` · `특수관리` 등 |",
          "| 오탐 예외 | `피부과(?!학)`(한국피부과학연구원) · `\\d원(?![가-힣])`(원료·원하는) · `\\d위(?![가-힣])` · 영문자 사이 `vs` 제외 |",
          "| 결정 기준 | 키워드 2개 이상 제외 · 1개 확인 필요 — **임의값, 데이터로 조정 안 함** |", "",
          "### rule_kw 한계", "",
          "| # | 한계 |", "|---|---|",
          "| 1 | **평가 표본과 규칙 작성 표본이 같음** — 골든 102섹션을 보고 키워드를 골라 이 표본 성적은 낙관적. 처음 보는 페이지에서 더 낮을 것 |",
          "| 2 | 골든 표기 방식에 맞춘 패턴 포함 — 가린 이름 `*님` 등. 다른 브랜드·쇼핑몰 표기에는 안 맞을 수 있음 |",
          "| 3 | 결정 기준(키워드 2개)이 임의값 |",
          "| 4 | 키워드 유무로는 **맥락을 못 가름** — 리뷰 3건 섹션(`250199_009_003`)이 키워드 1개로 확인 필요에 그침. `리뷰 작성은 필요 없어요`(이벤트) · `실사용자 만족도`(설문)가 리뷰로 걸림 |",
          "| 5 | OCR 깨진 글자(`1위)` · `top14위`) · 논문 초록 속 `vs`가 그대로 걸림 |",
          "| 6 | 글자 없는 섹션은 판단 못 함 — 유지로 둠 |",
          "| 7 | 사이트 정책(`all` · `review_ban`)은 가정 — 실제 정책 확정 시 항목·키워드 변경 가능 |", "",
          "**보완 방향** — 키워드를 현 상태로 고정하고 판정표 작성 후 수정 안 함 · 골든 밖 상세페이지를 따로 두어 재측정.", "",
          "## VLM variant", "",
          "| 항목 | 내용 |", "|---|---|",
          "| 모델 | `gemini-3.8-flash` · `temperature=0` · 이미지 긴 변 1024px · 4,000px 초과 섹션 2조각 |",
          "| 출력 | 항목별 `해당`(→ 제외) · `애매`(→ 확인 필요) · coverage(전체/일부) · 근거 블록 · 관련 섹션 |",
          "| `sec_only` | 섹션 이미지 + 섹션 블록 |",
          "| `sec_adj` | + 앞뒤 섹션 텍스트(참고) |",
          "| `sec_outline` | + 페이지 개요(섹션별 이름·요약, 페이지당 1호출) |",
          "| 항목 정의 | `run_vlm.py` `ITEM_DEFS` — **초안.** 브랜드 시험 / 사용자 설문 / 리뷰 경계는 팀 정의 미정 |", "",
          "## 섹션별 결정 · 판정표", "",
          "결정은 `all` 정책. 칸 형식 `결정 · 항목` — ●제외 ○확인 필요, `→` 뒤는 VLM이 적은 관련 섹션. "
          "vis: `results/{variant}/vis/sections/{섹션}.jpg`.", "",
          "**채울 칸** — `정답 항목`(해당 항목 키를 쉼표로, 없으면 `-`) · `전체/일부` · `비고`.",
          "**현재 값은 Claude 1차 후보(2026-09-17)** — 섹션 이미지 전수 육안 확인 · 항목 정의 초안(`ITEM_DEFS`) 기준. "
          "예람님 검토 전. `**맥락 사례**`는 판단 근거가 다른 섹션에 걸친 행.", "",
          "| 섹션 | 높이 | " + " | ".join(SHORT[v] for v in have) + " | " + " | ".join(FILL) + " |",
          "|---|---|" + "---|" * (len(have) + len(FILL))]
    for s in secs:
        sid = s["section"]
        cells = []
        for v in have:
            d = data[v].get(sid)
            cells.append("" if d is None else f"{d['decisions']['all']} · {hit_cell(d)}")
        fill = keep.get(sid, ["", "", ""])
        L.append(f"| `{sid}` | {s['height']} | " + " | ".join(cells) + " | " + " | ".join(fill) + " |")
    L += ["", "variant 약칭 — " + " · ".join(f"`{SHORT[v]}` {v}" for v in ORDER),
          "", "항목 키 — " + " · ".join(f"`{k}` {n}" for k, n, _ in base.ITEMS), ""]
    (HERE / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[compare] summary.md — variant {', '.join(have)} · 회수한 채움 행 "
          f"{sum(1 for v in keep.values() if any(x for x in v))}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
