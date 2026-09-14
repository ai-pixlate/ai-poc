"""누끼 — 요소 선별 `rule_comp` (`.venv-g`에서 실행).

재배치 대상 (2026-09-14 결정)
    남김   사람 · 제품 · 사진류(피부 전후 · 원료 · 제형 · 현미경)
    버림   그래픽(말풍선 · 배지 · 차트 · 아이콘 · 패널 · 선) · 도식 · 문서 이미지 · 지운 자국

입력 — `birefnet_erased_s50` 누끼 마스크 + s50 글자 지운 섹션.

방식 — 마스크를 덩어리(연결 요소)로 쪼개고 **질감**으로 거름. 사진 속 사람·제품·피부는
화소마다 밝기가 조금씩 다르고, 그래픽·패널·LaMa 지운 자국은 평평하거나 매끈하다.

덩어리 특징 (덩어리 안쪽을 3px 깎아 윤곽선 영향 제거)
    textured   5×5 국소 표준편차 ≥ TEX_STD 인 화소 비율
    colors     32단계 양자화 색 중 덩어리의 0.5% 이상을 차지하는 색 수

남김 조건 — textured ≥ MIN_TEXTURED **그리고** colors ≥ MIN_COLORS. 면적 MIN_AREA 미만은 버림.
덩어리가 하나도 안 남으면 그 섹션은 **요소 없음**.

⚠️ 한계 — 덩어리 단위라 **사람·제품에 붙은 그래픽은 못 떼어냄.** 문서 이미지는 글줄 때문에 질감이 높아 남을 수 있음.

출력
    results/rule_comp/mask/{section}.png   남긴 덩어리만
    results/rule_comp/rgba/{section}.png
    results/rule_comp/features.json        덩어리별 특징 · 남김 여부
    results/rule_comp/vis/{section}.jpg    s50 누끼 | 덩어리 번호(초록 남김 · 빨강 버림) | 선별 결과
    results/rule_comp/meta.json

사용법
    python run_rule.py
    python run_rule.py --sections A000000213548_018_003 A000000213548_002_001
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SRC_MASK = RESULTS / "birefnet_erased_s50" / "mask"
SRC_IMG = RESULTS / "_erase_s50" / "erased"
OUT = RESULTS / "rule_comp"

MIN_AREA = 0.003      # 섹션 면적 대비
ERODE = 3
TEX_STD = 4.0         # 국소 표준편차(0~255 밝기)
# 기준값은 결과가 뻔한 16섹션에서 잡음(과적합 주의) —
#   남길 것(사람·제품·잎·피부 사진·크림) 색 수 22~62 · 질감 0.05~0.28
#   버릴 것(말풍선·지운 자국·차트·도식·논문 이미지) 색 수 1~19 · 질감 0.00~0.71
# 질감만으로는 논문 이미지(0.71)가 사람(0.27)보다 높아 못 거름 → 색 수가 주 기준
MIN_TEXTURED = 0.03
MIN_COLORS = 20
PANEL_H = 700

# rule_flat — 덩어리로 쪼개기 전에 **넓고 평평한 영역**(흰 카드 · 빈 박스 · 배지 바탕 · 지운 자국)을 깎는다.
# rule_comp 판정에서 그래픽 잔존 27섹션 중 21섹션이 사람·제품과 한 덩어리였고,
# 대상 누락 10섹션 중 5섹션이 흰 패널과 한 덩어리라 색 수가 낮게 셈해져 버려졌다.
#
# v1(범위 6 · 모양 조건 없음) 시험 19섹션 — 흰 카드·빈 박스·표 칸은 깎였으나 **매끈한 피부(볼·목·이마)와
# 무지 튜브 몸통·흰 옷까지 깎아 구멍이 남**(250199_014_001 · 250199_007_001 · 213548_002_001 · 219554_002_023).
# 깎아야 할 것은 거의 완전히 평평하고 **사각형·원처럼 반듯**하며, 피부·튜브의 매끈한 부분은 모양이 불규칙함 →
# v2는 범위를 좁히고 **최소 외접 사각형 채움률**을 조건으로 더함.
FLAT_WIN = 9          # 이 창 안의 채널별 (최대 − 최소)
FLAT_RANGE = 3        # 이하면 평평한 화소 (v1: 6)
FLAT_MIN_AREA = 0.005 # 평평한 화소 뭉치가 섹션 면적의 이 비율 이상이어야 깎음
FLAT_RECT = 0.70      # 뭉치 면적 ÷ 최소 외접 사각형 면적 — 이 이상(반듯한 모양)만 깎음 (v1: 조건 없음)
OPEN_K = 5            # 깎은 뒤 가는 다리(지시선 등)를 끊는 열림 연산 크기
CARVE_DILATE = 5      # 깎는 영역을 이만큼 넓힘 — v2 시험에서 빈 박스의 얇은 테두리선이 남았음

VARIANTS = {"rule_comp": {"flat": False}, "rule_flat": {"flat": True}}


def read(p: Path, flag=cv2.IMREAD_COLOR) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def features(img: np.ndarray, comp: np.ndarray, local_std: np.ndarray) -> dict:
    inner = cv2.erode(comp.astype(np.uint8), np.ones((2 * ERODE + 1, 2 * ERODE + 1), np.uint8)) > 0
    if inner.sum() < 50:
        inner = comp
    n = int(inner.sum())
    textured = float((local_std[inner] >= TEX_STD).mean())
    q = (img[inner] // 8).astype(np.int32)
    keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    _, counts = np.unique(keys, return_counts=True)
    colors = int((counts >= max(1, 0.005 * n)).sum())
    return {"textured": round(textured, 3), "colors": colors}


def checker(h: int, w: int, size: int = 16) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    return np.where((((yy // size) + (xx // size)) % 2)[..., None], 205, 245).astype(np.uint8).repeat(3, axis=2)


def on_checker(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    a = mask[..., None].astype(np.float32)
    return (img * a + checker(*mask.shape) * (1 - a)).astype(np.uint8)


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def flat_regions(img: np.ndarray, fg: np.ndarray) -> np.ndarray:
    """전경 안의 넓고 평평한 영역 마스크."""
    k = np.ones((FLAT_WIN, FLAT_WIN), np.uint8)
    rng = np.max(cv2.dilate(img, k) - cv2.erode(img, k), axis=2)
    flat = (rng <= FLAT_RANGE) & fg
    n, labels, stats, _ = cv2.connectedComponentsWithStats(flat.astype(np.uint8))
    carve = np.zeros(n, bool)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < FLAT_MIN_AREA * fg.size:
            continue
        ys, xs = np.nonzero(labels == i)
        (_, _), (rw, rh), _ = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
        carve[i] = rw * rh > 0 and area / (rw * rh) >= FLAT_RECT
    return carve[labels]


def run_section(name: str, flat: bool) -> dict:
    img = read(SRC_IMG / f"{name}.png")
    alpha = read(SRC_MASK / f"{name}.png", cv2.IMREAD_GRAYSCALE)
    fg0 = alpha > 127
    h, w = fg0.shape
    carved = np.zeros_like(fg0)
    fg = fg0
    if flat:
        carved = flat_regions(img, fg0)
        k = 2 * CARVE_DILATE + 1
        carved = cv2.dilate(carved.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool) & fg0
        fg = fg0 & ~carved
        fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((OPEN_K, OPEN_K), np.uint8)) > 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.blur(gray, (5, 5))
    local_std = np.sqrt(np.maximum(cv2.blur(gray * gray, (5, 5)) - mean * mean, 0))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8))
    comps, keep_mask = [], np.zeros_like(fg)
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < MIN_AREA * h * w:
            continue
        comp = labels == i
        f = features(img, comp, local_std)
        keep = f["textured"] >= MIN_TEXTURED and f["colors"] >= MIN_COLORS
        x, y, bw, bh = (int(stats[i, k]) for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        comps.append({"id": len(comps) + 1, "bbox": [x, y, x + bw, y + bh], "area_pct": round(area / (h * w) * 100, 2),
                      **f, "keep": keep})
        if keep:
            keep_mask |= comp
    out_alpha = np.where(keep_mask, alpha, 0).astype(np.uint8)
    cv2.imwrite(str(OUT / "mask" / f"{name}.png"), out_alpha)
    cv2.imwrite(str(OUT / "rgba" / f"{name}.png"), np.dstack([img, out_alpha]))

    # 대지 — s50 누끼 | 덩어리 번호 | 선별 결과
    p1 = on_checker(img, alpha / 255.0)
    p2 = p1.copy()
    if flat:
        p2[carved] = (p2[carved] * 0.4 + np.array([60, 60, 255]) * 0.6).astype(np.uint8)
    for c in comps:
        x0, y0, x1, y1 = c["bbox"]
        color = (40, 170, 40) if c["keep"] else (40, 40, 220)
        cv2.rectangle(p2, (x0, y0), (x1, y1), color, max(2, w // 250))
    p3 = on_checker(img, out_alpha / 255.0)
    r = PANEL_H / h
    ps = [cv2.resize(p, (max(1, int(w * r)), PANEL_H)) for p in (p1, p2, p3)]
    pil = Image.fromarray(cv2.cvtColor(ps[1], cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    font = _font(15)
    for c in comps:
        x0, y0 = int(c["bbox"][0] * r), int(c["bbox"][1] * r)
        d.text((x0 + 3, y0 + 2), f"{c['id']} t{c['textured']:.2f} c{c['colors']}",
               fill=(0, 140, 0) if c["keep"] else (220, 0, 0), font=font)
    ps[1] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    gap = np.full((PANEL_H, 14, 3), 40, np.uint8)
    head = np.full((28, sum(p.shape[1] for p in ps) + 28, 3), 255, np.uint8)
    sheet = np.vstack([head, np.hstack([ps[0], gap, ps[1], gap, ps[2]])])
    hp = Image.fromarray(cv2.cvtColor(sheet, cv2.COLOR_BGR2RGB))
    label2 = "2. 평평한 영역 깎음(붉은 칠) + 덩어리" if flat else "2. 덩어리"
    ImageDraw.Draw(hp).text((4, 4), f"{name}   1. s50 누끼 | {label2} (초록 남김 · 빨강 버림, t=질감비율 c=색수) | "
                                    f"3. {'rule_flat' if flat else 'rule_comp'} 선별", fill=(200, 0, 0), font=_font(16))
    cv2.imwrite(str(OUT / "vis" / f"{name}.jpg"), cv2.cvtColor(np.array(hp), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])

    kept = sum(c["keep"] for c in comps)
    return {"section": name, "components": len(comps), "kept": kept, "dropped": len(comps) - kept,
            "no_element": kept == 0, "carved_pct": round(float(carved.sum() / max(1, fg0.sum()) * 100), 1),
            "comps": comps}


def main() -> None:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="rule_comp", choices=list(VARIANTS))
    ap.add_argument("--sections", nargs="*", default=None)
    args = ap.parse_args()
    flat = VARIANTS[args.variant]["flat"]
    OUT = RESULTS / args.variant
    for sub in ("mask", "rgba", "vis"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    names = args.sections or sorted(p.stem for p in SRC_MASK.glob("*.png"))
    t0 = time.perf_counter()
    rows = []
    for name in names:
        row = run_section(name, flat)
        rows.append(row)
        print(f"  {name:<24} 깎음 {row['carved_pct']:>5}%  덩어리 {row['components']:>2}  남김 {row['kept']:>2}  "
              + "  ".join(f"{c['id']}:{'O' if c['keep'] else 'x'} t{c['textured']:.2f} c{c['colors']} a{c['area_pct']}"
                          for c in row["comps"]), flush=True)
    (OUT / "features.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"variant": args.variant, "min_area": MIN_AREA, "erode": ERODE, "tex_std": TEX_STD,
            **({"flat_win": FLAT_WIN, "flat_range": FLAT_RANGE, "flat_min_area": FLAT_MIN_AREA,
                "flat_rect": FLAT_RECT, "open_k": OPEN_K, "carve_dilate": CARVE_DILATE} if flat else {}),
            "min_textured": MIN_TEXTURED, "min_colors": MIN_COLORS, "sections": len(rows),
            "components": sum(r["components"] for r in rows), "kept": sum(r["kept"] for r in rows),
            "no_element": sum(r["no_element"] for r in rows),
            "sec_per_section": round((time.perf_counter() - t0) / max(1, len(rows)), 3),
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not args.sections:
        (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{args.variant}] 섹션 {meta['sections']} · 덩어리 {meta['components']} · 남김 {meta['kept']} · 요소 없음 {meta['no_element']}")


if __name__ == "__main__":
    main()
