"""브랜드 로고 제외 — 골든 샘플 **OCR 전 제외** 검증 (후보 B: 템플릿 매칭 개선).

기능 전제는 **사용자가 올린 로고 파일**로 상세페이지에서 로고를 찾아 빼는 것이다.
확정 방식(`block_exact`)은 병합 뒤 브랜드명 문자열 대조라 병합 결과에 종속된다.
여기서는 로고 파일(템플릿)로 **섹션 이미지에서 먼저 찾고, 그 자리를 가린 뒤 OCR**을
돌려 로고가 하류에 아예 안 들어가는지 본다. 전부 로컬, 비용 0.

기존 템플릿 실행(run.py) 대비 바꾼 것
    · 페이지 → **섹션 단위**(단계 1 섹션 102개)
    · 배율 0.4~2.0(10%p 간격) → **0.25~6.0 · 2% 등비 162단계**(대형 로고 놓침이 배율 상한 탓이었음)
    · 템플릿은 **자기 브랜드 섹션에만** 적용 — 사용자가 그 상품의 로고를 올린다는 전제
    · **배경 제거 템플릿**(`gray_mask`) 추가 — 실제 로고 파일은 투명 배경이라 크롭과 조건이 다름

⚠️ 로고 파일이 없어 **페이지에서 크롭한 템플릿**을 쓴다(run.py `LOGOS` + celimax).
   떼어낸 자리는 무조건 맞으므로 찾음/놓침·오탐 어디에도 세지 않는다.

평가
    찾음/놓침 — 페이지 로고 7개 중 **템플릿을 떼지 않은 4개**(b.clinicx 2 · goodal 2).
               celimax는 페이지에 한 번뿐이라 떼어낸 자리밖에 없음 → 평가 제외
    오탐     — 통과 후보 중 페이지 로고 7개·떼어낸 자리·단계 3 라벨 블록 어디에도 안 걸린 것
    맞춤     — 정답 로고 중심이 후보 상자 안 · IoU ≥ 0.2 (템플릿 상자에 여백이 있어 느슨하게)
    하류     — 통과 후보를 가린 섹션으로 OCR → 휴리스틱 병합을 다시 돌려
               ① 가린 자리에서 브랜드명이 다시 읽히는지 ② 가린 자리 밖 글자가 사라지는지
               ③ 로고와 한 영역이던 글자(`Good all goodal`)가 갈리는지

출력
    results/golden/tmpl_{variant}/meta.json         후보·평가·하류
    results/golden/tmpl_{variant}/sheet.jpg         정답 4개 + 오탐 대지
    results/golden/_masked/{variant}/{섹션}.png      가린 섹션(하류 입력)
    results/golden/_templates/{로고}.png · {로고}_mask.png

사용법
    python run_tmpl_golden.py                  # 3 variant + 하류
    python run_tmpl_golden.py --variant gray_bg --no-ocr
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

import run as R          # 같은 과업 폴더 — 템플릿 목록·매칭 도구
import run_text as T     # 같은 과업 폴더 — 정답 로고·정규화·휴리스틱 병합·경로

Image.MAX_IMAGE_PIXELS = None

OUT = R.RESULTS / "golden"
REGIONS = T.GOLDEN_REGIONS
BLOCKS = T.GOLDEN_BLOCKS
LABELS = T.GOLDEN_LABELS

# 로고 → (브랜드 폴더, 떼어낸 페이지, 떼어낸 상자). celimax는 run.py에 없어 여기서 더함 — ×와 OLIVE YOUNG 앞까지
LOGO_BRAND = {"b.clinicx": "A000000213548", "goodal": "A000000219554",
              "goodal_serif": "A000000219554", "celimax": "A000000250199"}
LOGOS = list(R.LOGOS) + [("celimax", "images_A000000250199/A000000250199_002.jpg", (270, 80, 438, 130))]
BRAND_KEYS = {v.replace("images_", ""): k for v, k in T.BRANDS.items()}

# 2% 등비 — 점수가 배율 ±3% 밖에서 급락함(b.clinicx 1.10배 0.96 → ±4% 0.64~0.70). 12.5% 간격에서는 정답을 놓쳤음
SCALE_STEP = 1.02
N_SCALES = math.ceil(math.log(6.0 / 0.25) / math.log(SCALE_STEP)) + 1
SCALES = tuple(round(0.25 * SCALE_STEP ** i, 4) for i in range(N_SCALES))  # 0.25 ~ 6.0

VARIANTS = {
    "gray_bg": {"method": "gray", "mask": False, "thresh": 0.60},    # 기존 최선(template_gray_lo)과 같은 임계
    "gray_mask": {"method": "gray", "mask": True, "thresh": 0.60},   # 배경 제거 템플릿
    "edge_bg": {"method": "edge", "mask": False, "thresh": 0.45},    # 윤곽선
}
REPORT_FLOOR = 0.7    # 임계 × 이 값 이상은 '미달'로 남긴다 — 경계선 확인용
TARGET = {1, 2, 3, 5}  # PAGE_LOGOS 인덱스(0부터) — 떼어낸 자리(0·4)와 celimax(6) 제외


def page_box(b, off):
    return [b[0], b[1] + off, b[2], b[3] + off]


def center_in(inner, outer) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def templates() -> dict:
    tdir = OUT / "_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    out = {}
    for logo, src, box in LOGOS:
        g = R.load_gray(R.SRC / src)
        x1, y1, x2, y2 = box
        t = g[y1:y2, x1:x2].copy()
        # 배경 제거 근사 — 어두운 획만 남기고 획 주변 몇 px를 붙여 대비를 확보(투명 PNG 로고의 알파 대용)
        _, fg = cv2.threshold(t, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        m = cv2.dilate(fg, np.ones((3, 3), np.uint8), iterations=2)
        out[logo] = {"img": t, "mask": m, "src_page": Path(src).name, "src_box": list(box)}
        cv2.imencode(".png", t)[1].tofile(str(tdir / f"{logo}.png"))
        cv2.imencode(".png", m)[1].tofile(str(tdir / f"{logo}_mask.png"))
    return out


def match(sec: np.ndarray, tp: dict, cfg: dict) -> list[dict]:
    use_edge = cfg["method"] == "edge"
    src = R.edges(sec) if use_edge else sec
    floor = cfg["thresh"] * REPORT_FLOOR
    out = []
    for s in SCALES:
        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
        t = cv2.resize(tp["img"], None, fx=s, fy=s, interpolation=interp)
        if t.shape[0] < 12 or t.shape[1] < 24 or t.shape[0] >= src.shape[0] or t.shape[1] >= src.shape[1]:
            continue
        if use_edge:
            tt = R.edges(t)
            if tt.sum() == 0:
                continue
            res = cv2.matchTemplate(src, tt, cv2.TM_CCOEFF_NORMED)
        elif cfg["mask"]:
            mk = cv2.resize(tp["mask"], (t.shape[1], t.shape[0]), interpolation=cv2.INTER_NEAREST)
            res = cv2.matchTemplate(src, t, cv2.TM_CCOEFF_NORMED, mask=mk)
            res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            res = cv2.matchTemplate(src, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= floor)
        if len(ys) > 4000:
            idx = np.argsort(res[ys, xs])[-4000:]
            ys, xs = ys[idx], xs[idx]
        h, w = t.shape
        for y, x in zip(ys, xs):
            out.append({"bbox": [int(x), int(y), int(x + w), int(y + h)],
                        "score": round(float(min(res[y, x], 1.0)), 3), "scale": s})
    return R.nms(out)


def load_sections() -> list[dict]:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))["labels"]
    secs = []
    for f in sorted(REGIONS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sid, off = d["section"], d["top_offset"]
        blocks = json.loads((BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))["blocks"]
        lab = set(labels.get(sid, []))
        secs.append({"section": sid, "image": d["image"], "range": d["range"], "off": off,
                     "brand": sid[:13], "regions": d["regions"],
                     "label_boxes": [page_box(b["bbox"], off) for i, b in enumerate(blocks, 1) if i in lab]})
    return secs


def classify(det: dict, sec: dict, tp: dict) -> str:
    pb = det["page_bbox"]
    if det["page"] == tp["src_page"] and R.iou(pb, tp["src_box"]) > 0.3:
        return "원래 자리"
    for k, g in enumerate(T.PAGE_LOGOS):
        if g["image"] == det["page"] and center_in(g["bbox"], pb) and R.iou(g["bbox"], pb) >= 0.2:
            return f"로고{k + 1}"
    if any(center_in(pb, lb) or R.iou(pb, lb) >= 0.3 for lb in sec["label_boxes"]):
        return "라벨 소관"
    return "오탐"


def run_variant(name: str, secs: list[dict], tps: dict, pages: dict) -> dict:
    cfg = VARIANTS[name]
    t0 = time.perf_counter()
    dets, sec_sec = [], []
    page_name, page_img = None, None
    for sec in secs:
        if sec["image"] != page_name:
            page_name, page_img = sec["image"], R.load_gray(pages[sec["image"]])
        top, bot = sec["range"]
        gray = page_img[top:bot]
        ts = time.perf_counter()
        for logo, tp in tps.items():
            if LOGO_BRAND[logo] != sec["brand"]:
                continue
            for c in match(gray, tp, cfg):
                d = {**c, "logo": logo, "section": sec["section"], "page": sec["image"],
                     "page_bbox": page_box(c["bbox"], sec["off"]), "pass": c["score"] >= cfg["thresh"]}
                d["kind"] = classify(d, sec, tp)
                dets.append(d)
        sec_sec.append(time.perf_counter() - ts)

    passed = [d for d in dets if d["pass"]]
    found = {}
    for k in sorted(TARGET):
        hit = [d for d in passed if d["kind"] == f"로고{k + 1}"]
        best_any = max((d for d in dets if d["kind"] == f"로고{k + 1}"), key=lambda d: d["score"], default=None)
        found[k] = {"logo": T.PAGE_LOGOS[k], "status": "찾음" if hit else "놓침",
                    "best": max(hit, key=lambda d: d["score"]) if hit else best_any}
    false = [d for d in passed if d["kind"] == "오탐"]
    near = sorted((d for d in dets if not d["pass"] and d["kind"] == "오탐"), key=lambda d: -d["score"])[:10]
    counts = {"found": sum(v["status"] == "찾음" for v in found.values()),
              "missed": sum(v["status"] == "놓침" for v in found.values()), "false": len(false)}
    info = {"variant": name, "cfg": cfg, "scales": [SCALES[0], SCALES[-1], len(SCALES)],
            "counts": counts, "targets": [found[k] for k in sorted(found)],
            "false_hits": false, "near_false": near,
            "false_by_height": {"<20px": sum(1 for d in false if d["bbox"][3] - d["bbox"][1] < 20),
                                "20~40px": sum(1 for d in false if 20 <= d["bbox"][3] - d["bbox"][1] < 40),
                                ">=40px": sum(1 for d in false if d["bbox"][3] - d["bbox"][1] >= 40)},
            "false_by_logo": {k: sum(1 for d in false if d["logo"] == k) for k in sorted({d["logo"] for d in false})},
            "pass_by_kind": {k: sum(1 for d in passed if d["kind"] == k) for k in sorted({d["kind"] for d in passed})},
            "sec_per_section": {"mean": round(sum(sec_sec) / len(sec_sec), 3),
                                "max": round(max(sec_sec), 3)},
            "total_sec": round(time.perf_counter() - t0, 1)}
    info["_passed"] = passed
    return info


def mask_sections(passed: list[dict], secs: list[dict], pages: dict, out_dir: Path) -> dict:
    """통과 후보 자리를 둘레 색의 중앙값으로 칠한다. OCR이 그 자리를 못 읽게 하는 것이 목적."""
    by_sec: dict[str, list] = {}
    for d in passed:
        by_sec.setdefault(d["section"], []).append(d["bbox"])
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = {s["section"]: s for s in secs}
    cache, masked = {}, {}
    for sid, boxes in by_sec.items():
        sec = idx[sid]
        if sec["image"] not in cache:
            cache.clear()
            cache[sec["image"]] = cv2.imdecode(np.fromfile(str(pages[sec["image"]]), np.uint8), cv2.IMREAD_COLOR)
        top, bot = sec["range"]
        img = cache[sec["image"]][top:bot].copy()
        h, w = img.shape[:2]
        for x1, y1, x2, y2 in boxes:
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            ring = np.concatenate([img[max(0, y1 - 4):y1, x1:x2].reshape(-1, 3), img[y2:y2 + 4, x1:x2].reshape(-1, 3),
                                   img[y1:y2, max(0, x1 - 4):x1].reshape(-1, 3), img[y1:y2, x2:x2 + 4].reshape(-1, 3)])
            color = np.median(ring, axis=0) if len(ring) else np.array([255, 255, 255])
            img[y1:y2, x1:x2] = color.astype(np.uint8)
        p = out_dir / f"{sid}.png"
        cv2.imwrite(str(p), img)
        masked[sid] = {"path": p, "boxes": boxes}
    return masked


def ocr_array(model, img: np.ndarray) -> list[dict]:
    """섹션 OCR — 4,000px 넘으면 2,000px 띠 · 300px 겹침(단계 1 띠 규칙과 같은 몫 나눔)."""
    h = img.shape[0]
    if h <= 4000:
        tops = [0]
    else:
        tops = list(range(0, max(1, h - 300), 1700))
    regions = []
    for i, top in enumerate(tops):
        strip = img[top:top + (h if len(tops) == 1 else 2000)]
        res = list(model.predict(strip))[0]
        lo = top + (150 if i > 0 else 0)
        hi = top + strip.shape[0] - (150 if i < len(tops) - 1 else 0)
        for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) + top for p in poly]
            if not (lo <= (min(ys) + max(ys)) / 2 < hi):
                continue
            regions.append({"bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                            "text": text, "score": round(float(score), 4)})
    return regions


def downstream(model, masked: dict, secs: list[dict]) -> list[dict]:
    idx = {s["section"]: s for s in secs}
    rows = []
    for sid, m in masked.items():
        sec = idx[sid]
        img = cv2.imdecode(np.fromfile(str(m["path"]), np.uint8), cv2.IMREAD_COLOR)
        after = ocr_array(model, img)
        keys = [T.norm(k) for k in BRAND_KEYS[sec["brand"]]]
        boxes = m["boxes"]
        inside = lambda r: any(center_in(r["bbox"], b) for b in boxes)
        # ① 가린 자리에서 브랜드명이 다시 읽힘
        reread = [r["text"] for r in after if inside(r) and any(k in T.norm(r["text"]) for k in keys)]
        # ② 가린 자리 밖 글자가 사라짐 — 원래 영역(신뢰도 0.5 이상·텍스트 있음) 중 다시 못 찾은 것
        lost = []
        labels = [[b[0], b[1] - sec["off"], b[2], b[3] - sec["off"]] for b in sec["label_boxes"]]
        for r in sec["regions"]:
            if not r["text"].strip() or r.get("score", 1) < 0.5 or inside(r):
                continue
            if any(center_in(r["bbox"], lb) for lb in labels):   # 제품 인쇄 글자 — 라벨 소관
                continue
            if any(b[0] <= r["bbox"][0] and r["bbox"][2] <= b[2] and b[1] <= r["bbox"][1] and r["bbox"][3] <= b[3]
                   for b in boxes):
                continue
            straddle = any(R.iou(r["bbox"], b) > 0 for b in boxes)
            # OCR을 다시 돌리면 한두 글자가 달라짐 — 같은 자리(IoU ≥ 0.3)에 비슷한 글자(유사도 ≥ 0.6)가 있으면 남은 것으로 봄
            same = any(R.iou(r["bbox"], a["bbox"]) >= 0.3
                       and difflib.SequenceMatcher(None, T.norm(a["text"]), T.norm(r["text"])).ratio() >= 0.6
                       for a in after)
            if not same:
                near = [a["text"] for a in after if R.iou(r["bbox"], a["bbox"]) > 0]
                lost.append({"text": r["text"], "bbox": r["bbox"], "straddle": straddle, "now": near})
        # ③ 병합 후 블록에 브랜드명이 섞였는지
        w = img.shape[1]
        blocks = T.units_of(after, "block", w) if after else []
        # 가린 자리에 걸친 블록에 브랜드명이 남았는가 — 제목 속 한글 브랜드명은 로고가 아니므로 자리로 한정
        mixed = [b["text"] for b in blocks
                 if any(R.iou(b["bbox"], x) > 0 for x in boxes) and any(k in T.norm(b["text"]) for k in keys)]
        rows.append({"section": sid, "boxes": boxes, "regions_before": len(sec["regions"]),
                     "regions_after": len(after), "reread": reread, "lost": lost, "brand_in_block": mixed})
    return rows


def sheet(info: dict, pages: dict, out: Path) -> None:
    tiles = []
    for t in info["targets"]:
        g, b = t["logo"], t["best"]
        tiles.append((g["image"], g["bbox"], b["page_bbox"] if b else None,
                      f"{g['text']} y{g['bbox'][1]} {t['status']}" + (f" {b['score']}" if b else " 후보 없음"),
                      (20, 170, 60) if t["status"] == "찾음" else (220, 30, 30)))
    for d in info["false_hits"][:30]:
        tiles.append((d["page"], None, d["page_bbox"], f"오탐 {d['logo']} {d['score']} x{d['scale']}", (240, 140, 0)))
    cw, ch, cols = 360, 190, 3
    rows = max(1, math.ceil(len(tiles) / cols))
    canvas = Image.new("RGB", (cw * cols, ch * rows), (120, 120, 120))
    font = R._font(13)
    opened = {}
    for i, (page, truth, det, label, col) in enumerate(tiles):
        if page not in opened:
            opened.clear()
            opened[page] = Image.open(pages[page]).convert("RGB")
        im = opened[page]
        boxes = [b for b in (truth, det) if b]
        u = T.union_box(boxes)
        pad = 30
        box = (max(0, u[0] - pad), max(0, u[1] - pad), min(im.width, u[2] + pad), min(im.height, u[3] + pad))
        crop = im.crop(box)
        dr = ImageDraw.Draw(crop)
        if truth:
            dr.rectangle([truth[0] - box[0], truth[1] - box[1], truth[2] - box[0], truth[3] - box[1]], outline=(30, 90, 220), width=2)
        if det:
            dr.rectangle([det[0] - box[0], det[1] - box[1], det[2] - box[0], det[3] - box[1]], outline=col, width=3)
        s = min((cw - 4) / crop.width, (ch - 24) / crop.height, 2.0)
        crop = crop.resize((max(1, int(crop.width * s)), max(1, int(crop.height * s))))
        tile = Image.new("RGB", (cw - 2, ch - 2), (255, 255, 255))
        tile.paste(crop, (0, 22))
        ImageDraw.Draw(tile).text((3, 2), f"{page[:-4]} {label}", fill=col, font=font)
        canvas.paste(tile, ((i % cols) * cw, (i // cols) * ch))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=88)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all")
    ap.add_argument("--no-ocr", action="store_true")
    args = ap.parse_args()

    for p in (REGIONS, BLOCKS, LABELS):
        if not p.exists():
            raise SystemExit(f"상류 결과 없음: {p}")
    pages = {p.name: p for p in R.SRC.rglob("*.jpg")}
    tps = templates()
    secs = load_sections()
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    model = None
    if not args.no_ocr:
        from paddleocr import PaddleOCR
        model = PaddleOCR(**T.OCR_KWARGS)

    for n in names:
        info = run_variant(n, secs, tps, pages)
        c = info["counts"]
        print(f"[tmpl_{n}] 찾음 {c['found']} · 놓침 {c['missed']} · 오탐 {c['false']}  "
              f"(통과 구분 {info['pass_by_kind']}) · 섹션당 {info['sec_per_section']['mean']}s · {info['total_sec']}s", flush=True)
        for t in info["targets"]:
            b = t["best"]
            print(f"    {t['logo']['image']:<22} y{t['logo']['bbox'][1]:>6} {t['status']}  "
                  + (f"{b['logo']} {b['score']} x{b['scale']}" if b else "후보 없음"))
        passed = info.pop("_passed")
        out_dir = OUT / f"tmpl_{n}"
        if model is not None:
            masked = mask_sections(passed, secs, pages, OUT / "_masked" / n)
            info["downstream"] = downstream(model, masked, secs)
            lost = sum(len(r["lost"]) for r in info["downstream"])
            reread = sum(len(r["reread"]) for r in info["downstream"])
            mixed = sum(len(r["brand_in_block"]) for r in info["downstream"])
            info["downstream_counts"] = {"sections": len(masked), "reread": reread, "lost": lost, "brand_in_block": mixed}
            print(f"    하류 — 가린 섹션 {len(masked)} · 다시 읽힘 {reread} · 사라진 글자 {lost} · 블록에 섞인 브랜드명 {mixed}")
        info["run_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        sheet(info, pages, out_dir / "sheet.jpg")


if __name__ == "__main__":
    main()
