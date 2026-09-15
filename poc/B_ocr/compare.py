"""B. 텍스트 추출 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
등급 칸은 비워둔다. 채우는 건 사람 몫.

**이미 채워진 등급은 재실행해도 보존한다.** 기존 summary.md의 판정표를
(이미지, variant) 키로 읽어 되돌려 넣는다. variant를 추가하고 다시 돌려도
앞서 매긴 등급이 날아가지 않는다.

집계표는 채워진 등급에서 계산한다. 사람이 넣은 값의 산술 결과일 뿐,
비어 있는 칸을 추정하지 않는다.

--sample golden
    results/golden/baseline/ 을 읽어 summary_golden.md 를 만든다. 섹션 단위 판정표.
    · 4,000px 초과 섹션 분할 결과를 ocr_split 결과(분할 전 · 참조)와 기계 대조
    · 저신뢰·빈 텍스트 영역을 잘라 모은 시트 results/golden/baseline/_lowscore/
    · 섹션별 인식 텍스트 results/golden/baseline/texts.md
    채운 등급 · '잡은 것' 칸은 섹션 id 키로 보존한다.

사용법
    python compare.py
    python compare.py --sample golden
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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


def main_default() -> None:
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


# ── 골든 샘플 — 섹션 단위 ────────────────────────────────────────────────
GOLDEN = RESULTS / "golden"
GOLDEN_VARIANT = "baseline"
GOLDEN_OUT = HERE / "summary_golden.md"
OCR_SPLIT = HERE.parent / "ocr_split" / "results"   # 분할 전 결과 · 참조 — 데이터만 읽음
GOLDEN_SRC = HERE.parents[1] / "data" / "golden_sample"
LOW_SCORE = 0.5
SHEET_COLS, SHEET_ROWS = 5, 6
CELL_W, THUMB_H, CAP_H = 320, 170, 48
# 이음선 참조 — 그 자리가 조각 한가운데(경계에서 300px 이상)인 ocr_split variant. ocr_split과 같은 규칙
SEAM_REFS = ("tile_2000_ov300", "unit_ws_std", "tile_2000")
REF_MARGIN = 300

SID = re.compile(r"^A\d+_\d{3}_\d{3}$")
LID = re.compile(r"^L\d{3}$")


def cells_of(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def read_golden_kept() -> tuple[dict[str, list[str]], dict[tuple[str, str], str]]:
    """summary_golden.md에서 채워진 등급(섹션 id 키)과 '잡은 것' 칸((섹션, 영역#) 키)을 회수."""
    grades: dict[str, list[str]] = {}
    found: dict[tuple[str, str], str] = {}
    if not GOLDEN_OUT.exists():
        return grades, found
    for line in GOLDEN_OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = cells_of(line)
        if len(c) == len(GRADE_COLS) + 4 and SID.match(c[0]):
            vals = c[3 : 3 + len(GRADE_COLS)]
            if any(vals):
                grades[c[0]] = vals
        elif len(c) == 8 and LID.match(c[0]) and c[7]:
            found[(c[1], c[2])] = c[7]
    return grades, found


def iou(a: list[int], b: list[int]) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if not inter:
        return 0.0
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def split_page(variant: str, stem: str) -> dict:
    return json.loads((OCR_SPLIT / variant / "regions" / f"{stem}.json").read_text(encoding="utf-8"))


def in_range(regions: list[dict], t: int, b: int) -> list[dict]:
    return [r for r in regions if t <= (r["bbox"][1] + r["bbox"][3]) / 2 < b]


def page_bbox(r: dict, off: int) -> list[int]:
    x0, y0, x1, y1 = r["bbox"]
    return [x0, y0 + off, x1, y1 + off]


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d * 100:.1f}%)" if d else "-"


