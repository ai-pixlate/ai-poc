"""E1. 원문 지우기 — 골든 샘플 판정표 생성기 (계획 단계 5).

run_golden.py 결과를 읽어 summary_golden.md 와 판정 대지를 만든다.
등급 칸은 비워 둔다. 채우는 건 사람 몫(Claude 1차 판정 → 예람님 검토).

대지 results/golden/board/{섹션}.jpg — 가로로 4칸
    원본 | 마스크(빨강 = erase_s50도 지움 · 주황 = erase_all만 지움) | erase_all | erase_s50

기계 집계
    · 라벨·로고 블록으로 마스크에서 뺀 영역 수
    · 단계 1 판정표의 저신뢰·빈 텍스트 분류(`잡은 것`)를 받아 **글자 아닌 영역이 지워지는 섹션 수**
      — 확정 조건을 erase_all → erase_s50으로 바꾼 근거(2026-09-16 변경)

사용법
    python compare_golden.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLDEN = ROOT / "poc" / "golden"
OUT_DIR = HERE / "results" / "golden"
SUMMARY = HERE / "summary_golden.md"
REGIONS = GOLDEN / "1_B_ocr" / "results" / "baseline" / "regions"
BLOCKS = GOLDEN / "2_block_role" / "results" / "llm_assist" / "blocks"
TRUTH = GOLDEN / "3_product_label" / "results" / "vlm_relation" / "truth.json"
LOGO_META = GOLDEN / "4_logo_match" / "results" / "block_exact" / "meta.json"
OCR_SUMMARY = GOLDEN / "1_B_ocr" / "summary.md"

VARIANTS = ("erase_all", "erase_s50")
GRADE_COLS = ["erase_all", "erase_all 사진영역", "erase_s50", "erase_s50 사진영역", "비고"]
GATE = 0.70
SID = re.compile(r"^A[0-9]+_[0-9]{3}_[0-9]{3}$")
PIPE = re.compile(r"(?<!\\)\|")


def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def cells(line: str) -> list:
    return [c.strip() for c in PIPE.split(line.strip().strip("|"))]


def esc(s: str) -> str:
    return s.replace("|", "\\|").strip()


def read_filled() -> dict:
    """채워진 등급 회수 — 섹션 id 키."""
    got = {}
    if not SUMMARY.exists():
        return got
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = cells(line)
        if len(c) == 5 + len(GRADE_COLS) + 1 and SID.match(c[0]):
            vals = c[5:5 + len(GRADE_COLS)]
            if any(vals):
                got[c[0]] = vals
    return got


def low_score_items() -> list:
    """단계 1 판정표 4장 — 저신뢰·빈 텍스트 영역과 사람이 채운 `잡은 것` 분류."""
    out = []
    if not OCR_SUMMARY.exists():
        return out
    for line in OCR_SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.startswith("| L") and line[3:6].isdigit():
            c = cells(line)
            if len(c) == 8:
                out.append({"lid": c[0], "section": c[1], "n": int(c[2]), "text": c[3],
                            "score": float(c[4]), "kind": c[7]})
    return out


def skipped_regions(sid: str, labels: set, logos: set) -> set:
    blocks = json.loads((BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))["blocks"]
    out = set()
    for i, b in enumerate(blocks, 1):
        if i in labels or (sid, i) in logos:
            out.update(b["regions"])
    return out


def logo_blocks() -> set:
    m = json.loads(LOGO_META.read_text(encoding="utf-8"))
    out = {(r["host_section"], r["host_block"]) for r in m["page_logos"]
           if r["status"] == "찾음" and r["host_section"]}
    out |= {(r["section"], r["block"]) for r in m.get("false_hits", [])}
    return out


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


def board(sid: str) -> None:
    """원본 | 마스크 | erase_all | erase_s50 을 가로로 붙인다."""
    src = cv2.imdecode(np.fromfile(str(OUT_DIR / "sections" / f"{sid}.png"), np.uint8), cv2.IMREAD_COLOR)
    m_all = cv2.imdecode(np.fromfile(str(OUT_DIR / "masks" / "erase_all" / f"{sid}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    m_s50 = cv2.imdecode(np.fromfile(str(OUT_DIR / "masks" / "erase_s50" / f"{sid}.png"), np.uint8), cv2.IMREAD_GRAYSCALE)
    panels = [src]
    tint = src.copy()
    tint[m_all > 0] = (0, 140, 255)   # 주황 — erase_all만 지움
    tint[m_s50 > 0] = (0, 0, 255)     # 빨강 — 두 조건 모두 지움
    panels.append(cv2.addWeighted(src, 0.5, tint, 0.5, 0))
    for v in VARIANTS:
        p = OUT_DIR / v / f"{sid}.png"
        panels.append(cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR))

    head = 34
    h = max(p.shape[0] for p in panels)
    w = sum(p.shape[1] for p in panels) + 3 * 8
    canvas = np.full((h + head, w, 3), 255, np.uint8)
    titles = [f"원본 — {sid}", "마스크 (빨강 = 두 조건 · 주황 = erase_all만)", "erase_all", "erase_s50"]
    x, spots = 0, []
    for p in panels:
        canvas[head:head + p.shape[0], x:x + p.shape[1]] = p
        spots.append(x)
        x += p.shape[1] + 8
    # cv2.putText는 한글을 못 그린다 — 제목만 PIL로 얹는다
    pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    for sx, t in zip(spots, titles):
        draw.text((sx + 6, 6), t, fill=(0, 0, 0), font=_font(22))
    canvas = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    (OUT_DIR / "board").mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(OUT_DIR / "board" / f"{sid}.jpg"))



def dilate_section(grades: dict) -> list:
    """마스크를 넓히면 잔존이 줄어드는가 — run_dilate_golden.py 결과. grades = {섹션: erase_s50 등급}"""
    f = OUT_DIR / "dilate" / "meta.json"
    if not f.exists():
        return []
    m = json.loads(f.read_text(encoding="utf-8"))
    rows, s = m["per_section"], m["summary"]
    L = ["## 5. 마스크를 넓혀 다시 지우기 (`run_dilate_golden.py` · 확정 조건 `erase_s50`)", "",
         f"섹션 {m['sections']} · 지운 영역 {m['regions']:,}. **남은 글자** = 결과를 다시 OCR해 지운 자리에서 읽힌 영역(신뢰도 0.5 이상) · "
         "**얼룩** = 지운 덩어리 안쪽 색과 바깥 둘레 색의 Lab 거리(면적 가중 평균)", "",
         "| 조건 | 내용 | 남은 글자 | 남은 섹션 | 얼룩 평균 | 마스크 | LaMa |", "|---|---|---|---|---|---|---|"]
    desc = {"d15": "확정 조건 — 글자 높이 15% 팽창", "d30": "처음부터 30%", "d50": "처음부터 50%",
            "loop30": f"d15 결과에서 **다시 읽힌 영역만** 30%로 넓혀 한 번 더 ({m['loop_sections']}섹션)"}
    for n in ("d15", "d30", "d50", "loop30"):
        v = s[n]
        L.append(f"| `{n}` | {desc[n]} | {v['left']} ({v['left_rate']}%) | {v['sections_with_left']} | "
                 f"{v['blotch_mean']} | {v['mask_pct_mean']}% | {v['lama_sec']}s |")
    L += ["", "**얼룩 변화 — 섹션 수**(차이 1 초과)", "", "| 조건 | 늘어남 | 줄어듦 | 그대로 |", "|---|---|---|---|"]
    for n in ("d30", "d50"):
        up = sum(1 for r in rows if r[n]["blotch"] - r["d15"]["blotch"] > 1)
        dn = sum(1 for r in rows if r["d15"]["blotch"] - r[n]["blotch"] > 1)
        L.append(f"| `{n}` | {up} | {dn} | {len(rows) - up - dn} |")
    L += ["", "**등급별 얼룩 평균** — 단계 5 `erase_s50` 판정 기준", "", "| 등급 | 섹션 | d15 | d30 | d50 |", "|---|---|---|---|---|"]
    for g in "ABC":
        rs = [r for r in rows if grades.get(r["section"]) == g]
        if rs:
            L.append(f"| {g} | {len(rs)} | " + " | ".join(f"{sum(r[n]['blotch'] for r in rs) / len(rs):.2f}" for n in ("d15", "d30", "d50")) + " |")
    ab = [r["d15"]["blotch"] for r in rows if grades.get(r["section"]) in ("A", "B")]
    c = [r["d15"]["blotch"] for r in rows if grades.get(r["section"]) == "C"]
    L += ["", "**얼룩 지표로 C 가르기** — d15 기준, 임계 이상을 C 후보로 볼 때", "",
          "| 임계 | C 중 잡힘 | A·B 중 잘못 잡힘 |", "|---|---|---|"]
    for th in (3, 5, 8):
        L.append(f"| {th} | {sum(1 for x in c if x >= th)}/{len(c)} | {sum(1 for x in ab if x >= th)}/{len(ab)} |")
    L += ["", "**해석 — 넓혀서 다시 지우는 것은 도움이 되지 않음**", "",
          f"- **OCR로 다시 읽히는 글자는 거의 없음** — {s['d15']['left']}/{m['regions']:,}({s['d15']['left_rate']}%). 판정 비고에 잔상이 적힌 "
          f"{len(m['residue_tagged_sections'])}섹션의 잔상은 대부분 OCR이 못 읽는 희미한 흔적이라, **OCR 재검출로는 루프를 걸 수 없음**",
          "- 루프(`loop30`)는 다시 읽힌 3영역을 모두 없애고 얼룩도 늘리지 않음 — 다만 대상이 3섹션뿐이라 게이트에 영향 없음",
          "- **처음부터 넓히면 얼룩이 늘어남** — 평균 3.38 → 4.59(30%) → 7.04(50%). 50%에서 42섹션이 나빠지고 8섹션만 나아짐. "
          "**A 섹션이 가장 크게 나빠짐**(1.88 → 8.69) — 멀쩡하던 자리를 망가뜨림",
          "- 드물게 나아지는 경우도 있음 — `219554_002_010` 헤드라인 자리 회색 덩어리가 50%에서 사라짐(13.86 → 2.51). 일관되지 않아 규칙으로 쓸 수 없음",
          "- 배지 둘레의 곡선 글자(`인체 적용 테스트 완료`)는 **애초에 마스크에 없어** 넓혀도 남음 — 잔상의 일부는 OCR 미검출이 원인",
          "- **부수 발견: 얼룩 지표는 C에서 높게 나옴**(d15 C 평균 7.23 · A·B 약 1.9). 다만 임계 3에서 C 16/28을 잡는 동안 A·B 8/71도 걸리고, 임계 5에서는 C를 9/28만 잡음 — **단독 판정은 못 하고, 검수 우선순위를 매기는 보조 신호 수준**임",
          "",
          "> 육안 확인은 대지 `results/dilate/board/`(잔상이 적힌 섹션·다시 읽힌 섹션 25개) 중 일부만 봄. 조건별 A/B/C 재판정은 하지 않음", ""]
    return L

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    meta_path = OUT_DIR / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"{meta_path} 없음 — run_golden.py 먼저")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = meta["per_section"]
    filled = read_filled()
    labels_all = json.loads(TRUTH.read_text(encoding="utf-8"))["labels"]
    logos = logo_blocks()
    rel = "results/golden"

    for r in rows:
        board(r["section"])

    # 저신뢰·빈 텍스트 영역이 어느 조건에서 지워지는지
    items = low_score_items()
    for it in items:
        sid = it["section"]
        regions = json.loads((REGIONS / f"{sid}.json").read_text(encoding="utf-8"))["regions"]
        reg = regions[it["n"] - 1]
        skip = skipped_regions(sid, set(labels_all.get(sid, [])), logos)
        it["skipped"] = (it["n"] - 1) in skip
        it["in_all"] = not it["skipped"]
        it["in_s50"] = not it["skipped"] and bool(reg["text"].strip()) and reg["score"] >= 0.5
        it["is_text"] = it["kind"].startswith("글자")

    non_text = [it for it in items if not it["is_text"]]
    text_only = [it for it in items if it["is_text"]]
    nt_sections = sorted({it["section"] for it in non_text if it["in_all"]})
    nt_s50_sections = sorted({it["section"] for it in non_text if it["in_s50"]})
    txt_left = [it for it in text_only if it["in_all"] and not it["in_s50"]]

    L = ["# E1. 원문 지우기 — 골든 샘플 섹션 판정", "",
         "> `compare_golden.py`가 생성함. 재실행해도 **채운 등급은 보존함.**",
         "> 계획 `PoC_골든샘플_재실행_계획.md` 단계 5. 12장 결과(`summary.md`)는 건드리지 않음.", ""]

    L += ["## 1. 실행 조건", "", "| 항목 | 값 |", "|---|---|",
          f"| 모델 · 장치 | LaMa (iopaint) · {meta['device']} |",
          f"| 마스크 | {meta['cfg']['mask']} · 글자 높이 {meta['cfg']['dilate_ratio'] * 100:.0f}% 팽창(최소 {meta['cfg']['dilate_min_px']}px) |",
          f"| 제외 | {meta['cfg']['exclude']} — 라벨 블록 {meta['label_blocks']} · 로고 블록 {meta['logo_blocks']} → 영역 {meta['skipped_regions']}개 |",
          f"| 섹션 · 영역 | {meta['sections']} · {meta['total_regions']} |", ""]
    L += ["| variant | 조건 | 지우는 영역 | 지운 섹션 | LaMa 소요 |", "|---|---|---|---|---|"]
    cond = {"erase_all": "모든 OCR 영역 (기존 확정 조건 — 2026-09-16 폐기)",
            "erase_s50": "신뢰도 0.5 이상 · 텍스트 있는 영역 (**확정 조건** — 2026-09-16 변경)"}
    for v in VARIANTS:
        m = meta["variants"][v]
        L.append(f"| `{v}` | {cond[v]} | {m['total_regions']} | {m['sections_erased']} | {m['lama_sec']}s |")
    L.append("")

    # 2. 확인 항목 — 글자 아닌 영역
    L += ["## 2. 확인 항목 — 글자 아닌 영역이 지워지는가 (기계 집계)", "",
          "단계 1 판정표 4장 `잡은 것` 분류를 그대로 씀. 신뢰도 0.5 미만·빈 텍스트 영역 "
          f"{len(items)}개 중 글자가 아닌 것 {len(non_text)}개.", "",
          "| 구분 | 영역 | 섹션 |", "|---|---|---|",
          f"| 글자 아닌 영역이 `erase_all`에서 지워짐 | {sum(1 for it in non_text if it['in_all'])} | **{len(nt_sections)}** |",
          f"| 글자 아닌 영역이 `erase_s50`에서 지워짐 | {sum(1 for it in non_text if it['in_s50'])} | {len(nt_s50_sections)} |",
          f"| 라벨·로고로 이미 제외됨 | {sum(1 for it in non_text if it['skipped'])} | — |",
          f"| **`erase_s50`이면 안 지워지는 실제 글자** | **{len(txt_left)}** | {len(set(it['section'] for it in txt_left))} |", ""]
    if non_text:
        L += ["**글자 아닌 영역 — 조건별 처리**", "",
              "| L | 섹션 | 영역 | 잡은 것 | 크기 | `erase_all` | `erase_s50` |", "|---|---|---|---|---|---|---|"]
        for it in non_text:
            regions = json.loads((REGIONS / f"{it['section']}.json").read_text(encoding="utf-8"))["regions"]
            x0, y0, x1, y1 = regions[it["n"] - 1]["bbox"]
            mark = lambda b: "지움" if b else ("라벨·로고 제외" if it["skipped"] else "안 지움")
            L.append(f"| {it['lid']} | {it['section']} | {it['n']} | {it['kind']} | {x1 - x0}×{y1 - y0} | "
                     f"{mark(it['in_all'])} | {mark(it['in_s50'])} |")
        L.append("")
    if txt_left:
        L += [f"**`erase_s50`에서 남는 글자 {len(txt_left)}개** — 유형별 " +
              " · ".join(f"{k} {sum(1 for it in txt_left if it['kind'] == k)}"
                         for k in sorted({it["kind"] for it in txt_left})), ""]

    # 3. 판정표
    L += ["## 3. 판정표 (섹션 × 육안 A/B/C — 빈 칸 채울 것)", "",
          "**등급 기준** (원 과업 2.2 [확정])", "",
          "| 등급 | 기준 |", "|---|---|",
          "| **A** | 원문 흔적 없음, 배경과 자연스럽게 이어짐 |",
          "| **B** | 자세히 봐야 티가 남 — 번역문을 얹으면 가려질 수준, 검수로 흡수 가능 |",
          "| **C** | 원문이 읽히거나 왜곡·얼룩이 눈에 띔 |",
          "| **-** | 지운 영역이 없는 섹션(분모 제외) · `사진영역` 두 열은 사진·그라데이션 위 글자가 없을 때 |", "",
          "- `사진영역` 열: 사진·그라데이션 배경 위 글자만 따로 본 등급 (게이트 대상)",
          "- 대지 `" + rel + "/board/{섹션}.jpg` — 원본 | 마스크(빨강 = 두 조건 모두 · 주황 = `erase_all`만) | `erase_all` | `erase_s50`",
          "- 라벨·로고 블록은 마스크에서 빠졌으므로 **제품 인쇄 글자·페이지 로고가 남아 있는 것이 정상**",
          "- 판정 주체: Claude 1차 판정(비고에 \"Claude 육안 판정\") → 예람님 검토", "",
          "| 섹션 | 높이 | 영역 all/s50 | 마스크% all/s50 | 제외 | " + " | ".join(GRADE_COLS) + " | 대지 |",
          "|---|---|---|---|---|" + "---|" * len(GRADE_COLS) + "---|"]
    for r in rows:
        v = filled.get(r["section"], [" "] * len(GRADE_COLS))
        L.append(f"| {r['section']} | {r['size'][1]:,} | {r['erase_all']['regions']}/{r['erase_s50']['regions']} | "
                 f"{r['erase_all']['mask_pct']}/{r['erase_s50']['mask_pct']} | {r['skipped_regions']} | "
                 + " | ".join(v) + f" | [보기]({rel}/board/{r['section']}.jpg) |")
    L.append("")

    # 4. 집계
    L += ["## 4. 집계", ""]
    graded_cols = [[filled.get(r["section"], [""] * len(GRADE_COLS))[i] for r in rows] for i in range(4)]
    if not filled:
        L.append("_판정 전_ — 채워진 등급 없음.")
    else:
        L += ["| variant | 전체 | 사진영역 | 게이트 (A+B 70%) |", "|---|---|---|---|"]
        for k, v in enumerate(VARIANTS):
            a, b = ratio(graded_cols[k * 2]), ratio(graded_cols[k * 2 + 1])
            done = "판정" not in a and "판정" not in b
            pct = [x for x in (a, b) if x != "-" and "판정" not in x]
            gate = "판정 미완" if not done or not pct else (
                "O" if all(int(x.split("(")[1].rstrip("%)")) >= GATE * 100 for x in pct) else "X")
            L.append(f"| `{v}` | {a} | {b} | {gate} |")
        L += ["", "> 게이트 — 섹션 A+B 70%, 사진·그라데이션 위 글자 포함(계획 7장).", ""]
    L.append("")

    L += dilate_section({k: v[2] for k, v in filled.items()})
    SUMMARY.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {SUMMARY}  (섹션 {len(rows)} · 대지 {rel}/board/ · 판정 {len(filled)})")
    print(f"  글자 아닌 영역 지워지는 섹션 — erase_all {len(nt_sections)} · erase_s50 {len(nt_s50_sections)}")
    print(f"  erase_s50에서 안 지워지는 실제 글자 {len(txt_left)}개")


if __name__ == "__main__":
    main()
