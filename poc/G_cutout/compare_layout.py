"""누끼 — 원본 vs 글자 지운 입력 비교기 (`.venv-g`에서 실행).

입력 variant
    birefnet_raw          섹션 원본
    birefnet_erased       OCR 글자 박스 전부 지움 — **1차. 신뢰도 0.0 빈 박스가 얼굴·물방울 위에 잡혀 요소가 지워짐**
    birefnet_erased_s50   인식 신뢰도 0.5 이상 · 텍스트 있는 박스만 지움

기계 집계
    덮인 글자   OCR 글자 박스(전체 기준) 중 전경 마스크가 30% 이상 덮은 수 — 요소에 글자가 섞였다는 신호.
               지운 입력에서 남는 것은 사람·제품 위 글자, 지운 자리의 빈 패널, 지운 자국을 전경으로 잡은 것
    글자 밖 IoU 지운 박스(팽창)를 뺀 영역에서 원본 마스크와의 IoU — 낮으면 사람·제품 마스크가 달라짐(요소 손상 의심)
    큰 덩어리   섹션 면적 0.5% 이상 덩어리 수 — 재배치 요소 후보 수

사람 판정 — `birefnet_erased_s50` 기준으로 대지를 보고 채움
    글자 섞임(원본) · 글자 섞임(s50) — 요소에 페이지 글자가 섞였는가 O/X
    요소 손상(s50) — 지운 입력에서 사람·제품이 잘리거나 사라졌는가 O/X

출력
    results/_compare/{section}.jpg   원본 | 원본 누끼 | 지운 입력 | 지운 누끼 | s50 입력 | s50 누끼
    summary.md

사용법
    python compare_layout.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SECTIONS = ROOT / "poc" / "section_split" / "results" / "color_snap_vlm2"
OCR = ROOT / "poc" / "ocr_split" / "results" / "section_vlm2" / "regions"
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

RAW = "birefnet_raw"
ERASED = {"birefnet_erased": "_erase", "birefnet_erased_s50": "_erase_s50"}
LABEL = {"birefnet_raw": "원본", "birefnet_erased": "전부 지움", "birefnet_erased_s50": "s50 지움"}
COVER = 0.30
PANEL_H = 900
JUDGE = ["글자 섞임(원본)", "글자 섞임(s50)", "요소 손상(s50)", "비고"]
FIXED = 7


def checker(h: int, w: int, size: int = 16) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where((((yy // size) + (xx // size)) % 2)[..., None], 210, 245).astype(np.uint8).repeat(3, axis=2)


def on_checker(img: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    a = alpha[..., None].astype(np.float32) / 255
    return (img * a + checker(*alpha.shape) * (1 - a)).astype(np.uint8)


PANEL_NAME = {
    RAW: ("원본 누끼", "birefnet-general"),
    "birefnet_erased": ("전부 지운 입력", "LaMa · OCR 박스 전부"),
    "birefnet_erased_s50": ("s50 지운 입력", "LaMa · 신뢰도≥0.5만"),
}
MIN_PANEL_W = 230
HEAD_H = 58


def _font(size: int):
    from PIL import ImageFont
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def labeled_sheet(section: str, panels: list[np.ndarray], labels: list[tuple[str, str]]) -> np.ndarray:
    """칸마다 위에 이름(1줄)·모델(2줄)을 적고 가로로 붙인다. 좁은 칸은 이름이 들어가게 좌우를 넓힌다."""
    from PIL import Image, ImageDraw

    h = panels[0].shape[0]
    cols = []
    for p in panels:
        if p.shape[1] < MIN_PANEL_W:
            pad = MIN_PANEL_W - p.shape[1]
            p = cv2.copyMakeBorder(p, 0, 0, pad // 2, pad - pad // 2, cv2.BORDER_CONSTANT, value=(120, 120, 120))
        cols.append(p)
    gaps = [12 if i % 2 == 0 else 30 for i in range(len(cols) - 1)]
    width = sum(c.shape[1] for c in cols) + sum(gaps)
    canvas = Image.new("RGB", (width, h + HEAD_H + 30), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 4), section, fill=(200, 0, 0), font=_font(18))
    f1, f2 = _font(16), _font(13)
    x = 0
    for i, (c, (name, model)) in enumerate(zip(cols, labels)):
        w = c.shape[1]
        pair = i // 2
        bg = (235, 240, 250) if pair % 2 == 0 else (250, 240, 230)
        draw.rectangle([x, 30, x + w - 1, 30 + HEAD_H - 1], fill=bg)
        draw.text((x + 6, 34), f"{i + 1}. {name}", fill=(20, 20, 20), font=f1)
        draw.text((x + 6, 56), model, fill=(90, 90, 90), font=f2)
        canvas.paste(Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)), (x, 30 + HEAD_H))
        x += w
        if i < len(gaps):
            draw.rectangle([x, 30, x + gaps[i] - 1, 30 + HEAD_H + h], fill=(90, 90, 90) if gaps[i] == 12 else (30, 30, 30))
            x += gaps[i]
    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def read(p: Path, flag=cv2.IMREAD_COLOR) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def read_filled() -> dict[str, list[str]]:
    if not OUT.exists():
        return {}
    got = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("| `A0") and len(c) == FIXED + len(JUDGE):
            vals = c[FIXED:]
            if any(vals):
                got[c[0].strip("`")] = vals
    return got


OCR_META = ROOT / "poc" / "ocr_split" / "results" / "section_vlm2" / "meta.json"
RULE_JUDGE = ["그래픽 잔존", "대상 누락", "비고"]
# variant → 판정표 앞쪽 고정 열 수. 판정표를 열 수로 구분함(rule_flat은 깎음%, vlm_pick은 혼합·VLM 판단 열이 더 있음)
RULE_FIXED = {"rule_comp": 4, "rule_flat": 5, "vlm_pick": 6, "sam_pick": 7}


def read_rule_filled(variant: str) -> dict[str, list[str]]:
    if not OUT.exists():
        return {}
    got, fixed = {}, RULE_FIXED[variant]
    for line in OUT.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("| `A0") and len(c) == fixed + len(RULE_JUDGE):
            vals = c[fixed:]
            if any(vals):
                got[c[0].strip("`")] = vals
    return got


def sam_section(number: int, filled: dict[str, list[str]]) -> list[str]:
    """붙은 그래픽 분리 `sam_pick` — SAM 2 조각을 VLM이 고름. 표본 섹션만."""
    d = RESULTS / "sam_pick"
    if not (d / "answers.json").exists():
        return []
    ans = json.loads((d / "answers.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    parts = json.loads((RESULTS / "sam_parts" / "parts.json").read_text(encoding="utf-8"))
    regions = [p for a in ans.values() for p in a["regions"]]
    kinds: dict[str, int] = {}
    for p in regions:
        k = p["kind"] or "응답 없음"
        kinds[k] = kinds.get(k, 0) + 1
    cost = meta["all_answers"]
    sam_sec = [parts[s]["sec"] for s in ans if s in parts]
    L = [f"## {number}. 붙은 그래픽 분리 — `sam_pick`", "",
         "`run_sam_parts.py`(SAM 2 `sam2.1_hiera_small` 자동 분할 · 로컬 GPU)로 누끼 전경을 **물체 단위 조각**으로 쪼갠 뒤 "
         f"`run_vlm_pick.py --variant sam_pick`(프롬프트 v2 — 3D 렌더 대상 추가)으로 `{meta['model']}`가 조각 번호를 고름.", "",
         "표본 — `vlm_pick` 그래픽 잔존·대상 누락 섹션 + 대조군(이상 없던 섹션). 판정 칸은 5~7장과 같고, **조각을 빠뜨려 생긴 구멍도 대상 누락**으로 셈.", "",
         "| 항목 | 값 |", "|---|---|",
         f"| 섹션 | {len(ans)} |",
         f"| 조각 | {len(regions)} · 남김 {sum(p['keep'] for p in regions)} · 응답 누락 {sum(p['missing'] for p in regions)} |",
         "| 판단 종류 | " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])) + " |",
         f"| SAM 2 소요 | 섹션당 평균 {sum(sam_sec) / max(1, len(sam_sec)):.1f}s |",
         f"| 토큰 · 비용 | 입력 {cost['tokens_in']:,} · 출력 {cost['tokens_out']:,} · **${cost['cost_usd']}** |", "",
         "`results/sam_pick/vis/{섹션}.jpg` — 조각 번호 그린 섹션(VLM 입력) | 선별 결과 + 번호별 판단. `results/sam_parts/vis/` — 조각 색칠.", "",
         "| 섹션 | SAM 마스크 | 조각 | 남김 | 요소 없음 | 혼합 | VLM 판단 | " + " | ".join(RULE_JUDGE) + " |",
         "|---|---|---|---|---|---|---|" + "---|" * len(RULE_JUDGE)]
    for s in sorted(ans):
        regs = ans[s]["regions"]
        kept = sum(p["keep"] for p in regs)
        mixed = sum(1 for p in regs if p["kind"] == "혼합")
        brief = " · ".join(f"#{p['id']} {p['kind'] or '?'}" for p in regs)
        vals = filled.get(s, [""] * len(RULE_JUDGE))
        L.append(f"| `{s}` | {parts.get(s, {}).get('sam_masks', '')} | {len(regs)} | {kept} | {'O' if kept == 0 else ''} | "
                 f"{mixed or ''} | {brief} | " + " | ".join(vals) + " |")
    L.append("")
    judged = [filled[s] for s in ans if s in filled]
    if judged:
        cnt = lambda i, v: sum(1 for j in judged if j[i].strip() == v)
        L += [f"판정 {len(judged)}/{len(ans)}섹션.", "", "| 항목 | O | X | — |", "|---|---|---|---|"]
        for i, name in enumerate(RULE_JUDGE[:2]):
            L.append(f"| {name} | **{cnt(i, 'O')}** | {cnt(i, 'X')} | {cnt(i, '—')} |")
        L.append("")
    return L


def vlm_section(number: int, filled: dict[str, list[str]]) -> list[str]:
    """요소 선별 `vlm_pick` — 덩어리 번호를 VLM이 고름. 기계 집계 + 판정표."""
    d = RESULTS / "vlm_pick"
    if not (d / "answers.json").exists():
        return []
    ans = json.loads((d / "answers.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    rule = json.loads((RESULTS / "rule_comp" / "features.json").read_text(encoding="utf-8"))
    regions = [p for a in ans.values() for p in a["regions"]]
    kinds: dict[str, int] = {}
    for p in regions:
        k = p["kind"] or "응답 없음"
        kinds[k] = kinds.get(k, 0) + 1
    kept_of = {s: sum(p["keep"] for p in a["regions"]) for s, a in ans.items()}
    no_elem = sum(1 for r in rule if kept_of.get(r["section"], 0) == 0)
    cost = meta["all_answers"]
    L = [f"## {number}. 요소 선별 — `vlm_pick`", "",
         f"`run_vlm_pick.py` · `rule_comp`와 같은 덩어리에 **윤곽선·번호를 그려** `{meta['model']}`가 대상 번호를 고름. "
         "좌표를 묻지 않음. 대상과 그래픽이 한 덩어리면 `혼합`으로 남김.", "",
         "| 항목 | 값 |", "|---|---|",
         f"| 호출 섹션 (덩어리 1개 이상) | {len(ans)} |",
         f"| 덩어리 | {len(regions)} · 남김 {sum(p['keep'] for p in regions)} · 응답 누락 {sum(p['missing'] for p in regions)} |",
         "| 판단 종류 | " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])) + " |",
         f"| 요소 없음 섹션 | {no_elem} |",
         f"| 토큰 · 비용 | 입력 {cost['tokens_in']:,} · 출력 {cost['tokens_out']:,} · **${cost['cost_usd']}** |", "",
         "`results/vlm_pick/vis/{섹션}.jpg` — 번호 그린 섹션(VLM 입력) | 선별 결과 + 번호별 판단.",
         "**판정 칸**은 5·6장과 같음.", "",
         "| 섹션 | 덩어리 | 남김 | 요소 없음 | 혼합 | VLM 판단 | " + " | ".join(RULE_JUDGE) + " |",
         "|---|---|---|---|---|---|" + "---|" * len(RULE_JUDGE)]
    for r in rule:
        s = r["section"]
        regs = ans.get(s, {}).get("regions", [])
        kept = kept_of.get(s, 0)
        mixed = sum(1 for p in regs if p["kind"] == "혼합")
        brief = " · ".join(f"#{p['id']} {p['kind'] or '?'}" for p in regs) or "호출 안 함"
        vals = filled.get(s, [""] * len(RULE_JUDGE))
        L.append(f"| `{s}` | {len(regs)} | {kept} | {'O' if kept == 0 else ''} | {mixed or ''} | {brief} | " + " | ".join(vals) + " |")
    L.append("")
    judged = [filled[r["section"]] for r in rule if r["section"] in filled]
    if judged:
        cnt = lambda i, v: sum(1 for j in judged if j[i].strip() == v)
        L += [f"판정 {len(judged)}/{len(rule)}섹션.", "", "| 항목 | O | X | — |", "|---|---|---|---|"]
        for i, name in enumerate(RULE_JUDGE[:2]):
            L.append(f"| {name} | **{cnt(i, 'O')}** | {cnt(i, 'X')} | {cnt(i, '—')} |")
        L.append("")
    return L


def rule_section(variant: str, number: int, filled: dict[str, list[str]]) -> list[str]:
    """요소 선별 variant — 기계 집계 + 판정표(판정 칸은 사람이 채움)."""
    d = RESULTS / variant
    if not (d / "features.json").exists():
        return []
    rows = json.loads((d / "features.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    flat = variant == "rule_flat"
    how = (f"덩어리로 쪼개기 **전에** 평평한 영역(창 {meta.get('flat_win')}px 안 채널 차이 ≤ {meta.get('flat_range')} · "
           f"면적 {meta.get('flat_min_area', 0) * 100:.1f}% 이상 · 최소 외접 사각형 채움률 ≥ {meta.get('flat_rect')})을 "
           f"{meta.get('carve_dilate')}px 넓혀 깎고, " if flat else "")
    L = [f"## {number}. 요소 선별 — `{variant}`", "",
         f"`run_rule.py --variant {variant}` · s50 누끼 마스크에서 {how}덩어리로 쪼개 "
         f"**색 수 ≥ {meta['min_colors']} · 질감 비율 ≥ {meta['min_textured']}**인 덩어리만 남김. "
         f"면적 {meta['min_area'] * 100:.1f}% 미만 덩어리는 버림. 비용 0 · 섹션당 {meta['sec_per_section']}s.", "",
         "- **대상** — 사람 · 제품 · 사진류(피부 전후 · 원료 · 제형 · 현미경)",
         "- **버림** — 그래픽(말풍선 · 배지 · 차트 · 아이콘 · 패널 · 선) · 도식 · 문서 이미지 · 지운 자국", "",
         "| 항목 | 값 |", "|---|---|",
         f"| 덩어리 (면적 기준 이상) | {meta['components']} |", f"| 남긴 덩어리 | {meta['kept']} |",
         f"| 요소 없음 섹션 (남긴 덩어리 0) | {meta['no_element']} |", "",
         f"`results/{variant}/vis/{{섹션}}.jpg` — 1. s50 누끼 | 2. {'평평한 영역 깎음(붉은 칠) + ' if flat else ''}"
         "덩어리(초록 남김 · 빨강 버림, t=질감 비율 · c=색 수) | 3. 선별 결과.",
         "**판정 칸** — `그래픽 잔존`: 선별 결과에 그래픽·도식·문서·지운 자국이 남음 O/X · "
         "`대상 누락`: s50 누끼에 있던 사람·제품·사진류를 버리거나 구멍을 냄 O/X, 대상이 없으면 —.", "",
         "| 섹션 | " + ("깎음% | " if flat else "") + "덩어리 | 남김 | 요소 없음 | " + " | ".join(RULE_JUDGE) + " |",
         "|---|" + ("---|" if flat else "") + "---|---|---|" + "---|" * len(RULE_JUDGE)]
    for r in rows:
        vals = filled.get(r["section"], [""] * len(RULE_JUDGE))
        L.append(f"| `{r['section']}` | " + (f"{r.get('carved_pct', 0)} | " if flat else "")
                 + f"{r['components']} | {r['kept']} | {'O' if r['no_element'] else ''} | " + " | ".join(vals) + " |")
    L.append("")
    judged = [filled[r["section"]] for r in rows if r["section"] in filled]
    if judged:
        cnt = lambda i, v: sum(1 for j in judged if j[i].strip() == v)
        L += [f"판정 {len(judged)}/{len(rows)}섹션.", "", "| 항목 | O | X | — |", "|---|---|---|---|"]
        for i, name in enumerate(RULE_JUDGE[:2]):
            L.append(f"| {name} | **{cnt(i, 'O')}** | {cnt(i, 'X')} | {cnt(i, '—')} |")
        L.append("")
    return L


def timing_section(names: list[str], by: dict, variants: list[str]) -> list[str]:
    """원본 이미지 1장 단위 소요 — 섹션 OCR + 글자 지우기(LaMa) + 누끼.

    OCR·누끼는 실측 합. LaMa는 배치 1회로 돌려 섹션별 시간이 없어 **배치 총시간 ÷ 지운 섹션 수**를
    그 이미지의 지운 섹션 수만큼 곱한 추정치(모델 적재 시간 포함).
    """
    ocr = {Path(p["image"]).stem: p["sec"] for p in json.loads(OCR_META.read_text(encoding="utf-8"))["per_image"]}
    s50 = "birefnet_erased_s50"
    em = json.loads((RESULTS / ERASED[s50] / "meta.json").read_text(encoding="utf-8"))
    erased_by = {r["section"]: r["regions"] > 0 for r in em["per_section"]}
    lama_per = em["lama_sec"] / max(1, sum(erased_by.values()))

    per = {}
    for name in names:
        stem = name.rsplit("_", 1)[0]
        d = per.setdefault(stem, {"n": 0, "lama": 0.0, "raw": 0.0, "s50": 0.0})
        d["n"] += 1
        d["lama"] += lama_per if erased_by.get(name) else 0.0
        d["raw"] += by[RAW][name]["sec"]
        if s50 in variants:
            d["s50"] += by[s50][name]["sec"]
    rows = []
    for stem, d in per.items():
        h = json.loads((SECTIONS / "sections" / f"{stem}.json").read_text(encoding="utf-8"))["size"][1]
        total = ocr[stem] + d["lama"] + d["s50"]
        rows.append((stem, h, d["n"], ocr[stem], d["lama"], d["s50"], total, d["raw"]))

    def stat(i):
        vals = sorted(r[i] for r in rows)
        return sum(vals) / len(vals), vals[len(vals) // 2], vals[-1]

    n_sec = sum(r[2] for r in rows)
    L = ["## 4. 소요 시간 — 원본 이미지 1장 기준", "",
         f"골든 샘플 {len(rows)}장 · 섹션 {n_sec}개. **s50 흐름** = 섹션 OCR(GPU) → 글자 지우기 LaMa(GPU) → 누끼 `birefnet-general`(**CPU**).",
         f"LaMa는 배치 1회 실행이라 섹션별 시간이 없어 **총 {em['lama_sec']}s ÷ 지운 섹션 {sum(erased_by.values())}개 = 섹션당 {lama_per:.2f}s**로 추정(모델 적재 포함).", "",
         "| 단계 | 평균 | 중앙 | 최대 | 섹션당 평균 |", "|---|---|---|---|---|"]
    for label, i in (("섹션 OCR", 3), ("글자 지우기 (LaMa, 추정)", 4), ("누끼 (s50 입력)", 5), ("**s50 흐름 합계**", 6),
                     ("참고 — 원본 입력 누끼만", 7)):
        a, m, x = stat(i)
        L.append(f"| {label} | {a:.1f}s | {m:.1f}s | {x:.1f}s | {sum(r[i] for r in rows) / n_sec:.2f}s |")
    L += ["", "- 누끼가 합계의 대부분 — CPU 실행이라 섹션당 약 12초. **GPU 실행은 측정 안 함**", "",
          "| 이미지 | 높이 | 섹션 | OCR | LaMa(추정) | 누끼 | 합계 |", "|---|---|---|---|---|---|---|"]
    for stem, h, n_s, o, la, cu, tot, _ in sorted(rows):
        L.append(f"| {stem} | {h:,}px | {n_s} | {o:.1f}s | {la:.1f}s | {cu:.1f}s | **{tot:.1f}s** |")
    L.append("")
    return L


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    filled = read_filled()
    rule_filled = {v: read_rule_filled(v) for v in RULE_FIXED}
    (RESULTS / "_compare").mkdir(parents=True, exist_ok=True)
    variants = [RAW] + [v for v in ERASED if (RESULTS / v / "meta.json").exists()]
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in variants}
    by = {v: {r["section"]: r for r in metas[v]["per_section"]} for v in variants}
    erase_meta = {v: {r["section"]: r for r in json.loads((RESULTS / d / "meta.json").read_text(encoding="utf-8"))["per_section"]}
                  for v, d in ERASED.items() if v in variants}

    rows, cache = [], {}
    for name in by[RAW]:
        if not all(name in by[v] for v in variants):
            continue
        stem, idx = name.rsplit("_", 1)
        if stem not in cache:
            cache[stem] = (json.loads((SECTIONS / "sections" / f"{stem}.json").read_text(encoding="utf-8")),
                           json.loads((OCR / f"{stem}.json").read_text(encoding="utf-8")))
        secs = cache[stem][0]["sections"]
        ci = next(i for i, s in enumerate(secs) if s["index"] == int(idx))
        s = secs[ci]
        regs = [r for r in cache[stem][1]["regions"] if r["chunk"] == ci]

        img = read(SECTIONS / s["crop"])
        masks = {v: read(RESULTS / v / "mask" / f"{name}.png", cv2.IMREAD_GRAYSCALE) > 127 for v in variants}

        def covered(fg):
            n = 0
            for r in regs:
                x1, y1, x2, y2 = r["bbox"]
                box = fg[max(0, y1 - s["top_offset"]):y2 - s["top_offset"], max(0, x1):x2]
                n += bool(box.size and box.mean() >= COVER)
            return n

        row = {"section": name, "regions": len(regs), "cov": {}, "fg": {}, "big": {}, "iou": {}, "mask_pct": {}}
        panels = [img, on_checker(img, masks[RAW].astype(np.uint8) * 255)]
        for v in variants:
            row["cov"][v] = covered(masks[v])
            row["fg"][v] = by[v][name]["foreground_pct"]
            row["big"][v] = by[v][name]["big_components"]
        row["on_fg"] = {}
        for v in variants[1:]:
            d = RESULTS / ERASED[v]
            tm = read(d / "masks" / f"{name}.png", cv2.IMREAD_GRAYSCALE) == 0
            # 요소 안쪽 손상은 윤곽이 그대로라 IoU로 안 잡힘 — 원본 전경 중 지운 비율로 봄
            fg_px = masks[RAW].sum()
            row["on_fg"][v] = float((masks[RAW] & ~tm).sum() / fg_px * 100) if fg_px else 0.0
            inter = (masks[RAW] & masks[v] & tm).sum()
            union = ((masks[RAW] | masks[v]) & tm).sum()
            row["iou"][v] = inter / union if union else 1.0
            row["mask_pct"][v] = erase_meta[v][name]["mask_pct"]
            ers = read(d / "erased" / f"{name}.png")
            panels += [ers, on_checker(ers, masks[v].astype(np.uint8) * 255)]
        rows.append(row)

        r = PANEL_H / img.shape[0]
        panels = [cv2.resize(p, (max(1, int(p.shape[1] * r)), PANEL_H)) for p in panels]
        labels = [("원본", "섹션 크롭"), PANEL_NAME[RAW]]
        for v in variants[1:]:
            labels += [PANEL_NAME[v], (f"{PANEL_NAME[v][0].replace(' 입력', '')} 누끼", "birefnet-general")]
        sheet = labeled_sheet(name, panels, labels)
        cv2.imwrite(str(RESULTS / "_compare" / f"{name}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])

    n = len(rows)
    arrow = lambda d, f="{}": "→".join(f.format(d[v]) for v in variants)
    L = ["# 누끼 — 원본 vs 글자 지운 입력", "",
         "> `compare_layout.py`가 생성함. **목적: 세로→가로 재배치용 요소 분리(사람·제품 포함).** "
         "페이지 글자는 조판으로 다시 그리므로 요소에 섞이면 안 됨.",
         "> 입력: 골든 샘플 `color_snap_vlm2` 섹션 102개 · 글자 영역은 섹션 단위 OCR · 지우기는 LaMa(글자 높이 15% 팽창, bbox 사각형) · "
         "누끼 `birefnet-general`. **제품 인쇄 글자도 함께 지움**(골든 샘플 라벨 판정 미실행).", "",
         "## 1. 집계 (기계)", "",
         "| 항목 | " + " | ".join(f"{LABEL[v]} `{v}`" for v in variants) + " |",
         "|---|" + "---|" * len(variants),
         "| 전경에 덮인 글자 박스 (≥30%) | " + " | ".join(f"**{sum(r['cov'][v] for r in rows)}**" for v in variants) + " |",
         "| 글자 박스가 덮인 섹션 | " + " | ".join(str(sum(1 for r in rows if r['cov'][v])) for v in variants) + " |",
         "| 큰 덩어리 합 | " + " | ".join(str(sum(r['big'][v] for r in rows)) for v in variants) + " |",
         "| 글자 밖 IoU < 0.8 섹션 (원본 대비) | — | " + " | ".join(
             str(sum(1 for r in rows if r['iou'][v] < 0.8 and max(r['fg'][RAW], r['fg'][v]) > 1)) for v in variants[1:]) + " |",
         "| 지운 면적 평균 | — | " + " | ".join(f"{sum(r['mask_pct'][v] for r in rows) / n:.1f}%" for v in variants[1:]) + " |",
         "| **요소 위 지운 면적 10% 초과 섹션** (원본 전경 중 지운 비율) | — | " + " | ".join(
             str(sum(1 for r in rows if r['on_fg'][v] > 10 and r['fg'][RAW] > 1)) for v in variants[1:]) + " |",
         "| 소요 | " + " | ".join(f"{metas[v]['total_sec']}s" for v in variants) + " |", "",
         f"- 섹션 {n}개 · OCR 글자 박스 {sum(r['regions'] for r in rows)}개",
         "- `birefnet_erased`는 **인식 신뢰도 0.0 빈 박스가 얼굴·물방울·아이콘 위에 잡혀 LaMa가 요소를 지운 사례**가 있어 비교가 오염됨. "
         "판정은 `birefnet_erased_s50` 기준", "",
         "## 2. 섹션별 — 판정표", "",
         "`results/_compare/{섹션}.jpg` — " + " | ".join(
             ["원본", "원본 누끼"] + sum(([f"{LABEL[v]} 입력", f"{LABEL[v]} 누끼"] for v in variants[1:]), [])) + ". **판정 칸 3개를 O/X로 채움.**", "",
         f"| 섹션 | 글자 박스 | 덮인 글자({'→'.join(LABEL[v] for v in variants)}) | 전경% | 큰 덩어리 | "
         f"글자 밖 IoU · 요소 위 지운%({'·'.join(LABEL[v] for v in variants[1:])}) | 지운 면적% | " + " | ".join(JUDGE) + " |",
         "|---|---|---|---|---|---|---|" + "---|" * len(JUDGE)]
    for r in rows:
        vals = filled.get(r["section"], [""] * len(JUDGE))
        iou = " · ".join(f"{r['iou'][v]:.2f}{' ⚠' if r['iou'][v] < 0.8 and max(r['fg'][RAW], r['fg'][v]) > 1 else ''}"
                         f" / {r['on_fg'][v]:.0f}%{' ⚠' if r['on_fg'][v] > 10 and r['fg'][RAW] > 1 else ''}"
                         for v in variants[1:])
        L.append(f"| `{r['section']}` | {r['regions']} | {arrow(r['cov'])} | {arrow(r['fg'])} | {arrow(r['big'])} | {iou} | "
                 f"{' · '.join(str(r['mask_pct'][v]) for v in variants[1:])} | " + " | ".join(vals) + " |")
    L.append("")

    judged = [filled[r["section"]] for r in rows if r["section"] in filled]
    if judged:
        def cnt(i, v):
            return sum(1 for j in judged if j[i].strip() == v)
        no_elem = sum(1 for j in judged if j[3].startswith("요소 없음"))
        L += ["## 3. 판정 집계", "", f"판정 {len(judged)}/{n}섹션.", "",
              "| 항목 | O | X | — |", "|---|---|---|---|"]
        for i, name in enumerate(JUDGE[:3]):
            L.append(f"| {name} | **{cnt(i, 'O')}** | {cnt(i, 'X')} | {cnt(i, '—')} |")
        L += ["", f"- **요소 없음** (사람·제품 없이 빈 패널·지운 자국·그래픽만 요소로 나옴) — {no_elem}섹션", ""]

    L += timing_section([r["section"] for r in rows], by, variants)
    L += rule_section("rule_comp", 5, rule_filled["rule_comp"])
    L += rule_section("rule_flat", 6, rule_filled["rule_flat"])
    L += vlm_section(7, rule_filled["vlm_pick"])
    L += sam_section(8, rule_filled["sam_pick"])
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}")
    for v in variants:
        print(f"  {v:<22} 덮인 글자 {sum(r['cov'][v] for r in rows):>5}  큰 덩어리 {sum(r['big'][v] for r in rows):>4}"
              + (f"  IoU<0.8 {sum(1 for r in rows if r['iou'][v] < 0.8 and max(r['fg'][RAW], r['fg'][v]) > 1)}" if v != RAW else ""))


if __name__ == "__main__":
    main()
