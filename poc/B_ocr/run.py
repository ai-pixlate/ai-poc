"""B. 텍스트 추출 — PaddleOCR variant 실행기.

사용법
    python run.py --variant baseline
    python run.py --variant all
    python run.py --variant baseline --images 1.jpg 2.jpg   # 일부만
    python run.py --variant baseline --sample golden        # 골든 샘플 섹션 102개
    python run.py --variant baseline --sample golden --sections A000000250199_014_003

출력
    results/{variant}/regions/{stem}.json   인식 결과
    results/{variant}/vis/{stem}.jpg        bbox 시각화 (영역 번호 표기)
    results/{variant}/meta.json             실행 조건·소요시간

    --sample golden
    results/golden/{variant}/regions/{섹션}.json   섹션 로컬 좌표 · 분할 조각 · top_offset
    results/golden/{variant}/vis/{섹션}.jpg        대지 — 섹션 bbox | 인식 텍스트
    results/golden/{variant}/meta.json             실행 조건·분할·소요시간
    섹션 id = {이미지 stem}_{섹션 index 3자리}

좌표계
    bbox : [x1, y1, x2, y2] 축 정렬 사각형. 좌상단 원점, 픽셀 정수.
    poly : PaddleOCR 원본 4점 다각형 [[x, y] * 4]. 기울어진 글자를 더 좁게 감싼다.
           E1 인페인팅 마스크는 poly를 쓰는 편이 지울 면적이 작다.
    골든 샘플은 **섹션 로컬 좌표**. 원본 위치는 top_offset + y.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
RESULTS = HERE / "results"

# variant = 실험 조건명.
#   engine "ocr" — PaddleOCR (PP-OCRv5 검출 + 한국어 인식)
#   engine "vl"  — PaddleOCR-VL
#
# VL 주의: 기본값(문서 파싱 모드)은 상세페이지에 못 쓴다. 레이아웃 분류기가
# 사진 구간을 통째로 image 블록으로 묶어버려 그 안의 글자가 선 단위 좌표를
# 잃는다. use_layout_detection=False + prompt_label="spotting" 으로 레이아웃
# 분류를 건너뛰어야 선마다 4점 좌표가 나온다.
_COMMON = dict(
    lang="korean",
    use_doc_orientation_classify=False,  # 상세페이지는 정방향 — 방향 분류 불필요
    use_doc_unwarping=False,             # 스캔 문서가 아니라 왜곡 보정 불필요
    use_textline_orientation=False,
)

VARIANTS: dict[str, dict] = {
    # 1단계 — 모델·파라미터
    "baseline": {"engine": "ocr", "kwargs": dict(_COMMON)},
    "det_side_1280": {
        "engine": "ocr",
        "kwargs": dict(
            _COMMON,
            # 기본 960(max)이면 긴 변 1280px 이미지가 축소된 뒤 검출된다.
            # 표본 최대 변이 1280이라 축소를 막는 값으로 올림.
            text_det_limit_side_len=1280,
            text_det_limit_type="max",
        ),
    },
    "vl_spotting": {
        "engine": "vl",
        "kwargs": {"use_layout_detection": False},
        "predict_kwargs": {"prompt_label": "spotting"},
    },
}


def image_paths(names: list[str] | None) -> list[Path]:
    if names:
        return [IMAGES / n for n in names]
    return sorted(
        (p for p in IMAGES.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}),
        key=lambda p: (len(p.stem), p.stem),  # 1.jpg < 2.jpg < 10.jpg
    )


def sort_reading(regions: list[dict]) -> None:
    """읽는 순서(위→아래, 왼→오른쪽)로 정렬.

    허용오차는 이미지 전체 글자 높이의 중앙값에서 한 번만 구한다.
    영역마다 제 높이로 나누면 큰 글자와 작은 글자의 몫이 뒤섞여 순서가 깨진다.
    """
    if regions:
        heights = sorted(r["bbox"][3] - r["bbox"][1] for r in regions)
        tol = max(10, heights[len(heights) // 2] // 2)
        regions.sort(key=lambda r: (r["bbox"][1] // tol, r["bbox"][0]))


def extract(res, engine: str = "ocr") -> list[dict]:
    """엔진 결과 1건 → regions 리스트."""
    d = res if isinstance(res, dict) else getattr(res, "json", {}).get("res", res)
    if engine == "vl":
        # spotting 결과는 별도 키에 담겨 나온다. 신뢰도는 제공되지 않음.
        d = d.get("spotting_res") or {}
        if not d:
            raise KeyError("spotting_res 비어 있음 — prompt_label='spotting' 여부 확인")

    texts = d.get("rec_texts")
    if texts is None:
        raise KeyError(f"rec_texts 없음. 사용 가능한 키: {sorted(d.keys())}")
    scores = d.get("rec_scores") or [None] * len(texts)
    polys = d.get("rec_polys")
    if polys is None:
        polys = d.get("dt_polys")
    if polys is None:
        raise KeyError(f"rec_polys/dt_polys 없음. 사용 가능한 키: {sorted(d.keys())}")

    regions = []
    for text, score, poly in zip(texts, scores, polys):
        pts = [[int(round(float(x))), int(round(float(y)))] for x, y in poly]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        regions.append(
            {
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "poly": pts,
                "text": text,
                "score": round(float(score), 4) if score is not None else None,
            }
        )
    sort_reading(regions)
    return regions


def dump_json(path: Path, payload: dict) -> None:
    """regions를 한 줄에 하나씩. 좌표 배열이 세로로 풀리는 걸 막는다."""
    body = ",\n  ".join(
        json.dumps(r, ensure_ascii=False, separators=(", ", ": ")) for r in payload["regions"]
    )
    head = {k: v for k, v in payload.items() if k != "regions"}
    lines = [
        "{",
        *(f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in head.items()),
        ' "regions": [',
        f"  {body}" if body else "",
        " ]",
        "}",
    ]
    path.write_text("\n".join(l for l in lines if l != ""), encoding="utf-8")


def _font(size: int):
    for name in ("arial.ttf", "segoeui.ttf", "malgun.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()  # 번호는 ASCII라 기본 폰트로도 읽힘


def visualize(img_path: Path, regions: list[dict], out_path: Path) -> None:
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(13, min(img.width, img.height) // 60)
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    for i, r in enumerate(regions, 1):
        draw.polygon([tuple(p) for p in r["poly"]], outline=(255, 0, 0), width=2)
        x1, y1, x2, _ = r["bbox"]
        label = str(i)
        box_w = int(draw.textlength(label, font=font)) + 2 * pad

        # 번호표가 글자를 덮으면 판정을 못 하므로 bbox 바깥에 붙인다.
        # 왼쪽 → 오른쪽 → 위쪽 순으로 자리를 찾고, 다 막히면 안쪽에 둔다.
        if x1 - box_w >= 0:
            left, top = x1 - box_w, y1
        elif x2 + box_w <= img.width:
            left, top = x2, y1
        elif y1 - box_h >= 0:
            left, top = x1, y1 - box_h
        else:
            left, top = x1, y1
        top = max(0, min(top, img.height - box_h))

        draw.rectangle([left, top, left + box_w, top + box_h], fill=(255, 0, 0))
        draw.text((left + pad, top + pad // 2), label, fill=(255, 255, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


def run_variant(name: str, paths: list[Path]) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}")

    spec = VARIANTS[name]
    engine, kwargs = spec["engine"], spec["kwargs"]
    predict_kwargs = spec.get("predict_kwargs", {})

    out_dir = RESULTS / name
    (out_dir / "regions").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    print(f"[{name}] 엔진 초기화 ({engine}) — {kwargs} {predict_kwargs}")
    t_init = time.perf_counter()
    if engine == "vl":
        from paddleocr import PaddleOCRVL

        model = PaddleOCRVL(**kwargs)
    else:
        from paddleocr import PaddleOCR

        model = PaddleOCR(**kwargs)
    init_sec = time.perf_counter() - t_init

    per_image, total_regions = [], 0
    for path in paths:
        t0 = time.perf_counter()
        result = list(model.predict(str(path), **predict_kwargs))
        regions = extract(result[0], engine)
        elapsed = time.perf_counter() - t0

        payload = {"image": path.name, "variant": name, "regions": regions}
        dump_json(out_dir / "regions" / f"{path.stem}.json", payload)
        visualize(path, regions, out_dir / "vis" / f"{path.stem}.jpg")

        total_regions += len(regions)
        per_image.append({"image": path.name, "regions": len(regions), "sec": round(elapsed, 2)})
        print(f"  {path.name:<10} 영역 {len(regions):>3}개  {elapsed:.2f}s")

    meta = {
        "variant": name,
        "engine": engine,
        "kwargs": {**kwargs, **predict_kwargs},
        "images": len(paths),
        "total_regions": total_regions,
        "init_sec": round(init_sec, 2),
        "total_sec": round(sum(p["sec"] for p in per_image), 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 총 {total_regions}개 영역, {meta['total_sec']}s\n")


# ── 골든 샘플 — 섹션 단위 ────────────────────────────────────────────────
# 입력은 섹션 분해 채택안 `color_snap_vlm2`의 섹션 범위. 원본에서 잘라 넣는다
# (section_split crops/는 같은 픽셀을 JPEG로 다시 저장한 것).
GOLDEN_SRC = ROOT / "data" / "golden_sample"
GOLDEN_SECTIONS = ROOT / "poc" / "section_split" / "results" / "color_snap_vlm2" / "sections"
GOLDEN_RESULTS = RESULTS / "golden"
GOLDEN_VARIANTS = ("baseline",)  # 확정 조건만 재실행

# 결과 문서 10장 27번 — 섹션이 검출기 긴 변 상한을 넘으면 OCR 전에 추가 분할.
#   여백 우선  섹션 분해 `ws_std` 여백 판정 그대로 (행 밝기 표준편차 ≤ 6이 40px 이상 연속)
#   겹침 띠   여백이 없을 때. ocr_split `tile_2000_ov300` 그대로 (중심이 띠의 몫에 든 영역만)
DET_LIMIT = 4000
WS_TOL, WS_MIN_GAP, WS_MIN_PIECE = 6.0, 40, 200
BAND, BAND_OVERLAP = 2000, 300
EDGE_PX = 2  # 조각 위아래 끝 이 안에 닿으면 '경계 닿음' — 잘림 의심
LOW_SCORE = 0.5
PANEL_W = 560


def blank_runs(vals, tol: float, min_gap: int) -> list[tuple[int, int]]:
    """여백 행이 min_gap 이상 이어지는 구간. poc/section_split/run.py 복사."""
    blank = vals <= tol
    runs, start = [], None
    for y, b in enumerate(blank):
        if b and start is None:
            start = y
        elif not b and start is not None:
            if y - start >= min_gap:
                runs.append((start, y))
            start = None
    if start is not None and len(blank) - start >= min_gap:
        runs.append((start, len(blank)))
    return runs


def split_span(gray, lo: int, hi: int) -> tuple[list[dict], list[dict]]:
    """[lo, hi) → (조각, 이음선). 조각 = {range, keep}, 이음선 = {y, kind}.

    keep은 조각에서 영역을 채택하는 구간 — 영역 중심 y가 여기 들어야 남긴다.
    """
    if hi - lo <= DET_LIMIT:
        return [{"range": [lo, hi], "keep": [lo, hi]}], []
    runs = blank_runs(gray[lo:hi].std(axis=1), WS_TOL, WS_MIN_GAP)
    cands = [lo + (a + b) // 2 for a, b in runs if a > 0 and b < hi - lo]
    cands = [c for c in cands if c - lo >= WS_MIN_PIECE and hi - c >= WS_MIN_PIECE]
    if cands:
        # 조각이 고르게 나오도록 가운데에 가장 가까운 여백을 자른다. 남은 쪽이 길면 다시 자른다
        c = min(cands, key=lambda y: abs(y - (lo + hi) / 2))
        p1, s1 = split_span(gray, lo, c)
        p2, s2 = split_span(gray, c, hi)
        return p1 + p2, s1 + [{"y": c, "kind": "blank"}] + s2

    span = hi - lo
    tops = list(range(0, max(1, span - BAND_OVERLAP), BAND - BAND_OVERLAP))
    pieces, seams = [], []
    for i, t in enumerate(tops):
        b = min(span, t + BAND)
        k0 = t + (BAND_OVERLAP // 2 if i > 0 else 0)
        k1 = b - (BAND_OVERLAP // 2 if i < len(tops) - 1 else 0)
        pieces.append({"range": [lo + t, lo + b], "keep": [lo + k0, lo + k1]})
        if i > 0:
            seams.append({"y": lo + k0, "kind": "band"})
    return pieces, seams


def golden_sections(only: list[str] | None) -> list[dict]:
    items = []
    for f in sorted(GOLDEN_SECTIONS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        stem = Path(d["image"]).stem
        for s in d["sections"]:
            sid = f"{stem}_{s['index']:03d}"
            if only and sid not in only:
                continue
            items.append({"id": sid, "image": d["image"], "index": s["index"],
                          "top_offset": s["top_offset"], "range": s["range"]})
    return items


def _kfont(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def region_color(r: dict) -> tuple[int, int, int]:
    if not r["text"].strip():
        return (200, 0, 200)   # 빈 텍스트
    if r["score"] is not None and r["score"] < LOW_SCORE:
        return (255, 140, 0)   # 저신뢰
    return (230, 0, 0)


def _wrap(text: str, font, width: int) -> list[str]:
    out, cur = [], ""
    for ch in text:
        if cur and font.getlength(cur + ch) > width:
            out.append(cur)
            cur = "    " + ch
        else:
            cur += ch
    out.append(cur)
    return out


def golden_board(sec_img: Image.Image, payload: dict, out_path: Path) -> None:
    """대지 — 왼쪽 섹션 원본에 poly · 번호 · 이음선, 오른쪽 번호별 인식 텍스트."""
    w, h = sec_img.size
    regions = payload["regions"]
    left = sec_img.convert("RGB")
    draw = ImageDraw.Draw(left)
    size = 15
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    for i, r in enumerate(regions, 1):
        col = region_color(r)
        draw.polygon([tuple(p) for p in r["poly"]], outline=col, width=2)
        x1, y1, x2, _ = r["bbox"]
        label = str(i)
        box_w = int(draw.textlength(label, font=font)) + 2 * pad
        if x1 - box_w >= 0:
            lx, ly = x1 - box_w, y1
        elif x2 + box_w <= w:
            lx, ly = x2, y1
        elif y1 - box_h >= 0:
            lx, ly = x1, y1 - box_h
        else:
            lx, ly = x1, y1
        ly = max(0, min(ly, h - box_h))
        draw.rectangle([lx, ly, lx + box_w, ly + box_h], fill=col)
        draw.text((lx + pad, ly + pad // 2), label, fill=(255, 255, 255), font=font)

    for s in payload["seams"]:
        draw.line([(0, s["y"]), (w, s["y"])], fill=(0, 110, 255), width=3)
        draw.text((4, s["y"] + 3), f"seam {s['kind']} y={s['y']}", fill=(0, 110, 255), font=font)

    kf = _kfont(15)
    lh = 21
    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"{payload['section']}  {w}x{h}px  top_offset {payload['top_offset']}", (0, 0, 0)),
        (f"영역 {len(regions)}  조각 {len(payload['chunks'])}  이음선 {len(payload['seams'])}", (0, 0, 0)),
        ("빨강 일반 · 주황 신뢰도<0.5 · 보라 빈 텍스트 · 파랑 이음선", (110, 110, 110)),
        ("", (0, 0, 0)),
    ]
    for i, r in enumerate(regions, 1):
        txt = r["text"] if r["text"].strip() else "(빈 텍스트)"
        mark = "  [경계]" if r.get("edge_touch") else ""
        col = region_color(r)
        tcol = (0, 0, 0) if col == (230, 0, 0) else col
        for seg in _wrap(f"{i}. {txt}  ({r['score']:.2f}){mark}", kf, PANEL_W - 24):
            lines.append((seg, tcol))

    H = max(h, 12 + lh * len(lines) + 12)
    board = Image.new("RGB", (w + PANEL_W, H), (255, 255, 255))
    board.paste(left, (0, 0))
    d2 = ImageDraw.Draw(board)
    d2.line([(w, 0), (w, H)], fill=(180, 180, 180), width=2)
    y = 12
    for seg, col in lines:
        d2.text((w + 12, y), seg, fill=col, font=kf)
        y += lh
    out_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(out_path, quality=90)


def run_golden(name: str, only: list[str] | None) -> None:
    import cv2
    import numpy as np

    if name not in GOLDEN_VARIANTS:
        raise SystemExit(f"골든 샘플은 확정 조건만 실행: {', '.join(GOLDEN_VARIANTS)}")
    spec = VARIANTS[name]
    sections = golden_sections(only)
    if not sections:
        raise SystemExit("대상 섹션 없음")
    paths = {p.name: p for p in GOLDEN_SRC.rglob("*.jpg")}

    out_dir = GOLDEN_RESULTS / name
    (out_dir / "regions").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    print(f"[golden/{name}] 엔진 초기화 — {spec['kwargs']}")
    from paddleocr import PaddleOCR

    t_init = time.perf_counter()
    model = PaddleOCR(**spec["kwargs"])
    init_sec = time.perf_counter() - t_init

    per, page_name, page = [], None, None
    for s in sections:
        if s["image"] != page_name:
            page_name = s["image"]
            page = cv2.imdecode(np.fromfile(str(paths[page_name]), dtype=np.uint8), cv2.IMREAD_COLOR)
        top, bottom = s["range"]
        sec = page[top:bottom]
        h, w = sec.shape[:2]
        pieces, seams = split_span(cv2.cvtColor(sec, cv2.COLOR_BGR2GRAY), 0, h)

        regions, errors, t0 = [], [], time.perf_counter()
        for ci, pc in enumerate(pieces):
            t, b = pc["range"]
            k0, k1 = pc["keep"]
            last = ci == len(pieces) - 1
            try:
                res = list(model.predict(sec[t:b]))[0]
            except cv2.error as e:
                errors.append({"chunk": ci, "range": [t, b], "error": str(e).splitlines()[-1][:160]})
                continue
            for r in extract(res):
                ys = [p[1] for p in r["poly"]]
                cy = (min(ys) + max(ys)) / 2 + t
                if not (k0 <= cy < k1 or (last and cy >= k1)):
                    continue
                touch = (t > 0 and min(ys) <= EDGE_PX) or (b < h and max(ys) >= (b - t) - EDGE_PX)
                poly = [[x, y + t] for x, y in r["poly"]]
                px, py = [p[0] for p in poly], [p[1] for p in poly]
                regions.append({"bbox": [min(px), min(py), max(px), max(py)], "poly": poly,
                                "text": r["text"], "score": r["score"],
                                "chunk": ci, "edge_touch": bool(touch)})
        sort_reading(regions)
        sec_time = round(time.perf_counter() - t0, 2)

        payload = {"section": s["id"], "image": s["image"], "index": s["index"], "variant": name,
                   "top_offset": s["top_offset"], "range": [top, bottom], "size": [w, h],
                   "chunks": pieces, "seams": seams, "errors": errors, "sec": sec_time,
                   "regions": regions}
        dump_json(out_dir / "regions" / f"{s['id']}.json", payload)
        golden_board(Image.fromarray(cv2.cvtColor(sec, cv2.COLOR_BGR2RGB)), payload,
                     out_dir / "vis" / f"{s['id']}.jpg")

        low = sum(1 for r in regions if r["text"].strip() and r["score"] < LOW_SCORE)
        empty = sum(1 for r in regions if not r["text"].strip())
        per.append({"section": s["id"], "height": h, "chunks": len(pieces), "regions": len(regions),
                    "low_score": low, "empty_text": empty, "errors": len(errors), "sec": sec_time})
        print(f"  {s['id']:<24} {h:>5}px  조각 {len(pieces)}  영역 {len(regions):>3}  {sec_time}s"
              + (f"  오류 {len(errors)}" if errors else ""))

    if only:
        print(f"[golden/{name}] 일부 섹션만 실행 — meta.json 갱신 안 함")
        return
    meta = {
        "variant": name,
        "sample": "golden",
        "engine": spec["engine"],
        "kwargs": spec["kwargs"],
        "section_source": "poc/section_split/results/color_snap_vlm2",
        "split_rule": {"det_limit": DET_LIMIT, "blank": {"metric": "std", "tol": WS_TOL,
                       "min_gap": WS_MIN_GAP, "min_piece": WS_MIN_PIECE},
                       "band": {"size": BAND, "overlap": BAND_OVERLAP}},
        "sections": len(per),
        "split_sections": [p["section"] for p in per if p["chunks"] > 1],
        "pieces": sum(p["chunks"] for p in per),
        "total_regions": sum(p["regions"] for p in per),
        "low_score": sum(p["low_score"] for p in per),
        "empty_text": sum(p["empty_text"] for p in per),
        "errors": sum(p["errors"] for p in per),
        "init_sec": round(init_sec, 2),
        "total_sec": round(sum(p["sec"] for p in per), 2),
        "per_section": per,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[golden/{name}] 완료 — 섹션 {meta['sections']} · 조각 {meta['pieces']} · "
          f"영역 {meta['total_regions']} · {meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    ap.add_argument("--sample", choices=("default", "golden"), default="default",
                    help="default = data/images 12장 · golden = 골든 샘플 섹션")
    ap.add_argument("--sections", nargs="*", default=None, help="golden 일부 섹션 id")
    args = ap.parse_args()

    if args.sample == "golden":
        names = list(GOLDEN_VARIANTS) if args.variant == "all" else [args.variant]
        for name in names:
            run_golden(name, args.sections)
        return

    paths = image_paths(args.images)
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"이미지 없음: {missing}")
    if not paths:
        raise SystemExit(f"{IMAGES} 에 이미지 없음")

    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for name in names:
        run_variant(name, paths)


if __name__ == "__main__":
    main()
