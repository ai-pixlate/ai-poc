"""E1. 원문 지우기 — 마스크를 넓히면 잔존이 줄어드는가 (골든 샘플 · 확정 조건 `erase_s50`).

질문 두 가지
    ① 처음부터 넓게 — 팽창을 글자 높이 15% → 30% · 50%로 키우면 글자가 덜 남는가
    ② 다시 칠하기 루프 — 1차(15%) 결과를 OCR로 다시 읽어 **글자가 남은 영역만** 30%로 넓혀 1차 결과 위에 한 번 더 칠하면 나아지는가

지표 (전부 기계 · 로컬)
    잔존     지운 영역 중 결과 이미지 OCR에서 다시 읽힌 비율 (신뢰도 0.5 이상 · 텍스트 있음 · 중심이 원래 영역 안)
    얼룩     지운 덩어리마다 안쪽 색과 바깥 둘레(6px) 색의 차이(Lab ΔE) 평균 — 넓을수록 커지는지 보려는 것
    마스크   섹션 면적 대비 지운 비율

조건
    d15    확정 조건 그대로 — 단계 5 결과 재사용
    d30    처음부터 30%
    d50    처음부터 50%
    loop30 d15 결과 → 잔존 영역만 30% 마스크 → d15 결과 위에 LaMa 한 번 더

출력 (results/golden/dilate/)
    {조건}/{섹션}.png · masks/{조건}/{섹션}.png · board/{섹션}.jpg(잔상이 적힌 섹션)
    meta.json

사용법 (.venv — LaMa는 .venv-e1의 iopaint를 부름)
    python run_dilate_golden.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import run_golden as E   # 같은 과업 폴더 — 경로·제외 규칙·영역 선택

OUT = E.OUT / "dilate"
D15 = E.OUT / "erase_s50"
SECTIONS = E.OUT / "sections"
SUMMARY = E.HERE / "summary_golden.md"
CFG = E.VARIANTS["erase_s50"]
KEEP = 0.5
RESIDUE_KW = r"잔상|읽힘|판독|조각 잔존|글자 조각|흔적"


def build_mask(shape: tuple, regions: list, ratio: float) -> np.ndarray:
    """run_golden.build_mask와 같고 팽창 비율만 인자로 받음."""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        d = max(E.MIN_PX, int(round((y2 - y1) * ratio)))
        pad = d + 2
        sx1, sy1 = max(0, x1 - pad), max(0, y1 - pad)
        sx2, sy2 = min(w, x2 + pad), min(h, y2 + pad)
        if sx2 <= sx1 or sy2 <= sy1:
            continue
        sub = np.zeros((sy2 - sy1, sx2 - sx1), np.uint8)
        cv2.fillPoly(sub, [np.array(r["poly"], np.int32) - [sx1, sy1]], 255)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
        np.maximum(mask[sy1:sy2, sx1:sx2], cv2.dilate(sub, k), out=mask[sy1:sy2, sx1:sx2])
    return mask


def lama(pairs: dict, out_dir: Path) -> float:
    """pairs = {섹션: (입력 이미지 경로, 마스크 배열)}"""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pairs:
        return 0.0
    tmp = Path(tempfile.mkdtemp(prefix="e1_dilate_"))
    try:
        img_dir, msk_dir, res_dir = tmp / "img", tmp / "msk", tmp / "out"
        for d in (img_dir, msk_dir, res_dir):
            d.mkdir()
        for sid, (src, mask) in pairs.items():
            shutil.copy2(src, img_dir / f"{sid}.png")
            cv2.imwrite(str(msk_dir / f"{sid}.png"), mask)
        cmd = [str(E.IOPAINT), "run", "--model=lama", "--device=cuda",
               f"--image={img_dir}", f"--mask={msk_dir}", f"--output={res_dir}"]
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise SystemExit(f"iopaint 실패 {proc.stderr[-1500:]}")
        for p in res_dir.glob("*.*"):
            im = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out_dir / f"{p.stem}.png"), im)
        return round(time.perf_counter() - t0, 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ocr(model, path: Path) -> list:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    h = img.shape[0]
    tops = [0] if h <= 4000 else list(range(0, h - 300, 1700))
    out = []
    for i, top in enumerate(tops):
        strip = img[top:top + (h if len(tops) == 1 else 2000)]
        res = list(model.predict(strip))[0]
        lo = top + (150 if i else 0)
        hi = top + strip.shape[0] - (150 if i < len(tops) - 1 else 0)
        for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) + top for p in poly]
            if lo <= (min(ys) + max(ys)) / 2 < hi and score >= KEEP and text.strip():
                out.append({"bbox": [min(xs), min(ys), max(xs), max(ys)], "text": text, "score": float(score)})
    return out


def residue(regions: list, after: list) -> list:
    """지운 영역 중 결과에서 다시 읽힌 것의 인덱스."""
    left = []
    for i, r in enumerate(regions):
        x1, y1, x2, y2 = r["bbox"]
        for a in after:
            cx, cy = (a["bbox"][0] + a["bbox"][2]) / 2, (a["bbox"][1] + a["bbox"][3]) / 2
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                left.append(i)
                break
    return left


def blotch(img: np.ndarray, mask: np.ndarray) -> float:
    """지운 덩어리 안쪽 평균색과 바깥 둘레 6px 중앙값 색의 Lab 거리 — 면적 가중 평균."""
    if not mask.any():
        return 0.0
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    n, lbl = cv2.connectedComponents((mask > 0).astype(np.uint8))
    ring_k = np.ones((13, 13), np.uint8)
    tot, wsum = 0.0, 0
    for k in range(1, n):
        comp = (lbl == k).astype(np.uint8)
        area = int(comp.sum())
        if area < 30:
            continue
        ring = (cv2.dilate(comp, ring_k) > 0) & (mask == 0)
        if not ring.any():
            continue
        inside = lab[comp > 0].mean(axis=0)
        outside = np.median(lab[ring], axis=0)
        tot += float(np.linalg.norm(inside - outside)) * area
        wsum += area
    return round(tot / wsum, 2) if wsum else 0.0


def residue_sections() -> set:
    """단계 5 판정 비고에 잔상이 적힌 섹션 (erase_s50 B·C)."""
    if not SUMMARY.exists():
        return set()
    out = set()
    tab = SUMMARY.read_text(encoding="utf-8").split("## 3.")[1].split("## 4.")[0]
    for line in tab.splitlines():
        if line.startswith("| A0"):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if c[7] in ("B", "C") and re.search(RESIDUE_KW, c[9]):
                out.add(c[0])
    return out


def _font(size):
    for n in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def board(sid: str, cols: list, path: Path, notes: dict) -> None:
    ims = [Image.open(p).convert("RGB") for _, p in cols]
    w = 420
    ims = [im.resize((w, max(1, int(im.height * w / im.width)))) for im in ims]
    h = max(im.height for im in ims)
    canvas = Image.new("RGB", (w * len(ims), h + 44), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    f = _font(15)
    for i, ((name, _), im) in enumerate(zip(cols, ims)):
        canvas.paste(im, (i * w, 44))
        d.text((i * w + 4, 2), name, fill=(0, 0, 0), font=f)
        d.text((i * w + 4, 22), notes.get(name, ""), fill=(200, 30, 30), font=f)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=88)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from paddleocr import PaddleOCR
    model = PaddleOCR(lang="korean", use_doc_orientation_classify=False,
                      use_doc_unwarping=False, use_textline_orientation=False)

    labels_all = json.loads(E.TRUTH.read_text(encoding="utf-8"))["labels"]
    logos = E.logo_blocks()
    secs = {}
    for f in sorted(E.REGIONS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = d["section"]
        blocks = json.loads((E.BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))["blocks"]
        skip, _, _ = E.excluded(sid, blocks, set(labels_all.get(sid, [])), logos)
        regs = E.pick(d["regions"], CFG, skip)
        if regs:
            img = cv2.imdecode(np.fromfile(str(SECTIONS / f"{sid}.png"), np.uint8), cv2.IMREAD_COLOR)
            secs[sid] = {"regions": regs, "shape": img.shape[:2]}
    print(f"대상 섹션 {len(secs)} · 지운 영역 {sum(len(s['regions']) for s in secs.values())}", flush=True)

    masks = {"d15": {}, "d30": {}, "d50": {}, "loop30": {}}
    for sid, s in secs.items():
        for name, ratio in (("d15", 0.15), ("d30", 0.30), ("d50", 0.50)):
            masks[name][sid] = build_mask(s["shape"], s["regions"], ratio)
        (OUT / "masks").mkdir(parents=True, exist_ok=True)

    sec_time = {}
    for name in ("d30", "d50"):
        sec_time[name] = lama({sid: (SECTIONS / f"{sid}.png", masks[name][sid]) for sid in secs}, OUT / name)
        print(f"  LaMa {name} {sec_time[name]}s", flush=True)

    # d15 = 단계 5 결과 그대로. 잔존 영역을 찾아 루프 입력으로
    results = {"d15": {}, "d30": {}, "d50": {}, "loop30": {}}
    loop_pairs = {}
    for sid, s in secs.items():
        after = ocr(model, D15 / f"{sid}.png")
        left = residue(s["regions"], after)
        results["d15"][sid] = left
        if left:
            m = build_mask(s["shape"], [s["regions"][i] for i in left], 0.30)
            masks["loop30"][sid] = m
            loop_pairs[sid] = (D15 / f"{sid}.png", m)
    sec_time["loop30"] = lama(loop_pairs, OUT / "loop30")
    print(f"  루프 대상 섹션 {len(loop_pairs)} · LaMa {sec_time['loop30']}s", flush=True)
    for sid in secs:   # 루프 대상이 아닌 섹션은 1차 결과 그대로
        if sid not in loop_pairs:
            (OUT / "loop30").mkdir(parents=True, exist_ok=True)
            shutil.copy2(D15 / f"{sid}.png", OUT / "loop30" / f"{sid}.png")

    src = {"d15": D15, "d30": OUT / "d30", "d50": OUT / "d50", "loop30": OUT / "loop30"}
    rows = []
    for sid, s in secs.items():
        row = {"section": sid, "regions": len(s["regions"])}
        for name in ("d15", "d30", "d50", "loop30"):
            if name != "d15":
                results[name][sid] = residue(s["regions"], ocr(model, src[name] / f"{sid}.png"))
            img = cv2.imdecode(np.fromfile(str(src[name] / f"{sid}.png"), np.uint8), cv2.IMREAD_COLOR)
            m = masks["d15"][sid] if name == "loop30" else masks[name][sid]
            if name == "loop30" and sid in masks["loop30"]:
                m = np.maximum(m, masks["loop30"][sid])
            row[name] = {"left": len(results[name][sid]),
                         "left_text": [s["regions"][i]["text"] for i in results[name][sid]][:6],
                         "mask_pct": round(float((m > 0).mean() * 100), 1), "blotch": blotch(img, m)}
        rows.append(row)
    print("OCR 대조 완료", flush=True)

    tagged = residue_sections()
    for r in rows:
        if r["section"] in tagged or r["d15"]["left"]:
            sid = r["section"]
            notes = {n: f"남음 {r[n]['left']} · 얼룩 {r[n]['blotch']}" for n in ("d15", "d30", "d50", "loop30")}
            board(sid, [("원본", SECTIONS / f"{sid}.png"), ("d15", src["d15"] / f"{sid}.png"),
                        ("d30", src["d30"] / f"{sid}.png"), ("d50", src["d50"] / f"{sid}.png"),
                        ("loop30", src["loop30"] / f"{sid}.png")], OUT / "board" / f"{sid}.jpg", notes)

    total = sum(r["regions"] for r in rows)
    summ = {}
    for n in ("d15", "d30", "d50", "loop30"):
        left = sum(r[n]["left"] for r in rows)
        summ[n] = {"left": left, "left_rate": round(left / total * 100, 1),
                   "sections_with_left": sum(1 for r in rows if r[n]["left"]),
                   "blotch_mean": round(sum(r[n]["blotch"] for r in rows) / len(rows), 2),
                   "mask_pct_mean": round(sum(r[n]["mask_pct"] for r in rows) / len(rows), 1),
                   "lama_sec": sec_time.get(n, 280.32)}
    meta = {"sections": len(rows), "regions": total, "loop_sections": len(loop_pairs),
            "residue_tagged_sections": sorted(tagged), "summary": summ, "per_section": rows,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    for n, v in summ.items():
        print(f"  {n:<7} 남은 영역 {v['left']:>3} ({v['left_rate']}%) · 남은 섹션 {v['sections_with_left']:>2}"
              f" · 얼룩 {v['blotch_mean']} · 마스크 {v['mask_pct_mean']}% · LaMa {v['lama_sec']}s")


if __name__ == "__main__":
    main()
