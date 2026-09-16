"""E1. 원문 지우기 — 골든 샘플 섹션 실행기 (계획 단계 5).

확정 조건 그대로 돌리되 입력만 섹션으로 바꾼다.
    마스크  OCR poly 채움 + 글자 높이 15% 팽창(최소 3px)
    모델    LaMa (iopaint, .venv-e1)
    제외    단계 3 라벨 블록 · 단계 4 로고 블록의 영역은 마스크에서 뺌

variant (계획 단계 5 — 결정 사항 4)
    erase_all  확정 조건 — 모든 OCR 영역
    erase_s50  인식 신뢰도 0.5 이상 · 텍스트 있는 영역만

입력
    poc/golden/1_B_ocr/results/baseline/regions/{섹션}.json        poly·score (섹션 로컬)
    poc/golden/2_block_role/results/llm_assist/blocks/{섹션}.json  블록 → 소속 region
    poc/golden/3_product_label/results/vlm_relation/truth.json     라벨 블록 정답
    poc/golden/4_logo_match/results/block_exact/meta.json          로고 블록
    data/golden_sample/... 원본 페이지 (섹션 range로 크롭)

출력
    results/golden/sections/{섹션}.png             섹션 원본 (LaMa 입력)
    results/golden/masks/{variant}/{섹션}.png      흰색 = 지울 곳
    results/golden/masks/{variant}/vis/{섹션}.jpg  마스크 겹친 확인용
    results/golden/{variant}/{섹션}.png            지운 결과
    results/golden/meta.json

사용법
    python run_golden.py
    python run_golden.py --sections A000000250199_014_003
    python run_golden.py --device cpu
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GOLDEN = ROOT / "poc" / "golden"
REGIONS = GOLDEN / "1_B_ocr" / "results" / "baseline" / "regions"
BLOCKS = GOLDEN / "2_block_role" / "results" / "llm_assist" / "blocks"
TRUTH = GOLDEN / "3_product_label" / "results" / "vlm_relation" / "truth.json"
LOGO_META = GOLDEN / "4_logo_match" / "results" / "block_exact" / "meta.json"
PAGES = ROOT / "data" / "golden_sample"
IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"
OUT = HERE / "results" / "golden"

RATIO, MIN_PX = 0.15, 3  # 확정 조건 — 글자 높이 15% 팽창, 최소 3px
LOW_SCORE = 0.5
VARIANTS = {
    "erase_all": {"min_score": 0.0, "require_text": False},
    "erase_s50": {"min_score": LOW_SCORE, "require_text": True},
}


def logo_blocks() -> set:
    """단계 4에서 로고로 걸러진 블록 (섹션, 블록번호). 라벨 블록 위 통과는 라벨 소관이라 뺀다."""
    if not LOGO_META.exists():
        return set()
    m = json.loads(LOGO_META.read_text(encoding="utf-8"))
    out = set()
    for r in m["page_logos"]:
        if r["status"] == "찾음" and r["host_section"]:
            out.add((r["host_section"], r["host_block"]))
    for r in m.get("false_hits", []):
        out.add((r["section"], r["block"]))
    return out


def excluded(sid: str, blocks: list, labels: set, logos: set) -> tuple:
    """마스크에서 뺄 region 인덱스(0부터) · 라벨 블록 수 · 로고 블록 수."""
    out, n_lab, n_logo = set(), 0, 0
    for i, b in enumerate(blocks, 1):
        is_lab, is_logo = i in labels, (sid, i) in logos
        if is_lab:
            n_lab += 1
        if is_logo:
            n_logo += 1
        if is_lab or is_logo:
            out.update(b["regions"])
    return out, n_lab, n_logo


def build_mask(shape: tuple, regions: list) -> np.ndarray:
    """poly 채움 + 글자 높이 비례 팽창. make_mask.py build_mask 복사 (섹션 로컬 좌표)."""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        d = max(MIN_PX, int(round((y2 - y1) * RATIO)))
        pad = d + 2
        sx1, sy1 = max(0, x1 - pad), max(0, y1 - pad)
        sx2, sy2 = min(w, x2 + pad), min(h, y2 + pad)
        if sx2 <= sx1 or sy2 <= sy1:
            continue
        sub = np.zeros((sy2 - sy1, sx2 - sx1), np.uint8)
        poly = np.array(r["poly"], np.int32) - [sx1, sy1]
        cv2.fillPoly(sub, [poly], 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
        sub = cv2.dilate(sub, kernel)
        np.maximum(mask[sy1:sy2, sx1:sx2], sub, out=mask[sy1:sy2, sx1:sx2])
    return mask


def overlay(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    tint = img.copy()
    tint[mask > 0] = (0, 0, 255)
    return cv2.addWeighted(img, 0.55, tint, 0.45, 0)


def pick(regions: list, cfg: dict, skip: set) -> list:
    out = []
    for i, r in enumerate(regions):
        if i in skip:
            continue
        if cfg["require_text"] and not r["text"].strip():
            continue
        if r["score"] < cfg["min_score"]:
            continue
        out.append(r)
    return out


def run_lama(variant: str, names: list, device: str) -> float:
    """마스크가 있는 섹션만 LaMa 배치 실행."""
    if not names:
        return 0.0
    if not IOPAINT.exists():
        raise SystemExit(f"iopaint 없음: {IOPAINT}")
    out_dir = OUT / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="e1_golden_"))
    try:
        img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
        for d in (img_dir, msk_dir, res_dir):
            d.mkdir()
        for n in names:
            shutil.copy2(OUT / "sections" / f"{n}.png", img_dir / f"{n}.png")
            shutil.copy2(OUT / "masks" / variant / f"{n}.png", msk_dir / f"{n}.png")
        cmd = [str(IOPAINT), "run", "--model=lama", f"--device={device}",
               f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}"]
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        sec = time.perf_counter() - t0
        if proc.returncode != 0:
            raise SystemExit(f"iopaint 실패 (exit {proc.returncode}) {proc.stderr[-2000:]}")
        got = sorted(res_dir.glob("*.*"))
        for p in got:
            im = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out_dir / f"{p.stem}.png"), im)
        print(f"[{variant}] LaMa {len(got)}개 · {sec:.1f}s ({device})", flush=True)
        return round(sec, 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", nargs="*", default=None)
    ap.add_argument("--device", default="cuda")
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

    (OUT / "sections").mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        (OUT / "masks" / v / "vis").mkdir(parents=True, exist_ok=True)
        (OUT / v).mkdir(parents=True, exist_ok=True)

    rows, todo = [], {v: [] for v in VARIANTS}
    page_name, page_img = None, None
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        sid, regions = d["section"], d["regions"]
        top, bottom = d["range"]
        if d["image"] != page_name:
            page_name = d["image"]
            page_img = cv2.imdecode(np.fromfile(str(pages[page_name]), np.uint8), cv2.IMREAD_COLOR)
        img = page_img[top:bottom]
        h, w = img.shape[:2]
        cv2.imwrite(str(OUT / "sections" / f"{sid}.png"), img)

        blocks = json.loads((BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))["blocks"]
        skip, n_lab, n_logo = excluded(sid, blocks, set(labels_all.get(sid, [])), logos)
        row = {"section": sid, "size": [w, h], "regions": len(regions),
               "label_blocks": n_lab, "logo_blocks": n_logo, "skipped_regions": len(skip)}
        for v, cfg in VARIANTS.items():
            regs = pick(regions, cfg, skip)
            mask = build_mask((h, w), regs)
            cv2.imwrite(str(OUT / "masks" / v / f"{sid}.png"), mask)
            cv2.imwrite(str(OUT / "masks" / v / "vis" / f"{sid}.jpg"), overlay(img, mask),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
            row[v] = {"regions": len(regs), "mask_pct": round(float((mask > 0).mean() * 100), 1)}
            if mask.any():
                todo[v].append(sid)
        rows.append(row)
        print(f"  {sid:<24} {w}x{h}  영역 {len(regions):>3} → all {row['erase_all']['regions']:>3}"
              f" / s50 {row['erase_s50']['regions']:>3}  제외 {len(skip)}"
              f"  마스크 {row['erase_all']['mask_pct']:>5.1f}% / {row['erase_s50']['mask_pct']:>5.1f}%", flush=True)

    lama_sec = {}
    for v in VARIANTS:
        lama_sec[v] = run_lama(v, todo[v], args.device)
        for r in rows:  # 마스크가 빈 섹션은 원본 그대로
            if r["section"] not in todo[v]:
                shutil.copy2(OUT / "sections" / f"{r['section']}.png", OUT / v / f"{r['section']}.png")

    missing = {v: [r["section"] for r in rows if not (OUT / v / f"{r['section']}.png").exists()] for v in VARIANTS}
    meta = {"sample": "golden", "model": "lama", "device": args.device,
            "cfg": {"dilate_ratio": RATIO, "dilate_min_px": MIN_PX, "mask": "poly 채움 + 팽창",
                    "exclude": "단계 3 라벨 블록 · 단계 4 로고 블록"},
            "source": {"regions": str(REGIONS.relative_to(ROOT)), "blocks": str(BLOCKS.relative_to(ROOT)),
                       "labels": str(TRUTH.relative_to(ROOT)), "logos": str(LOGO_META.relative_to(ROOT))},
            "variants": {v: {"min_score": c["min_score"], "require_text": c["require_text"],
                             "sections_erased": len(todo[v]), "lama_sec": lama_sec[v],
                             "total_regions": sum(r[v]["regions"] for r in rows)} for v, c in VARIANTS.items()},
            "sections": len(rows),
            "total_regions": sum(r["regions"] for r in rows),
            "skipped_regions": sum(r["skipped_regions"] for r in rows),
            "label_blocks": sum(r["label_blocks"] for r in rows),
            "logo_blocks": sum(r["logo_blocks"] for r in rows),
            "missing": missing, "per_section": rows, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 — 섹션 {len(rows)} · 제외 영역 {meta['skipped_regions']}"
          f" (라벨 블록 {meta['label_blocks']} · 로고 블록 {meta['logo_blocks']})")
    for v in VARIANTS:
        m = meta["variants"][v]
        print(f"  {v}: 영역 {m['total_regions']} · 지운 섹션 {m['sections_erased']}"
              f" · LaMa {m['lama_sec']}s · 누락 {len(missing[v])}")


if __name__ == "__main__":
    main()
