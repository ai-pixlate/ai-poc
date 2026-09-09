"""섹션 분해 + 절단 지점 산출 — variant 실행기.

초장축 상세페이지를 **여백에서** 잘라 섹션으로 나눈다. 전부 로컬, 비용 0.

왜 먼저 자르는가
    1000×37,665 같은 이미지는 텍스트 인식에 그대로 넣을 수 없다. 검출기가
    긴 변을 기준으로 축소해 글자가 사라진다. 고정 크기 타일로 자르면 경계가
    글자 한복판을 지나 누락이 생긴다.
    **여백에서 자르면 경계가 글자를 지나지 않는다.** 섹션은 하류에서도
    그대로 쓰이므로 버리는 중간물이 아니다.

두 층을 구분한다
    처리 단위  텍스트 인식에 넣을 크기로 잘게 나눈 것. 여백이면 어디서든 자른다.
    **의미 섹션**  제품소개·고민·제품제시·효과소개 같은 문맥 단위. 굵직하게 나눈다.
    앞의 것은 버리는 중간물이고, 하류(조판·검수)가 쓰는 것은 뒤의 것이다.

variant
    ws_std     처리 단위 — 행별 밝기 표준편차가 낮으면 여백 행
    ws_edge    처리 단위 — 행별 엣지 밀도가 낮으면 여백 행
    gap_major  **의미 섹션** — 큰 여백과 배경색 전환이 겹치는 곳만 자른다

폴백
    사진이 길게 이어져 여백 행이 없으면 섹션이 여전히 초장축으로 남는다.
    `max_section`을 넘으면 **강제 분할**하고 그 사실을 기록한다. 강제 분할한
    자리는 글자를 지날 수 있으므로 판정에서 따로 본다.

출력
    results/{variant}/sections/{stem}.json   절단 y좌표·섹션 범위·top_offset·폴백 여부
    results/{variant}/crops/{stem}/{i}.jpg   섹션 이미지. 다음 단계(OCR) 입력
    results/{variant}/vis/{stem}.jpg         축소 미리보기에 절단선 표시
    results/{variant}/meta.json              집계

사용법
    python run.py --variant all
    python run.py --variant ws_std --images A000000219554_002.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
RESULTS = HERE / "results"

# variant = 실험 조건명.
#   metric      여백 판정에 쓰는 값 (std | edge)
#   tol         이 값 이하인 행을 여백으로 본다
#   min_gap     여백이 이만큼 연속돼야 절단 후보로 삼는다 (px)
#   min_section 섹션이 이보다 짧으면 앞 섹션에 붙인다 (px)
#   max_section 이보다 길면 강제 분할한다 (px). 폴백
#   big_gap     이만큼 넓은 여백은 그것만으로 의미 경계로 본다 (px, gap_major)
#   color_delta 여백 앞뒤 배경색이 이만큼 바뀌면 경계로 본다 (0~255, gap_major)
VARIANTS: dict[str, dict] = {
    "ws_std": {"metric": "std", "tol": 6.0, "min_gap": 40, "min_section": 200,
               "max_section": 4000},
    "ws_edge": {"metric": "edge", "tol": 0.01, "min_gap": 40, "min_section": 200,
                "max_section": 4000},
    # 의미 섹션 — 잘게 자르지 않는다. 최소 섹션이 1500px, 폴백 상한도 크게 둔다.
    "gap_major": {"metric": "std", "tol": 6.0, "min_gap": 40, "min_section": 1500,
                  "max_section": 12000, "big_gap": 200, "color_delta": 30},
}


def row_metric(gray: np.ndarray, metric: str) -> np.ndarray:
    """행마다 하나의 값. 낮을수록 '아무것도 없는 행'이다."""
    if metric == "std":
        return gray.std(axis=1)
    # edge — 가로 방향 밝기 변화가 있는 화소의 비율
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    return (dx > 12).mean(axis=1)


def blank_runs(vals: np.ndarray, tol: float, min_gap: int) -> list[tuple[int, int]]:
    """여백 행이 min_gap 이상 이어지는 구간."""
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


def major_runs(runs: list[tuple[int, int]], rowmean: np.ndarray, h: int,
               cfg: dict) -> list[tuple[int, int]]:
    """의미 경계로 볼 만한 여백만 남긴다.

    두 신호 중 하나면 통과 — **넓은 여백** 또는 **여백 앞뒤 배경색 전환**.
    상세페이지는 문맥이 바뀔 때 배경을 갈아끼우는 경우가 많다.
    """
    keep = []
    for a, b in runs:
        if a <= 0 or b >= h:
            continue
        if b - a >= cfg["big_gap"]:
            keep.append((a, b))
            continue
        before = rowmean[max(0, a - 30):a]
        after = rowmean[b:b + 30]
        if len(before) == 0 or len(after) == 0:
            continue
        delta = float(np.abs(before.mean(axis=0) - after.mean(axis=0)).max())
        if delta >= cfg["color_delta"]:
            keep.append((a, b))
    return keep


def cut_points(vals: np.ndarray, h: int, cfg: dict,
               rowmean: np.ndarray | None = None) -> tuple[list[int], list[int]]:
    """절단 y좌표를 고른다. (절단점, 강제 분할한 절단점)"""
    runs = blank_runs(vals, cfg["tol"], cfg["min_gap"])
    if "big_gap" in cfg and rowmean is not None:
        runs = major_runs(runs, rowmean, h, cfg)
    # 여백 구간의 한가운데를 자른다. 양끝 여백은 절단점이 아니다.
    cands = [(a + b) // 2 for a, b in runs if a > 0 and b < h]

    cuts: list[int] = []
    last = 0
    for c in cands:
        if c - last >= cfg["min_section"] and h - c >= cfg["min_section"]:
            cuts.append(c)
            last = c

    # 폴백 — 여백이 없어 너무 길게 남은 구간을 강제로 자른다
    forced: list[int] = []
    bounds = [0] + cuts + [h]
    for a, b in zip(bounds, bounds[1:]):
        span = b - a
        if span <= cfg["max_section"]:
            continue
        n = int(np.ceil(span / cfg["max_section"]))
        step = span // n
        for k in range(1, n):
            forced.append(a + step * k)
    if forced:
        cuts = sorted(cuts + forced)
    return cuts, forced


def visualize(img: Image.Image, cuts: list[int], forced: list[int], out: Path) -> None:
    """축소 미리보기에 절단선. 초장축이라 폭 240으로 줄여 세로로 길게 남긴다."""
    w, h = img.size
    scale = 240 / w
    thumb = img.resize((240, max(1, int(h * scale))), Image.BILINEAR).convert("RGB")
    arr = np.array(thumb)
    for c in cuts:
        y = int(c * scale)
        if 0 <= y < arr.shape[0]:
            arr[y, :] = (220, 30, 30) if c not in forced else (255, 150, 0)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out, quality=90)


def run_variant(name: str, paths: list[Path]) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    for sub in ("sections", "crops", "vis"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    print(f"[{name}] {cfg}")
    per_image = []
    t_all = time.perf_counter()

    for path in paths:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        vals = row_metric(gray, cfg["metric"])
        rowmean = np.array(img).reshape(h, -1, 3).mean(axis=1)
        cuts, forced = cut_points(vals, h, cfg, rowmean)

        bounds = [0] + cuts + [h]
        sections = []
        crop_dir = out_dir / "crops" / path.stem
        crop_dir.mkdir(parents=True, exist_ok=True)
        for i, (y0, y1) in enumerate(zip(bounds, bounds[1:]), 1):
            crop = img.crop((0, y0, w, y1))
            crop.save(crop_dir / f"{i:03d}.jpg", quality=92)
            sections.append({
                "index": i,
                "top_offset": y0,          # 계약 — 원본 y = top_offset + 섹션 내 y
                "range": [y0, y1],
                "height": y1 - y0,
                "forced": y0 in forced,    # 강제 분할로 생긴 시작점인가
                "crop": f"crops/{path.stem}/{i:03d}.jpg",
            })

        (out_dir / "sections" / f"{path.stem}.json").write_text(
            json.dumps({"image": path.name, "variant": name, "size": [w, h],
                        "cuts": cuts, "forced_cuts": forced, "sections": sections},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        visualize(img, cuts, forced, out_dir / "vis" / f"{path.stem}.jpg")

        heights = [s["height"] for s in sections]
        per_image.append({"image": path.name, "size": [w, h], "sections": len(sections),
                          "forced": len(forced), "max_height": max(heights),
                          "median_height": int(np.median(heights))})
        print(f"  {path.name:<26} {w}x{h:<6} 섹션 {len(sections):>3}  "
              f"강제 {len(forced):>2}  최대 {max(heights):>5}px")

    meta = {
        "variant": name, "cfg": cfg, "source": "data/golden_sample",
        "images": len(paths),
        "total_sections": sum(p["sections"] for p in per_image),
        "total_forced": sum(p["forced"] for p in per_image),
        "max_section_height": max(p["max_height"] for p in per_image),
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image, "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 섹션 {meta['total_sections']} (강제 {meta['total_forced']}), "
          f"{meta['total_sec']}s\n")


def images(names: list[str] | None) -> list[Path]:
    if names:
        return [p for p in SRC.rglob("*.jpg") if p.name in names]
    return sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    paths = images(args.images)
    if not paths:
        raise SystemExit(f"{SRC} 에 이미지 없음")
    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, paths)


if __name__ == "__main__":
    main()