def make_sheets(items: list[dict], out_dir: Path) -> None:
    """저신뢰·빈 텍스트 영역을 원본에서 여유 있게 잘라 격자로 모은다."""
    from PIL import Image, ImageDraw, ImageFont

    Image.MAX_IMAGE_PIXELS = None

    def kfont(size):
        for name in ("malgun.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    font = kfont(13)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("sheet_*.jpg"):
        old.unlink()
    paths = {p.name: p for p in GOLDEN_SRC.rglob("*.jpg")}
    per = SHEET_COLS * SHEET_ROWS
    cell_h = THUMB_H + CAP_H
    page_name, page = None, None
    for si in range(0, len(items), per):
        chunk = items[si : si + per]
        rows = (len(chunk) + SHEET_COLS - 1) // SHEET_COLS
        sheet = Image.new("RGB", (SHEET_COLS * CELL_W, rows * cell_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        for k, it in enumerate(chunk):
            if it["image"] != page_name:
                page_name = it["image"]
                page = Image.open(paths[page_name]).convert("RGB")
            x0, y0, x1, y1 = it["page_bbox"]
            bw, bh = x1 - x0, y1 - y0
            pad = max(16, bh // 2)
            cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
            cx1, cy1 = min(page.width, x1 + pad), min(page.height, y1 + pad)
            crop = page.crop((cx0, cy0, cx1, cy1))
            scale = min((CELL_W - 12) / crop.width, (THUMB_H - 8) / crop.height, 3.0)
            tw, th = max(1, int(crop.width * scale)), max(1, int(crop.height * scale))
            thumb = crop.resize((tw, th))
            gx, gy = (k % SHEET_COLS) * CELL_W, (k // SHEET_COLS) * cell_h
            ox, oy = gx + (CELL_W - tw) // 2, gy + (THUMB_H - th) // 2
            sheet.paste(thumb, (ox, oy))
            draw.rectangle([ox + (x0 - cx0) * scale, oy + (y0 - cy0) * scale,
                            ox + (x1 - cx0) * scale, oy + (y1 - cy0) * scale],
                           outline=(200, 0, 200) if it["empty"] else (255, 140, 0), width=2)
            text = it["text"] if it["text"].strip() else "(빈)"
            draw.text((gx + 6, gy + THUMB_H + 2), f"{it['lid']}  {it['section']} #{it['n']}",
                      fill=(0, 0, 0), font=font)
            draw.text((gx + 6, gy + THUMB_H + 22), f"{it['score']:.2f}  {bw}x{bh}px  {text[:16]}",
                      fill=(90, 90, 90), font=font)
            draw.rectangle([gx, gy, gx + CELL_W - 1, gy + cell_h - 1], outline=(220, 220, 220))
        sheet.save(out_dir / f"sheet_{si // per + 1:02d}.jpg", quality=90)


def main_golden() -> None:
    base = GOLDEN / GOLDEN_VARIANT
    if not (base / "meta.json").exists():
        raise SystemExit("results/golden/baseline/meta.json 없음. run.py --sample golden 먼저 실행.")
    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    secs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((base / "regions").glob("*.json"))]
    grades, found = read_golden_kept()
    rel = f"results/golden/{GOLDEN_VARIANT}"

    L: list[str] = []
    L.append("# B. 텍스트 추출 — 골든 샘플 섹션 판정")
    L.append("")
    L.append("> `compare.py --sample golden`이 생성함. 재실행 시 덮어쓰되 **채운 등급 · '잡은 것' 칸은 보존함.**")
    L.append("> 계획 `PoC_골든샘플_재실행_계획.md` 단계 1. 12장 결과(`summary.md`)는 건드리지 않음.")
    L.append("")

    # 1. 실행 요약
    total = meta["total_regions"]
    L.append("## 1. 실행 요약")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|---|---|")
    L.append(f"| 입력 | 골든 샘플 34장 → `color_snap_vlm2` 섹션 {meta['sections']}개 |")
    L.append(f"| 조건 | `{GOLDEN_VARIANT}` — {esc(', '.join(f'{k}={v}' for k, v in meta['kwargs'].items()))} |")
    sr = meta["split_rule"]
    L.append(f"| 추가 분할 | {sr['det_limit']:,}px 초과 섹션 — 여백(std ≤ {sr['blank']['tol']} · {sr['blank']['min_gap']}px 연속) 우선, "
             f"없으면 {sr['band']['size']:,}px 띠 · {sr['band']['overlap']}px 겹침 |")
    L.append(f"| 분할된 섹션 | {len(meta['split_sections'])}개 — " + (", ".join(f"`{s}`" for s in meta["split_sections"]) or "없음") + " |")
    L.append(f"| OCR 조각 | {meta['pieces']} |")
    L.append(f"| 검출 영역 | {total:,} (섹션당 {total / meta['sections']:.1f}) |")
    L.append(f"| 실행 오류 | {meta['errors']} |")
    L.append(f"| 소요 | 초기화 {meta['init_sec']}s · 인식 {meta['total_sec']}s (섹션당 {meta['total_sec'] / meta['sections']:.2f}s) |")
    L.append(f"| 실행 시각 | {meta['run_at']} |")
    L.append("")

    # 2. 긴 섹션 분할
    L.append("## 2. 4,000px 초과 섹션 분할 (기계 집계)")
    L.append("")
    L.append("- **이전** = `ocr_split` `section_vlm2`(분할 없이 넣어 축소됨) · **참조** = `ocr_split` `tile_2000_ov300`")
    L.append("- 참조 일치 = 참조 영역을 IoU ≥ 0.5로 찾은 비율")
    L.append("")
    split = [s for s in secs if len(s["chunks"]) > 1]
    if not split:
        L.append("분할된 섹션 없음.")
        L.append("")
    else:
        L.append("| 섹션 | 높이 | 조각 (섹션 로컬) | 영역 이전 → 이번 | 참조 일치 이전 | 참조 일치 이번 | 경계 닿음 | 중복 |")
        L.append("|---|---|---|---|---|---|---|---|")
        seam_rows = []
        for s in split:
            stem = Path(s["image"]).stem
            t, b = s["range"]
            off = s["top_offset"]
            new = [page_bbox(r, off) for r in s["regions"]]
            prev = [r["bbox"] for r in in_range(split_page("section_vlm2", stem)["regions"], t, b)]
            ref = [r["bbox"] for r in in_range(split_page("tile_2000_ov300", stem)["regions"], t, b)]
            hit_prev = sum(1 for rb in ref if any(iou(rb, c) >= 0.5 for c in prev))
            hit_new = sum(1 for rb in ref if any(iou(rb, c) >= 0.5 for c in new))
            edge = sum(1 for r in s["regions"] if r.get("edge_touch"))
            rs = s["regions"]
            dup = sum(1 for i in range(len(rs)) for j in range(i + 1, len(rs))
                      if rs[i]["text"].strip() == rs[j]["text"].strip() and iou(rs[i]["bbox"], rs[j]["bbox"]) > 0.5)
            pieces = " · ".join(f"{c['range'][0]}~{c['range'][1]}" for c in s["chunks"])
            L.append(f"| `{s['section']}` | {s['size'][1]:,}px | {pieces} | {len(prev)} → {len(new)} | "
                     f"{pct(hit_prev, len(ref))} | {pct(hit_new, len(ref))} | {edge} | {dup} |")

            for seam in s["seams"]:
                y = seam["y"] + off
                ref_v, ref_regions = None, []
                for v in SEAM_REFS:
                    d = split_page(v, stem)
                    if any(ct + REF_MARGIN <= y <= cb - REF_MARGIN for ct, cb in d["chunks"]):
                        ref_v, ref_regions = v, d["regions"]
                        break
                crossing = [r for r in ref_regions if r["bbox"][1] < y < r["bbox"][3]]
                ok = cut = miss = 0
                texts = []
                for r in crossing:
                    best = max((iou(r["bbox"], c) for c in new), default=0.0)
                    if best >= 0.5:
                        ok += 1
                    elif best > 0:
                        cut += 1
                        texts.append(f"잘림 `{esc(r['text'])}`")
                    else:
                        miss += 1
                        texts.append(f"누락 `{esc(r['text'])}`")
                seam_rows.append(f"| `{s['section']}` | {seam['y']} | {seam['kind']} | "
                                 f"{('`' + ref_v + '`') if ref_v else '없음'} | {len(crossing)} | {ok} | {cut} | {miss} | "
                                 f"{' · '.join(texts) or '-'} |")
        L.append("")
        L.append("**이음선 대조** — 이음선을 가로지르는 참조 글자를 이번 결과에서 찾음")
        L.append("")
        L.append("| 섹션 | 이음선 y (로컬) | 방식 | 참조 | 가로지르는 글자 | 온전 | 잘림 | 누락 | 사례 |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        L.extend(seam_rows or ["| - | - | - | - | 0 | 0 | 0 | 0 | - |"])
        L.append("")
        L.append("> 방식 `blank` = 여백 절단(겹침 없음) · `band` = 겹침 띠. 여백 절단은 글자를 지나지 않아야 정상.")
        L.append("")

    # 3. 영역 수 변화
    L.append("## 3. 영역 수 변화 — 분할 전(`section_vlm2`) 대비")
    L.append("")
    by_page: dict[str, int] = {}
    for s in secs:
        by_page[s["image"]] = by_page.get(s["image"], 0) + len(s["regions"])
    prev_total, diff_rows = 0, []
    for img in sorted(by_page):
        n_prev = len(split_page("section_vlm2", Path(img).stem)["regions"])
        prev_total += n_prev
        if n_prev != by_page[img]:
            diff_rows.append(f"| {img} | {n_prev} | {by_page[img]} | {by_page[img] - n_prev:+d} |")
    L.append("| 페이지 | 이전 | 이번 | 차이 |")
    L.append("|---|---|---|---|")
    L.extend(diff_rows)
    L.append(f"| **합계 (34장)** | **{prev_total:,}** | **{total:,}** | **{total - prev_total:+d}** |")
    L.append("")
    L.append(f"> 차이 나는 페이지만 표시함. 나머지 {len(by_page) - len(diff_rows)}장은 영역 수 같음.")
    L.append("")

    # 4. 저신뢰 · 빈 텍스트
    items = []
    for s in secs:
        for n, r in enumerate(s["regions"], 1):
            empty = not r["text"].strip()
            if empty or r["score"] < LOW_SCORE:
                items.append({"section": s["section"], "image": s["image"], "n": n, "text": r["text"],
                              "score": r["score"], "empty": empty,
                              "page_bbox": page_bbox(r, s["top_offset"])})
    for k, it in enumerate(items, 1):
        it["lid"] = f"L{k:03d}"
    per = SHEET_COLS * SHEET_ROWS
    make_sheets(items, base / "_lowscore")
    n_empty = sum(1 for it in items if it["empty"])
    L.append("## 4. 저신뢰 · 빈 텍스트 영역 — 무엇을 잡았는지")
    L.append("")
    L.append("결과 문서 8장 ⑫ 확인 항목. 원문 지우기 `erase_s50`이 마스크에서 빼는 영역과 같음.")
    L.append("")
    L.append("| 구분 | 영역 | 비율 |")
    L.append("|---|---|---|")
    L.append(f"| 신뢰도 0.5 미만 (빈 텍스트 포함) | {sum(1 for it in items if it['score'] < LOW_SCORE)} | "
             f"{sum(1 for it in items if it['score'] < LOW_SCORE) / total * 100:.1f}% |")
    L.append(f"| 빈 텍스트 | {n_empty} | {n_empty / total * 100:.1f}% |")
    L.append(f"| **합집합 — 아래 목록** | **{len(items)}** | **{len(items) / total * 100:.1f}%** |")
    L.append("")
    L.append(f"시트 `{rel}/_lowscore/sheet_NN.jpg` — 한 장 {per}칸, 주황 저신뢰 · 보라 빈 텍스트. "
             "**채울 칸은 `잡은 것`** (글자 · 얼굴 · 물방울 · 아이콘 · 제품 · 기타)")
    L.append("")
    L.append("| L | 섹션 | 영역 | 텍스트 | 신뢰도 | 크기 | 시트 | 잡은 것 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for k, it in enumerate(items):
        x0, y0, x1, y1 = it["page_bbox"]
        sheet = f"[{k // per + 1:02d}]({rel}/_lowscore/sheet_{k // per + 1:02d}.jpg)"
        text = esc(it["text"]) if not it["empty"] else "(빈)"
        mark = found.get((it["section"], str(it["n"])), " ")
        L.append(f"| {it['lid']} | {it['section']} | {it['n']} | {text} | {it['score']:.2f} | "
                 f"{x1 - x0}×{y1 - y0} | {sheet} | {mark} |")
    L.append("")

    # 5. 판정표
    L.append("## 5. 판정표 (섹션 × 육안 A/B/C — 빈 칸 채울 것)")
    L.append("")
    L.append("**등급 기준** (원 과업 2.1 [확정])")
    L.append("")
    L.append("| 등급 | 텍스트 열 | bbox 열 |")
    L.append("|---|---|---|")
    L.append("| **A** | 대부분 정확, 오탈자 거의 없음 — 그대로 번역에 넘겨도 됨 | 텍스트 영역을 정확히 감쌈 |")
    L.append("| **B** | 일부 오탈자 있으나 1차 검수로 고칠 수 있는 수준 | 약간 어긋나지만 마스크 확장으로 흡수 가능 |")
    L.append("| **C** | 오탈자 과다하거나 인식 실패 — 사용 불가 | 크게 빗나가거나 영역 누락 |")
    L.append("| **-** | `텍스트`·`bbox`: 글자 없는 섹션(분모 제외) · `사진영역` 두 열: 사진·그라데이션 위 글자 없음 | 〃 |")
    L.append("")
    L.append("- 대지 `vis/{섹션}.jpg` — 왼쪽 bbox · 번호, 오른쪽 번호별 인식 텍스트. 영역 0인 섹션도 글자 누락 여부를 보고 매길 것")
    L.append("- 판정 주체: Claude 1차 판정(비고에 \"Claude 육안 판정\") → 예람님 검토")
    L.append("")
    L.append("| 섹션 | 높이 | 영역 | " + " | ".join(GRADE_COLS) + " | 대지 |")
    L.append("|---|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for s in secs:
        vals = grades.get(s["section"], [" "] * len(GRADE_COLS))
        L.append(f"| {s['section']} | {s['size'][1]:,} | {len(s['regions'])} | " + " | ".join(vals)
                 + f" | [보기]({rel}/vis/{s['section']}.jpg) |")
    L.append("")
    L.append("**집계** — 위 판정표에서 자동 계산됨. 직접 채우지 말 것")
    L.append("")
    cols = [[grades.get(s["section"], [""] * len(GRADE_COLS))[i] for s in secs] for i in range(4)]
    cells = [ratio(c) for c in cols]
    head = cells[:2]
    if any("판정" in c for c in head) or all(c == "-" for c in head):
        gate = "판정 미완"
    else:
        gate = "O" if all(c == "-" or int(c.split("(")[1].rstrip("%)")) >= 70 for c in head) else "X"
    L.append("| 텍스트 | bbox | 사진영역 텍스트 | 사진영역 bbox | 게이트 (텍스트 · bbox 70%) |")
    L.append("|---|---|---|---|---|")
    L.append("| " + " | ".join(cells) + f" | {gate} |")
    L.append("")
    L.append("> 게이트는 계획 7장 기준 — 텍스트 · bbox 두 열. 사진영역 두 열은 원문 지우기 판단 근거로 같이 봄.")
    L.append("")

    # 6. 인식 텍스트
    L.append("## 6. 인식 텍스트")
    L.append("")
    L.append(f"섹션별 전체 목록은 [`{rel}/texts.md`]({rel}/texts.md). 행 번호 = 대지 번호.")
    L.append("")

    T = ["# 골든 샘플 섹션 인식 텍스트", "",
         "> `compare.py --sample golden`이 생성함. 괄호 안은 인식 신뢰도. `경계` = 조각 끝 2px 안에 닿음.", ""]
    for s in secs:
        T.append(f"## {s['section']}")
        T.append("")
        T.append(f"[대지](vis/{s['section']}.jpg) · {s['size'][0]}×{s['size'][1]}px · top_offset {s['top_offset']} · "
                 f"영역 {len(s['regions'])} · 조각 {len(s['chunks'])}")
        T.append("")
        if not s["regions"]:
            T.append("영역 없음.")
            T.append("")
            continue
        T.append("| # | 텍스트 | 신뢰도 | 조각 | 경계 |")
        T.append("|---|---|---|---|---|")
        for n, r in enumerate(s["regions"], 1):
            text = esc(r["text"]) if r["text"].strip() else "(빈)"
            T.append(f"| {n} | {text} | {r['score']:.2f} | {r['chunk']} | {'O' if r.get('edge_touch') else ''} |")
        T.append("")

    GOLDEN_OUT.write_text("\n".join(L), encoding="utf-8")
    (base / "texts.md").write_text("\n".join(T), encoding="utf-8")
    print(f"작성 완료: {GOLDEN_OUT}")
    print(f"  섹션 {len(secs)} · 영역 {total} · 저신뢰·빈 텍스트 {len(items)} (시트 {(len(items) + per - 1) // per}장)")
    print(f"  판정 {len(grades)}/{len(secs)}행" + (" (기존 등급 보존됨)" if grades else ""))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", choices=("default", "golden"), default="default")
    args = ap.parse_args()
    if args.sample == "golden":
        main_golden()
    else:
        main_default()


if __name__ == "__main__":
    main()
