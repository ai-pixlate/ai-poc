"""제품 라벨 판정 — 로컬 variant 실행기.

제품 용기·패키지에 인쇄된 글자를 배경 위 텍스트와 구분한다.
라벨로 판정된 블록은 하류에서 번역·인페인팅 대상에서 통째로 빠진다.

LLM을 쓰지 않는 세 경로를 먼저 잰다. 전부 로컬 실행, 비용 0.

variant
    mask_overlap  제품컷 누끼 마스크와 블록 bbox의 교차.
                  전경(제품) 안에 있으면 라벨로 본다.
                  재료는 G 과업이 이미 만든 `birefnet-general` 마스크다.
    bg_texture    블록 주변 화소의 밝기 분산. 라벨은 사진·곡면 위에 있어
                  주변이 울퉁불퉁하고, 배경 텍스트는 평면 위라 고르다.
    poly_skew     인식 poly의 기울기·사다리꼴 정도. 용기에 인쇄된 글자는
                  원근과 곡면 때문에 축 정렬 사각형에서 벗어난다.

입력
    ../block_role/results/llm_assist/blocks/{stem}.json   (채택 블록)
    ../B_ocr/results/baseline/regions/{stem}.json         (poly — poly_skew용)
    ../G_cutout/results/rembg_birefnet/mask/{stem}.png    (mask_overlap용)

출력
    results/{variant}/blocks/{stem}.json   is_product_label + 판정에 쓴 수치
    results/{variant}/vis/{stem}.jpg       라벨은 빨강, 배경은 파랑
    results/{variant}/meta.json            임계·집계

판정
    **미탐 0 우선.** 오탐(라벨이 아닌데 라벨로 봄)은 번역이 누락돼 검수에서
    복구되지만, 미탐(라벨인데 놓침)은 제품 사진 위 글자가 지워져 복구 불가다.
    등급은 사람이 매긴다. 이 코드는 판정하지 않는다.

사용법
    python run.py --variant all
    python run.py --variant mask_overlap --images 11.jpg
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
SRC = ROOT / "poc" / "block_role" / "results" / "llm_assist" / "blocks"
REGIONS = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"
MASKS = ROOT / "poc" / "G_cutout" / "results" / "rembg_birefnet" / "mask"
RESULTS = HERE / "results"

# variant = 실험 조건명. 임계는 전부 이 표에서만 바꾼다.
#   cover  : bbox 안에서 전경 마스크가 덮은 비율이 이 값을 넘으면 라벨
#   std    : 블록 주변 띠의 밝기 표준편차가 이 값을 넘으면 라벨
#   ring   : 주변 띠의 폭 (블록 높이 배수)
#   deg    : poly 윗변 기울기(도)가 이 값을 넘으면 라벨
#   hdiff  : poly 좌우 높이 차 비율이 이 값을 넘으면 라벨
VARIANTS: dict[str, dict] = {
    "mask_overlap": {"cover": 0.5},
    "bg_texture": {"std": 18.0, "ring": 0.6},
    "poly_skew": {"deg": 2.0, "hdiff": 0.06},
}


# ---------------------------------------------------------------- 유틸
# block_role 과업의 것을 복사했다. 과업 간 코드는 공유하지 않는다(CLAUDE.md).

def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def dump_json(path: Path, payload: dict) -> None:
    body = ",\n  ".join(
        json.dumps(b, ensure_ascii=False, separators=(", ", ": ")) for b in payload["blocks"]
    )
    head = {k: v for k, v in payload.items() if k != "blocks"}
    lines = [
        "{",
        *(f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in head.items()),
        ' "blocks": [',
        f"  {body}" if body else "",
        " ]",
        "}",
    ]
    path.write_text("\n".join(l for l in lines if l != ""), encoding="utf-8")


def visualize(img_path: Path, blocks: list[dict], out_path: Path) -> None:
    """라벨은 빨강, 배경 텍스트는 파랑. 판정 결과가 한눈에 갈리게 한다."""
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(13, min(img.width, img.height) // 55)
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    for i, b in enumerate(blocks, 1):
        is_label = b["is_product_label"]
        color = (220, 30, 30) if is_label else (30, 90, 220)
        draw.rectangle(b["bbox"], outline=color, width=3)
        x1, y1, x2, _ = b["bbox"]
        text = f"{i} {'라벨' if is_label else '배경'} {b['score']}"
        box_w = int(draw.textlength(text, font=font)) + 2 * pad

        if y1 - box_h >= 0:
            left, top = x1, y1 - box_h
        elif x1 - box_w >= 0:
            left, top = x1 - box_w, y1
        else:
            left, top = min(x2, img.width - box_w), y1
        left = max(0, min(left, img.width - box_w))
        top = max(0, min(top, img.height - box_h))

        draw.rectangle([left, top, left + box_w, top + box_h], fill=color)
        draw.text((left + pad, top + pad // 2), text, fill=(255, 255, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


# ---------------------------------------------------------------- 판정기

def judge_mask(blocks: list[dict], stem: str, img: Image.Image, cfg: dict) -> list[dict]:
    """전경 마스크가 bbox를 덮은 비율."""
    path = MASKS / f"{stem}.png"
    if not path.exists():
        raise SystemExit(f"누끼 마스크 없음: {path} — G 과업을 먼저 실행할 것")
    mask = Image.open(path).convert("L")
    sx, sy = mask.width / img.width, mask.height / img.height

    out = []
    for b in blocks:
        x1, y1, x2, y2 = b["bbox"]
        crop = mask.crop(
            (int(x1 * sx), int(y1 * sy), max(int(x1 * sx) + 1, int(x2 * sx)),
             max(int(y1 * sy) + 1, int(y2 * sy)))
        )
        px = list(crop.getdata())
        cover = sum(1 for p in px if p > 127) / max(1, len(px))
        out.append({**b, "score": round(cover, 3), "is_product_label": cover > cfg["cover"]})
    return out


def judge_texture(blocks: list[dict], stem: str, img: Image.Image, cfg: dict) -> list[dict]:
    """블록을 둘러싼 띠의 밝기 표준편차.

    블록 안쪽은 글자라 어느 배경에서든 대비가 크다. 배경의 성질을 보려면
    글자를 뺀 **주변**을 봐야 한다.
    """
    gray = img.convert("L")
    out = []
    for b in blocks:
        x1, y1, x2, y2 = b["bbox"]
        pad = max(4, int((y2 - y1) * cfg["ring"]))
        ox1, oy1 = max(0, x1 - pad), max(0, y1 - pad)
        ox2, oy2 = min(img.width, x2 + pad), min(img.height, y2 + pad)
        outer = gray.crop((ox1, oy1, ox2, oy2))
        w, h = outer.size
        ix1, iy1 = x1 - ox1, y1 - oy1
        ix2, iy2 = ix1 + (x2 - x1), iy1 + (y2 - y1)

        px = list(outer.getdata())
        ring = [
            v for idx, v in enumerate(px)
            if not (ix1 <= idx % w < ix2 and iy1 <= idx // w < iy2)
        ]
        if len(ring) < 2:
            std = 0.0
        else:
            m = sum(ring) / len(ring)
            std = math.sqrt(sum((v - m) ** 2 for v in ring) / len(ring))
        out.append({**b, "score": round(std, 1), "is_product_label": std > cfg["std"]})
    return out


def judge_skew(blocks: list[dict], stem: str, img: Image.Image, cfg: dict) -> list[dict]:
    """인식 poly가 축 정렬 사각형에서 얼마나 벗어났는가.

    윗변 기울기와 좌우 높이 차 중 큰 쪽을 쓴다. 하나라도 임계를 넘으면 라벨.
    """
    regions = json.loads((REGIONS / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
    out = []
    for b in blocks:
        deg_max, hdiff_max = 0.0, 0.0
        for i in b["regions"]:
            if i >= len(regions):
                continue
            p = regions[i]["poly"]
            (ax, ay), (bx, by), (cx, cy), (dx, dy) = p[0], p[1], p[2], p[3]
            deg = abs(math.degrees(math.atan2(by - ay, max(1, bx - ax))))
            left_h, right_h = abs(dy - ay), abs(cy - by)
            hdiff = abs(left_h - right_h) / max(1, max(left_h, right_h))
            deg_max, hdiff_max = max(deg_max, deg), max(hdiff_max, hdiff)
        label = deg_max > cfg["deg"] or hdiff_max > cfg["hdiff"]
        out.append(
            {**b, "score": f"{deg_max:.1f}°/{hdiff_max:.2f}", "is_product_label": label}
        )
    return out


JUDGE = {"mask_overlap": judge_mask, "bg_texture": judge_texture, "poly_skew": judge_skew}


# ---------------------------------------------------------------- 실행

def run_variant(name: str, stems: list[str]) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    (out_dir / "blocks").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    print(f"[{name}] {cfg}")
    per_image = []
    t_all = time.perf_counter()
    for stem in stems:
        src = json.loads((SRC / f"{stem}.json").read_text(encoding="utf-8"))
        blocks = src["blocks"]
        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        img = Image.open(img_path).convert("RGB")

        t0 = time.perf_counter()
        new = JUDGE[name](blocks, stem, img, cfg)
        sec = time.perf_counter() - t0
        n_label = sum(1 for b in new if b["is_product_label"])

        dump_json(
            out_dir / "blocks" / f"{stem}.json",
            {"image": img_path.name, "variant": name, "cfg": cfg,
             "blocks_in": len(blocks), "labels": n_label, "blocks": new},
        )
        visualize(img_path, new, out_dir / "vis" / f"{stem}.jpg")
        per_image.append({"image": img_path.name, "blocks": len(new), "labels": n_label,
                          "sec": round(sec, 2)})
        print(f"  {img_path.name:<10} 블록 {len(new):>3}  라벨 {n_label:>3}  {sec:.2f}s")

    meta = {
        "variant": name,
        "cfg": cfg,
        "source": "poc/block_role/results/llm_assist",
        "images": len(stems),
        "total_blocks": sum(p["blocks"] for p in per_image),
        "total_labels": sum(p["labels"] for p in per_image),
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 블록 {meta['total_blocks']} 중 라벨 {meta['total_labels']}, "
          f"{meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    stems = (
        [Path(n).stem for n in args.images]
        if args.images
        else sorted((p.stem for p in SRC.glob("*.json")), key=lambda s: (len(s), s))
    )
    missing = [s for s in stems if not (SRC / f"{s}.json").exists()]
    if missing:
        raise SystemExit(f"상류 블록 없음: {missing} — block_role 의 llm_assist 를 먼저 실행할 것")

    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, stems)


if __name__ == "__main__":
    main()
