"""누끼 — SAM 2 조각 생성 (`.venv-sam`에서 실행 · 로컬 GPU).

`vlm_pick`은 대상 누락을 2/57로 줄였으나 그래픽 잔존 28이 남았다. 대부분 **대상과 한 덩어리로 붙은
그래픽**(인물 옆 아이콘 · 튜브에 붙은 배지 · 사진에 붙은 빈 박스)이라 덩어리 단위 선택으로는 못 뗀다.
SAM 2 자동 분할로 누끼 전경을 **물체 단위 조각**으로 쪼갠다. 조각 선택은 run_vlm_pick.py --variant sam_pick.

조각 만들기
    ① SAM 2 자동 분할 — 긴 섹션은 정사각형에 가까운 띠(겹침)로 나눠 돌림(모델 입력이 1024px라 작은 그래픽이 뭉개짐)
    ② 누끼 전경(`birefnet_erased_s50`) 안에 PART_INSIDE 이상 든 마스크만 씀
    ③ **큰 마스크부터** 전경 화소를 차지 — 사람 전체가 먼저 한 조각이 되고, 그 안의 눈·입 같은 하위 마스크는
       새로 차지할 화소가 없어 조각이 안 됨. 인물 밖에 붙은 아이콘은 별도 조각이 됨
    ④ **담는 틀 풀기** — 작은 마스크가 한 조각 안에 들어 있고 그 조각의 나머지가 평평하면(흰 카드·패널)
       작은 마스크를 별도 조각으로 뗌. 카드 안 미니 튜브가 카드와 한 조각이 되는 문제 대응
    ⑤ 어느 마스크에도 안 든 전경 화소는 연결 요소로 묶어 조각(PART_MIN 이상), 작으면 옆 조각에 붙임

출력
    results/sam_parts/labels/{section}.png   조각 번호 지도(16bit, 0 = 배경)
    results/sam_parts/parts.json             섹션별 조각 수 · SAM 마스크 수 · 소요
    results/sam_parts/vis/{section}.jpg      조각 색칠

사용법
    python run_sam_parts.py                      # 기본 표본 40섹션
    python run_sam_parts.py --sections A000000213548_002_001
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SRC_MASK = RESULTS / "birefnet_erased_s50" / "mask"
SRC_IMG = RESULTS / "_erase_s50" / "erased"
OUT = RESULTS / "sam_parts"
SUMMARY = HERE / "summary.md"

CKPT = Path(os.path.expanduser("~/.cache/sam2/sam2.1_hiera_small.pt"))
CONFIG = "configs/sam2.1/sam2.1_hiera_s.yaml"

TILE_RATIO = 1.3      # 띠 높이 = 폭 × 이 값
TILE_OVERLAP = 0.2    # 띠 겹침(띠 높이 대비)
PART_INSIDE = 0.6     # SAM 마스크가 누끼 전경 안에 드는 비율 하한
PART_MIN = 0.001      # 조각 최소 면적(섹션 대비)
MAX_PARTS = 40        # 섹션당 조각 상한 — 넘으면 작은 조각부터 옆 조각에 붙임
# 담는 틀 풀기 — 시험 2섹션에서 흰 구성 카드가 안의 미니 튜브까지 한 조각으로 삼킴(큰 마스크부터 차지하기 때문).
# 작은 마스크가 한 조각 안에 CARVE_INSIDE 이상 들어 있고, 그 조각에서 작은 마스크를 뺀 나머지가 평평하면
# 틀(카드·패널)로 보고 작은 마스크를 별도 조각으로 뗌. 얼굴처럼 명암이 있는 조각은 안 뗌.
# 평평함 = 나머지 화소 중 중앙값 ±FLAT_TOL 안에 드는 비율 ≥ FLAT_FRAC.
#   표준편차(<10)로 재면 카드 속 `+` 아이콘·검은 점 몇 개에도 크게 흔들려 틀로 못 봄(시험 2회차).
CARVE_INSIDE = 0.9
CARVE_MAX = 0.5       # 작은 마스크가 조각 면적의 이 비율 미만일 때만
FLAT_TOL = 12.0
FLAT_FRAC = 0.85

# 대조군 — vlm_pick에서 그래픽 잔존·대상 누락이 모두 없던 섹션(과분할로 구멍이 나는지 확인)
CONTROL = ["A000000213548_001_001", "A000000213548_014_002", "A000000219554_002_009", "A000000219554_002_017",
           "A000000219554_002_022", "A000000250199_007_002", "A000000250199_008_001", "A000000250199_009_007",
           "A000000250199_010_002", "A000000250199_014_001"]


def default_sections() -> list[str]:
    """summary.md 7장(vlm_pick) 판정표에서 그래픽 잔존 O · 대상 누락 O 섹션 + 대조군."""
    picked = []
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("| `A0") and len(c) == 9 and (c[6] == "O" or c[7] == "O"):
            picked.append(c[0].strip("`"))
    return sorted(set(picked) | set(CONTROL))


def read(p: Path, flag=cv2.IMREAD_COLOR) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def sam_masks(gen, rgb: np.ndarray) -> list[np.ndarray]:
    h, w = rgb.shape[:2]
    th = int(w * TILE_RATIO)
    if h <= th:
        return [m["segmentation"] for m in gen.generate(rgb)]
    step = int(th * (1 - TILE_OVERLAP))
    out = []
    for top in range(0, h, step):
        bottom = min(h, top + th)
        for m in gen.generate(rgb[top:bottom]):
            full = np.zeros((h, w), bool)
            full[top:bottom] = m["segmentation"]
            out.append(full)
        if bottom == h:
            break
    return out


def build_parts(masks: list[np.ndarray], fg: np.ndarray, gray: np.ndarray) -> np.ndarray:
    h, w = fg.shape
    min_px = PART_MIN * h * w
    labels = np.zeros((h, w), np.int32)
    nxt = 1
    usable = [m for m in masks if m.sum() and (m & fg).sum() / m.sum() >= PART_INSIDE]
    for m in sorted(usable, key=lambda m: -int(m.sum())):
        new = m & fg & (labels == 0)
        if new.sum() < min_px:
            continue
        labels[new] = nxt
        nxt += 1
    # 담는 틀 풀기 — 작은 마스크부터
    for m in sorted(usable, key=lambda m: int(m.sum())):
        mf = m & fg
        n_mf = int(mf.sum())
        if n_mf < min_px:
            continue
        ids, counts = np.unique(labels[mf], return_counts=True)
        p = int(ids[np.argmax(counts)])
        if p == 0 or counts.max() < CARVE_INSIDE * n_mf:
            continue
        part = labels == p
        if n_mf >= CARVE_MAX * part.sum():
            continue
        rest = part & ~m
        if rest.sum() < min_px:
            continue
        vals = gray[rest]
        flat = float((np.abs(vals - np.median(vals)) <= FLAT_TOL).mean())
        if os.environ.get("SAM_DEBUG"):
            ys, xs = np.nonzero(mf)
            print(f"    후보 조각{p} 마스크 {n_mf}px bbox({xs.min()},{ys.min()})-({xs.max()},{ys.max()}) "
                  f"조각 {int(part.sum())}px 평평 {flat:.2f}")
        if flat < FLAT_FRAC:
            continue
        labels[mf & part] = nxt
        nxt += 1
    # 남은 전경 — 연결 요소로 조각, 작으면 이웃 조각에 붙임
    rest = fg & (labels == 0)
    n, cc, stats, _ = cv2.connectedComponentsWithStats(rest.astype(np.uint8))
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_px:
            labels[cc == i] = nxt
            nxt += 1
    labels = absorb_small(labels, fg, min_px)
    return relabel(labels)


def absorb_small(labels: np.ndarray, fg: np.ndarray, min_px: float) -> np.ndarray:
    """번호 없는 전경 화소와 너무 작은 조각을 이웃 조각에 붙임. 조각이 MAX_PARTS를 넘으면 작은 것부터 붙임."""
    k = np.ones((3, 3), np.uint8)
    for _ in range(3):
        ids, counts = np.unique(labels[labels > 0], return_counts=True)
        order = sorted(zip(counts, ids))
        drop = [i for c, i in order if c < min_px]
        if len(ids) - len(drop) > MAX_PARTS:
            drop += [i for c, i in order if i not in drop][: len(ids) - len(drop) - MAX_PARTS]
        for i in drop:
            labels[labels == i] = 0
        hole = fg & (labels == 0)
        for _ in range(50):
            if not hole.any():
                break
            grown = cv2.dilate(labels.astype(np.float32), k).astype(np.int32)
            fill = hole & (grown > 0)
            labels[fill] = grown[fill]
            hole = fg & (labels == 0)
        if not drop:
            break
    return labels


def relabel(labels: np.ndarray) -> np.ndarray:
    """위→아래, 왼→오 순으로 1부터 다시 번호."""
    ids = [i for i in np.unique(labels) if i > 0]
    pos = []
    for i in ids:
        ys, xs = np.nonzero(labels == i)
        pos.append((int(ys.min()) // 40, int(xs.min()), i))
    out = np.zeros_like(labels)
    for new, (_, _, i) in enumerate(sorted(pos), 1):
        out[labels == i] = new
    return out


def colorize(img: np.ndarray, labels: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(7)
    lut = rng.integers(40, 255, (int(labels.max()) + 1, 3), dtype=np.uint8)
    lut[0] = 0
    color = lut[labels]
    out = img.copy()
    m = labels > 0
    out[m] = (img[m] * 0.4 + color[m] * 0.6).astype(np.uint8)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", nargs="*", default=None)
    args = ap.parse_args()
    names = args.sections or default_sections()

    import torch
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    from sam2.build_sam import build_sam2

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam2(CONFIG, str(CKPT), device=device, apply_postprocessing=False)
    gen = SAM2AutomaticMaskGenerator(model, points_per_side=32, pred_iou_thresh=0.8, stability_score_thresh=0.9)

    for sub in ("labels", "vis"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    parts_path = OUT / "parts.json"
    report = json.loads(parts_path.read_text(encoding="utf-8")) if parts_path.exists() else {}
    for name in names:
        img = read(SRC_IMG / f"{name}.png")
        fg = read(SRC_MASK / f"{name}.png", cv2.IMREAD_GRAYSCALE) > 127
        t0 = time.perf_counter()
        with torch.inference_mode(), torch.autocast(device, dtype=torch.bfloat16, enabled=device == "cuda"):
            masks = sam_masks(gen, cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        labels = build_parts(masks, fg, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32))
        sec = round(time.perf_counter() - t0, 2)
        cv2.imwrite(str(OUT / "labels" / f"{name}.png"), labels.astype(np.uint16))
        cv2.imwrite(str(OUT / "vis" / f"{name}.jpg"), colorize(img, labels), [cv2.IMWRITE_JPEG_QUALITY, 85])
        report[name] = {"sam_masks": len(masks), "parts": int(labels.max()), "sec": sec, "device": device}
        print(f"  {name:<24} SAM 마스크 {len(masks):>4}  조각 {int(labels.max()):>3}  {sec}s", flush=True)
    parts_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[sam_parts] 섹션 {len(names)} · 조각 {sum(report[n]['parts'] for n in names)}")


if __name__ == "__main__":
    main()
