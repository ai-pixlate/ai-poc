"""B. 텍스트 추출 — PaddleOCR variant 실행기.

사용법
    python run.py --variant baseline
    python run.py --variant all
    python run.py --variant baseline --images 1.jpg 2.jpg   # 일부만

출력
    results/{variant}/regions/{stem}.json   인식 결과
    results/{variant}/vis/{stem}.jpg        bbox 시각화 (영역 번호 표기)
    results/{variant}/meta.json             실행 조건·소요시간

좌표계
    bbox : [x1, y1, x2, y2] 축 정렬 사각형. 좌상단 원점, 픽셀 정수.
    poly : PaddleOCR 원본 4점 다각형 [[x, y] * 4]. 기울어진 글자를 더 좁게 감싼다.
           E1 인페인팅 마스크는 poly를 쓰는 편이 지울 면적이 작다.
"""

from __future__ import annotations

import argparse
import json
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

    # 읽는 순서(위→아래, 왼→오른쪽)로 정렬.
    # 허용오차는 이미지 전체 글자 높이의 중앙값에서 한 번만 구한다.
    # 영역마다 제 높이로 나누면 큰 글자와 작은 글자의 몫이 뒤섞여 순서가 깨진다.
    if regions:
        heights = sorted(r["bbox"][3] - r["bbox"][1] for r in regions)
        tol = max(10, heights[len(heights) // 2] // 2)
        regions.sort(key=lambda r: (r["bbox"][1] // tol, r["bbox"][0]))
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

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
