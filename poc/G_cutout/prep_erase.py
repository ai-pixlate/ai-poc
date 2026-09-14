"""누끼 입력 준비 — 섹션 크롭에서 글자를 지운다 (`.venv`에서 실행).

재배치용 누끼에서 페이지 글자는 요소에 섞이면 안 된다(번역 후 조판으로 다시 그림).
파이프라인상 누끼 전에 원문 지우기가 이미 돌므로, **글자 지운 섹션을 누끼 입력으로
쓰면 글자 파편 문제가 사라지는지** 비교하려고 지운 입력을 만든다.

입력
    섹션      poc/section_split/results/color_snap_vlm2/crops/{stem}/{i}.jpg   (섹션 분해 채택안)
    글자 영역 poc/ocr_split/results/section_vlm2/regions/{stem}.json          (섹션 단위 OCR)

지우기 — 원문 지우기 확정 조건: LaMa · 글자 높이 15% 팽창(최소 3px).
    ⚠️ 차이 1 — 확정 조건은 OCR poly를 채우지만 섹션 OCR 캐시에는 bbox만 있어 **bbox 사각형**을 씀.
       기울어진 글자에서 마스크가 조금 커짐
    ⚠️ 차이 2 — 골든 샘플은 제품 라벨 판정을 안 돌려 **제품 인쇄 글자도 함께 지움**.
       실서비스에서는 라벨 글자는 남음

출력
    results/_erase/masks/{stem}_{i}.png    흰색 = 지울 곳
    results/_erase/erased/{stem}_{i}.png   글자 지운 섹션 (글자 없는 섹션은 원본 복사)
    results/_erase/meta.json

사용법
    python prep_erase.py
    python prep_erase.py --images A000000250199_008.jpg
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
SRC = ROOT / "data" / "golden_sample"
SECTIONS = ROOT / "poc" / "section_split" / "results" / "color_snap_vlm2"
OCR = ROOT / "poc" / "ocr_split" / "results" / "section_vlm2" / "regions"
IOPAINT = ROOT / ".venv-e1" / "Scripts" / "iopaint.exe"
OUT = HERE / "results" / "_erase"

RATIO, MIN_PX = 0.15, 3   # 원문 지우기 확정 조건
DEVICE = "cuda"


def section_mask(h: int, w: int, regions: list[dict], top: int) -> np.ndarray:
    mask = np.zeros((h, w), np.uint8)
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        y1, y2 = y1 - top, y2 - top
        d = max(MIN_PX, int(round((y2 - y1) * RATIO)))
        cv2.rectangle(mask, (max(0, x1 - d), max(0, y1 - d)), (min(w - 1, x2 + d), min(h - 1, y2 + d)), 255, -1)
    return mask


def main() -> None:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=None)
    # 1차 실행에서 **인식 신뢰도 0.0 · 빈 텍스트 박스가 얼굴·물방울 위에 잡혀** LaMa가 지워버렸다.
    # 신뢰도 하한을 두어 오검출을 지우기 대상에서 뺀다.
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--tag", default="", help="출력 폴더 접미사 — results/_erase_{tag}/")
    args = ap.parse_args()
    if args.tag:
        OUT = HERE / "results" / f"_erase_{args.tag}"

    for sub in ("masks", "erased"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    stems = sorted(p.stem for p in (SECTIONS / "sections").glob("*.json"))
    if args.images:
        stems = [s for s in stems if f"{s}.jpg" in args.images]

    tmp = Path(tempfile.mkdtemp(prefix="g_erase_"))
    img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
    for d in (img_dir, msk_dir, res_dir):
        d.mkdir()
    rows = []
    try:
        for stem in stems:
            sec = json.loads((SECTIONS / "sections" / f"{stem}.json").read_text(encoding="utf-8"))
            ocr = json.loads((OCR / f"{stem}.json").read_text(encoding="utf-8"))
            for ci, s in enumerate(sec["sections"]):
                name = f"{stem}_{s['index']:03d}"
                crop = SECTIONS / s["crop"]
                img = cv2.imdecode(np.fromfile(str(crop), np.uint8), cv2.IMREAD_COLOR)
                h, w = img.shape[:2]
                regs = [r for r in ocr["regions"] if r["chunk"] == ci
                        and (args.min_score <= 0 or (r["score"] >= args.min_score and r["text"].strip()))]
                mask = section_mask(h, w, regs, s["top_offset"])
                cv2.imwrite(str(OUT / "masks" / f"{name}.png"), mask)
                pct = float((mask > 0).mean() * 100)
                rows.append({"section": name, "size": [w, h], "regions": len(regs), "mask_pct": round(pct, 1)})
                if regs:
                    cv2.imwrite(str(img_dir / f"{name}.png"), img)
                    shutil.copy2(OUT / "masks" / f"{name}.png", msk_dir / f"{name}.png")
                else:
                    cv2.imwrite(str(OUT / "erased" / f"{name}.png"), img)

        todo = len(list(img_dir.glob("*.png")))
        print(f"섹션 {len(rows)}개 · 지울 섹션 {todo}개 → LaMa ({DEVICE})")
        t0 = time.perf_counter()
        if todo:
            cmd = [str(IOPAINT), "run", "--model=lama", f"--device={DEVICE}",
                   f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise SystemExit(f"iopaint 실패 (exit {proc.returncode})\n{proc.stderr[-2000:]}")
            for p in res_dir.glob("*.*"):
                im = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
                cv2.imwrite(str(OUT / "erased" / f"{p.stem}.png"), im)
        sec_total = round(time.perf_counter() - t0, 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    missing = [r["section"] for r in rows if not (OUT / "erased" / f"{r['section']}.png").exists()]
    meta = {"sections": len(rows), "erased": todo, "ratio": RATIO, "min_px": MIN_PX, "device": DEVICE,
            "min_score": args.min_score,
            "lama_sec": sec_total, "missing": missing, "per_section": rows,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 — LaMa {sec_total}s · 누락 {len(missing)}")


if __name__ == "__main__":
    main()
