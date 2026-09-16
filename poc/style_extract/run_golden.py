"""스타일 추출 — 골든 샘플 섹션 실행기 (계획 단계 6).

확정 조건(`otsu_border`) 그대로 돌리되 입력만 섹션으로 바꾼다.
색·정렬 계산은 run.py 함수를 그대로 불러 쓴다(같은 과업 폴더).

입력
    poc/golden/1_B_ocr/results/baseline/regions/{섹션}.json        영역 bbox·텍스트
    poc/golden/2_block_role/results/llm_assist/blocks/{섹션}.json  블록·역할·소속 region
    poc/golden/3_product_label/results/vlm_relation/truth.json     라벨 정답(판정 제외용)
    poc/golden/4_logo_match/results/block_exact/meta.json          로고 블록(판정 제외용)
    data/golden_sample/... 원본 페이지 (섹션 range로 크롭)

실행 범위 — **전 블록에 돌린다.** 라벨·로고는 표시만 하고 판정에서 뺀다.

출력
    results/golden/otsu_border/sections/{섹션}.png    섹션 원본 (시각화 입력)
    results/golden/otsu_border/styles/{섹션}.json     영역별 색·크기 + 블록 정렬·역할·라벨·로고
    results/golden/otsu_border/vis/{섹션}.jpg         전체 영역 + 색 스와치 띠
    results/golden/otsu_border/vis_target/{섹션}.jpg  조판 대상만(라벨·로고 제외), 번호는 전체 뷰와 같음
    results/golden/otsu_border/meta.json

사용법
    python run_golden.py
    python run_golden.py --sections A000000250199_014_003
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

import run as R  # 같은 과업 폴더 — 색·정렬 계산과 시각화를 그대로 쓴다

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLDEN = ROOT / "poc" / "golden"
REGIONS = GOLDEN / "1_B_ocr" / "results" / "baseline" / "regions"
BLOCKS = GOLDEN / "2_block_role" / "results" / "llm_assist" / "blocks"
TRUTH = GOLDEN / "3_product_label" / "results" / "vlm_relation" / "truth.json"
LOGO_META = GOLDEN / "4_logo_match" / "results" / "block_exact" / "meta.json"
PAGES = ROOT / "data" / "golden_sample"
OUT = HERE / "results" / "golden" / "otsu_border"
VARIANT = "otsu_border"  # 확정 조건


def logo_blocks() -> set:
    m = json.loads(LOGO_META.read_text(encoding="utf-8"))
    out = {(r["host_section"], r["host_block"]) for r in m["page_logos"]
           if r["status"] == "찾음" and r["host_section"]}
    out |= {(r["section"], r["block"]) for r in m.get("false_hits", [])}
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", nargs="*", default=None)
    args = ap.parse_args()

    for p in (REGIONS, BLOCKS, TRUTH, LOGO_META):
        if not p.exists():
            raise SystemExit(f"상류 결과 없음: {p}")
    labels_all = json.loads(TRUTH.read_text(encoding="utf-8"))["labels"]
    logos = logo_blocks()
    pages = {p.name: p for p in PAGES.rglob("*.jpg")}

    files = sorted(REGIONS.glob("*.json"))
    if args.sections:
        files = [f for f in files if f.stem in args.sections]
    if not files:
        raise SystemExit("대상 섹션 없음")

    for sub in ("sections", "styles", "vis", "vis_target"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    split = R.SPLIT[VARIANT]
    per, aligns = [], {}
    page_name, page_img = None, None
    t_all = time.perf_counter()

    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        sid, regions = d["section"], d["regions"]
        top, bottom = d["range"]
        if d["image"] != page_name:
            page_name = d["image"]
            page_img = cv2.imdecode(np.fromfile(str(pages[page_name]), np.uint8), cv2.IMREAD_COLOR)
        bgr = page_img[top:bottom]
        sec_path = OUT / "sections" / f"{sid}.png"
        cv2.imwrite(str(sec_path), bgr)

        blocks = json.loads((BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))["blocks"]
        labels = set(labels_all.get(sid, []))
        owner = {}
        for bi, b in enumerate(blocks):
            for ri in b["regions"]:
                owner[ri] = bi
        align_of = {bi: R.block_align([regions[ri]["bbox"] for ri in b["regions"] if ri < len(regions)])
                    for bi, b in enumerate(blocks)}

        rows = []
        for ri, reg in enumerate(regions):
            x1, y1, x2, y2 = reg["bbox"]
            crop = bgr[max(0, y1):max(y1 + 1, y2), max(0, x1):max(x1 + 1, x2)]
            if crop.size == 0:
                continue
            fg, bg = split(crop)
            bi = owner.get(ri)
            h = y2 - y1
            is_label = bi is not None and (bi + 1) in labels
            is_logo = bi is not None and (sid, bi + 1) in logos
            rows.append({
                "region": ri, "bbox": reg["bbox"], "text": reg["text"],
                "font_color": R._hex(fg), "bg_color": R._hex(bg),
                "contrast": R.contrast_ratio(fg, bg),
                "est_font_px": h, "est_em_px": round(h * R.EM_RATIO),
                "align": align_of.get(bi, "단일행"), "block": None if bi is None else bi + 1,
                "role": blocks[bi]["role"] if bi is not None else None,
                "is_product_label": is_label, "is_logo": is_logo,
            })
            aligns[rows[-1]["align"]] = aligns.get(rows[-1]["align"], 0) + 1

        (OUT / "styles" / f"{sid}.json").write_text(json.dumps(
            {"section": sid, "image": d["image"], "variant": VARIANT, "top_offset": d["top_offset"],
             "range": d["range"], "size": d["size"], "styles": rows}, ensure_ascii=False, indent=1),
            encoding="utf-8")

        for i, r in enumerate(rows, 1):
            r["no"] = i
        R.visualize(sec_path, rows, OUT / "vis" / f"{sid}.jpg")
        target = [r for r in rows if not r["is_product_label"] and not r["is_logo"]]
        R.visualize(sec_path, target, OUT / "vis_target" / f"{sid}.jpg")

        med = sorted(r["contrast"] for r in rows)[len(rows) // 2] if rows else 0
        low = sum(1 for r in target if r["contrast"] < 1.5)
        per.append({"section": sid, "size": d["size"], "regions": len(rows),
                    "target_regions": len(target), "label_regions": sum(1 for r in rows if r["is_product_label"]),
                    "logo_regions": sum(1 for r in rows if r["is_logo"]),
                    "target_low_contrast": low, "contrast_median": med})
        print(f"  {sid:<24} 영역 {len(rows):>3}  조판 대상 {len(target):>3}  대비 중앙 {med}", flush=True)

    meta = {"variant": VARIANT, "sample": "golden",
            "cfg": {"em_ratio": R.EM_RATIO, "align_tol": R.ALIGN_TOL, "align_margin": R.ALIGN_MARGIN},
            "source": {"regions": str(REGIONS.relative_to(ROOT)), "blocks": str(BLOCKS.relative_to(ROOT)),
                       "labels": str(TRUTH.relative_to(ROOT)), "logos": str(LOGO_META.relative_to(ROOT))},
            "sections": len(per),
            "total_regions": sum(p["regions"] for p in per),
            "target_regions": sum(p["target_regions"] for p in per),
            "label_regions": sum(p["label_regions"] for p in per),
            "logo_regions": sum(p["logo_regions"] for p in per),
            "target_low_contrast": sum(p["target_low_contrast"] for p in per),
            "align_dist": aligns, "total_sec": round(time.perf_counter() - t_all, 2),
            "per_section": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[golden/{VARIANT}] 완료 — 섹션 {meta['sections']} · 영역 {meta['total_regions']} "
          f"(조판 대상 {meta['target_regions']} · 라벨 {meta['label_regions']} · 로고 {meta['logo_regions']}) "
          f"· 대비 1.5 미만 {meta['target_low_contrast']} · {meta['total_sec']}s")


if __name__ == "__main__":
    main()
