"""스타일 추출 — 골든 샘플 판정표 생성기 (계획 단계 6).

run_golden.py 결과를 읽어 summary_golden.md 를 만든다. 등급 칸은 비워 둔다.

판정 대상 — **조판 대상 영역만**(단계 3 라벨 정답·단계 4 로고 블록 제외).
대지는 `vis_target/{섹션}.jpg`(조판 대상만) · 전체는 `vis/{섹션}.jpg`.

기계 집계
    · 명도 대비 1.5 미만 영역 — 글자색과 배경색이 갈리지 않은 것. 색 실패 후보
    · 정렬 분포 — `불명` 비율
    · 12장 결과와 나란히 비교

사용법
    python compare_golden.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_DIR = HERE / "results" / "golden" / "otsu_border"
OLD_META = HERE / "results" / "otsu_border" / "meta.json"
SUMMARY = HERE / "summary_golden.md"
GRADE_COLS = ["색", "크기", "정렬", "비고"]
GATE = 0.70
ALIGN_ORDER = ("left", "center", "right", "단일행", "무관", "불명")
SID = re.compile(r"^A[0-9]+_[0-9]{3}_[0-9]{3}$")
PIPE = re.compile(r"(?<!\\)\|")


def cells(line: str) -> list:
    return [c.strip() for c in PIPE.split(line.strip().strip("|"))]


def esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " / ").strip()


def read_filled() -> dict:
    got = {}
    if not SUMMARY.exists():
        return got
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = cells(line)
        if len(c) == 4 + len(GRADE_COLS) + 1 and SID.match(c[0]):
            vals = c[4:4 + len(GRADE_COLS)]
            if any(vals):
                got[c[0]] = vals
    return got


def ratio(values: list) -> str:
    graded = [v.upper() for v in values if v.upper() in {"A", "B", "C"}]
    skipped = sum(1 for v in values if v == "-")
    total = len(values) - skipped
    if total == 0:
        return "-"
    if len(graded) < total:
        return f"판정 {len(graded)}/{total}"
    ab = sum(1 for v in graded if v in {"A", "B"})
    return f"{ab}/{total} ({ab / total * 100:.0f}%)"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mp = OUT_DIR / "meta.json"
    if not mp.exists():
        raise SystemExit(f"{mp} 없음 — run_golden.py 먼저")
    meta = json.loads(mp.read_text(encoding="utf-8"))
    rows = meta["per_section"]
    filled = read_filled()
    rel = "results/golden/otsu_border"

    styles = {}
    for r in rows:
        styles[r["section"]] = json.loads((OUT_DIR / "styles" / f"{r['section']}.json")
                                          .read_text(encoding="utf-8"))["styles"]

    L = ["# 스타일 추출 — 골든 샘플 섹션 판정", "",
         "> `compare_golden.py`가 생성함. 재실행해도 **채운 등급은 보존함.**",
         "> 계획 `PoC_골든샘플_재실행_계획.md` 단계 6. 12장 결과(`summary.md`)는 건드리지 않음.", ""]

    L += ["## 1. 실행 조건", "", "| 항목 | 값 |", "|---|---|",
          f"| variant | `{meta['variant']}` — Otsu로 가르고 **테두리에 많이 닿는 쪽을 배경**으로 봄 |",
          f"| 크기 | bbox 높이 = 글자 획 높이, em 환산 ×{meta['cfg']['em_ratio']} |",
          f"| 정렬 | 블록 안 줄들의 좌·중앙·우 분산 비교, 허용 오차 블록 폭 {meta['cfg']['align_tol'] * 100:.0f}% |",
          f"| 섹션 · 영역 | {meta['sections']} · {meta['total_regions']:,} |",
          f"| 판정 대상 | **조판 대상 {meta['target_regions']:,}영역** — 라벨 {meta['label_regions']} · 로고 {meta['logo_regions']} 제외 |",
          f"| 소요 | {meta['total_sec']}s (로컬, 비용 0) |", ""]

    # 2. 기계 집계
    L += ["## 2. 기계 집계 (정오 아님)", ""]
    old = json.loads(OLD_META.read_text(encoding="utf-8")) if OLD_META.exists() else None
    L += ["**정렬 분포** — 블록 안 줄이 1개면 `단일행`, 세 축이 모두 고르면 `무관`, 어느 축도 고르지 않으면 `불명`", "",
          "| 표본 | " + " | ".join(f"`{a}`" for a in ALIGN_ORDER) + " | 영역 |", "|---|" + "---|" * (len(ALIGN_ORDER) + 1)]
    d = meta["align_dist"]
    L.append("| 골든 102섹션 | " + " | ".join(str(d.get(a, 0)) for a in ALIGN_ORDER) + f" | {meta['total_regions']:,} |")
    if old:
        od = old["align_dist"]
        L.append("| 12장 | " + " | ".join(str(od.get(a, 0)) for a in ALIGN_ORDER) + f" | {old['total_regions']} |")
    L.append("")

    low = [(r["section"], s) for r in rows for s in styles[r["section"]]
           if not s["is_product_label"] and not s["is_logo"] and s["contrast"] < 1.5]
    L += [f"**명도 대비 1.5 미만 — 조판 대상 {len(low)}영역** (글자색과 배경색이 거의 같게 나온 것, 색 실패 후보)", ""]
    if low:
        L += ["| 섹션 | 영역 | 텍스트 | 글자색 | 배경색 | 대비 |", "|---|---|---|---|---|---|"]
        for sid, s in low:
            t = esc(s["text"]) or "(빈)"
            L.append(f"| `{sid}` | {s['region'] + 1} | {t[:40]} | `{s['font_color']}` | `{s['bg_color']}` | {s['contrast']} |")
        L.append("")

    # 3. 판정표
    L += ["## 3. 판정표 (섹션 × 육안 A/B/C — 빈 칸 채울 것)", "",
          "**등급 기준** (원 과업 — 조판 대상 영역 기준으로 섹션마다 세 축)", "",
          "| 등급 | 색 | 크기 | 정렬 |", "|---|---|---|---|",
          "| **A** | 글자색·배경색이 원본과 거의 같음 | 원본 글자 크기와 거의 같음 | 원본 정렬과 같음 |",
          "| **B** | 약간 어긋나지만 조판에 쓸 수 있음 | 약간 어긋나지만 조판에 쓸 수 있음 | `불명`이지만 배치로 유추 가능 |",
          "| **C** | 반전되거나 크게 틀림 | 크게 틀림 | 틀린 축을 고름 |",
          "| **-** | 조판 대상 영역이 없는 섹션 | 〃 | 〃 |", "",
          f"- 대지 `{rel}/vis_target/{{섹션}}.jpg` — **조판 대상만**. 오른쪽 띠에 글자색·배경색 스와치, 크기(px), 정렬(좌·중·우·1행·?)",
          f"- 전체 영역(라벨·로고 포함) 대지는 `{rel}/vis/{{섹션}}.jpg`",
          "- 확인 항목: **사진 배경 위 글자**와 **아웃라인·배지 테두리 글자** (12장 색 실패 유형) — 비고에 기록",
          "- 판정 주체: Claude 1차 판정(비고에 \"Claude 육안 판정\") → 예람님 검토", "",
          "| 섹션 | 조판 대상 | 제외 라벨/로고 | 대비<1.5 | " + " | ".join(GRADE_COLS) + " | 대지 |",
          "|---|---|---|---|" + "---|" * len(GRADE_COLS) + "---|"]
    for r in rows:
        v = filled.get(r["section"], [" "] * len(GRADE_COLS))
        L.append(f"| {r['section']} | {r['target_regions']} | {r['label_regions']}/{r['logo_regions']} | "
                 f"{r['target_low_contrast']} | " + " | ".join(v) + f" | [보기]({rel}/vis_target/{r['section']}.jpg) |")
    L.append("")

    # 4. 집계
    L += ["## 4. 집계", ""]
    cols = [[filled.get(r["section"], [""] * len(GRADE_COLS))[i] for r in rows] for i in range(3)]
    if not filled:
        L.append("_판정 전_ — 채워진 등급 없음.")
    else:
        L += ["| 색 | 크기 | 정렬 | 게이트 (각 A+B 70%) |", "|---|---|---|---|"]
        cs = [ratio(c) for c in cols]
        done = all("판정" not in c for c in cs)
        pct = [c for c in cs if c != "-" and "판정" not in c]
        gate = "판정 미완" if not done or not pct else (
            "O" if all(int(c.split("(")[1].rstrip("%)")) >= GATE * 100 for c in pct) else "X")
        L.append("| " + " | ".join(cs) + f" | {gate} |")
        L += ["", "> 게이트 — 색·크기·정렬 각 섹션 A+B 70%(계획 7장). 한 축이라도 미달이면 X.", ""]
    L.append("")

    SUMMARY.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {SUMMARY}  (섹션 {len(rows)} · 판정 {len(filled)})")
    print(f"  대비 1.5 미만 조판 대상 {len(low)}영역 · 정렬 불명 {meta['align_dist'].get('불명', 0)}")


if __name__ == "__main__":
    main()
