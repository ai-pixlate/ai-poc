"""섹션 분해 — 배경색 전환 기반 (color_snap).

한국형 상세페이지는 **섹션마다 배경색을 갈아끼운다.** 그 전환을 주 신호로 삼고
여백으로 경계를 다듬는다. 단독 규칙이 아니라 세 단계를 겹친다.

    ① 행 단위 **지배 배경색** 추출 → 색 변화 지점 검출
    ② 변화 지점을 **가장 가까운 여백**으로 스냅. 여백이 없으면 뚜렷한 색 경계선으로.
       둘 다 없으면 **자르지 않고** `확인 필요`로 남긴다 — 사진 배경 섹션에서 억지로
       자르면 글자를 관통한다
    ③ 색이 안 바뀌는 긴 구간은 보조 분해
         후보 1  여백으로 잘게 자른 뒤 인접 조각 병합     ← 이 파일 (`color_snap_ws`)
         후보 4  VLM이 내용을 보고 경계 판단            ← run_color_vlm.py

지배색은 행의 **최빈색**이다. 평균색은 글자·사진에 끌려 배경을 못 잡는다.

출력 (review.py가 그대로 읽는 형식)
    results/{variant}/sections/{stem}.json   섹션·top_offset·절단 출처
    results/{variant}/crops/{stem}/{i}.jpg
    results/{variant}/vis/{stem}.jpg         빨강 색전환 · 파랑 보조 · 주황 스냅 실패
    results/{variant}/plan/{stem}.json       ①② 결과와 보조 분해 대상 구간 — VLM 단계 입력
    results/{variant}/meta.json

사용법
    python run_color.py
    python run_color.py --images A000000219554_002.jpg
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
VARIANT = "color_snap_ws"

# ① 지배 배경색
Q = 16             # 채널 양자화 단계 — 미세한 노이즈를 한 색으로 묶는다
MIN_SHARE = 0.55   # 행에서 최빈색이 이 비율 이상이어야 '배경색이 있는 행'
MIN_RUN = 60       # 같은 배경색이 이만큼 이어져야 배경 구간 (px)
DELTA = 40         # 인접 배경 구간의 색 차이가 이 이상이면 색 변화 (채널 최대차)
WIDE_GAP = 200     # 두 배경 구간 사이가 이보다 넓으면 사이에 사진이 끼어 있다고 본다

# ② 스냅
BLANK_TOL = 6.0    # 행 밝기 표준편차가 이 이하면 여백 행
BLANK_GAP = 40     # 여백 행이 이만큼 이어져야 여백 구간
SNAP = 300         # 변화 지점에서 이 거리 안의 여백으로 스냅 (px)
EDGE_JUMP = 25     # 여백이 없을 때 인정할 행 평균색 급변의 크기
EDGE_WIN = 40      # 급변을 찾는 범위 (px)

# ③ 보조 분해 — 후보 1 (여백 + 병합)
AUX_LEN = 3000     # 색 변화 없이 이보다 긴 구간만 보조 분해한다
MIN_PIECE = 1200   # 이보다 짧은 조각은 이웃과 병합
MERGE_DELTA = 20   # 인접 조각의 배경색 차이가 이 미만이면 병합
MAX_MERGED = 3000  # 병합해도 이 길이는 넘기지 않는다
MIN_SECTION = 400  # 최종 섹션 최소 길이


# ---------------------------------------------------------------- ① 지배색

def dominant_rows(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """행마다 최빈 양자화 색과 그 비율."""
    h, w, _ = rgb.shape
    q = (rgb // Q).astype(np.int32)
    key = q[..., 0] * Q * Q + q[..., 1] * Q + q[..., 2]
    cols = np.empty(h, np.int32)
    share = np.empty(h)
    for y in range(h):
        v, c = np.unique(key[y], return_counts=True)
        i = c.argmax()
        cols[y], share[y] = v[i], c[i] / w
    return cols, share


def key_rgb(k: int) -> np.ndarray:
    return np.array([k // (Q * Q), (k // Q) % Q, k % Q]) * Q + Q // 2


def bg_runs(cols: np.ndarray, share: np.ndarray) -> list[tuple[int, int, int]]:
    """같은 지배색이 MIN_RUN 이상 이어지는 구간. 배경색이 불분명한 행(사진)에서 끊는다."""
    runs, s = [], None
    for y in range(len(cols) + 1):
        ok = y < len(cols) and share[y] >= MIN_SHARE
        if s is not None and (not ok or cols[y] != cols[s]):
            if y - s >= MIN_RUN:
                runs.append((s, y, int(cols[s])))
            s = None
        if ok and s is None:
            s = y
    return runs


def color_changes(runs: list[tuple[int, int, int]]) -> list[dict]:
    """인접 배경 구간끼리 색이 크게 다른 곳.

    사이가 넓으면 사진이 끼어 있다는 뜻이라 가운데가 아니라 **양 가장자리**를
    후보로 삼는다. 가운데를 자르면 사진 위 글자를 관통한다.
    """
    out = []
    for (s1, e1, c1), (s2, e2, c2) in zip(runs, runs[1:]):
        d = int(np.abs(key_rgb(c1) - key_rgb(c2)).max())
        if d < DELTA:
            continue
        if s2 - e1 > WIDE_GAP:
            out.append({"y": e1, "delta": d, "kind": "사진 위쪽 가장자리"})
            out.append({"y": s2, "delta": d, "kind": "사진 아래쪽 가장자리"})
        else:
            out.append({"y": (e1 + s2) // 2, "delta": d, "kind": "색 전환"})
    return out


# ---------------------------------------------------------------- ② 스냅

def blank_centers(gray: np.ndarray) -> list[tuple[int, int]]:
    std = gray.std(axis=1)
    b = std <= BLANK_TOL
    out, s = [], None
    for y, x in enumerate(b):
        if x and s is None:
            s = y
        elif not x and s is not None:
            if y - s >= BLANK_GAP:
                out.append((s, y))
            s = None
    return out


def snap(y: int, blanks: list[tuple[int, int]], jump: np.ndarray, h: int) -> tuple[int | None, str]:
    """변화 지점을 실제로 자를 자리로 옮긴다. 못 찾으면 None."""
    best = None
    for a, b in blanks:
        c = (a + b) // 2
        d = abs(c - y)
        if d <= SNAP and (best is None or d < abs(best - y)):
            best = c
    if best is not None:
        return best, "여백"
    lo, hi = max(0, y - EDGE_WIN), min(h - 1, y + EDGE_WIN)
    if hi > lo and jump[lo:hi].max() >= EDGE_JUMP:
        return lo + int(jump[lo:hi].argmax()) + 1, "경계선"
    return None, "실패"


# ---------------------------------------------------------------- ③ 후보 1

def aux_ws_merge(y0: int, y1: int, blanks: list[tuple[int, int]],
                 cols: np.ndarray) -> list[int]:
    """긴 구간을 여백에서 잘게 자른 뒤 인접 조각을 병합한다."""
    cuts = [(a + b) // 2 for a, b in blanks if y0 < (a + b) // 2 < y1]
    bounds = [y0] + cuts + [y1]
    pieces = [[a, b] for a, b in zip(bounds, bounds[1:])]

    def bg(a: int, b: int) -> np.ndarray:
        seg = cols[a:b]
        v, c = np.unique(seg, return_counts=True)
        return key_rgb(int(v[c.argmax()]))

    merged = [pieces[0]] if pieces else []
    for p in pieces[1:]:
        cur = merged[-1]
        short = (cur[1] - cur[0]) < MIN_PIECE or (p[1] - p[0]) < MIN_PIECE
        similar = np.abs(bg(*cur) - bg(*p)).max() < MERGE_DELTA
        fits = p[1] - cur[0] <= MAX_MERGED
        if (short or similar) and fits:
            cur[1] = p[1]
        else:
            merged.append(p)
    return [m[0] for m in merged[1:]]


# ---------------------------------------------------------------- 실행

def visualize(img: Image.Image, cuts: dict[int, str], failed: list[int], out: Path) -> None:
    w, h = img.size
    scale = 240 / w
    arr = np.array(img.resize((240, max(1, int(h * scale))), Image.BILINEAR).convert("RGB"))
    color = {"color": (220, 30, 30), "aux_ws": (40, 110, 230)}
    for y, src in cuts.items():
        yy = int(y * scale)
        if 0 <= yy < arr.shape[0]:
            arr[max(0, yy - 1):yy + 2, :] = color.get(src, (0, 0, 0))
    for y in failed:
        yy = int(y * scale)
        if 0 <= yy < arr.shape[0]:
            arr[yy, ::6] = (255, 150, 0)      # 점선 — 자르지 않았음
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out, quality=90)


def process(path: Path, out_dir: Path) -> dict:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    rgb = np.array(img)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    jump = np.abs(np.diff(rgb.astype(np.int16).mean(axis=1), axis=0)).max(axis=1)

    cols, share = dominant_rows(rgb)
    runs = bg_runs(cols, share)
    changes = color_changes(runs)
    blanks = blank_centers(gray)

    # ② 스냅
    cuts: dict[int, str] = {}
    snaps, failed = [], []
    for ch in changes:
        y, how = snap(ch["y"], blanks, jump, h)
        snaps.append({**ch, "snapped": y, "how": how})
        if y is None:
            failed.append(ch["y"])
        elif MIN_SECTION <= y <= h - MIN_SECTION:
            cuts[y] = "color"

    # 너무 가까운 절단은 하나만 남긴다
    kept: dict[int, str] = {}
    for y in sorted(cuts):
        if not kept or y - max(kept) >= MIN_SECTION:
            kept[y] = cuts[y]
    cuts = kept

    # ③ 색 변화 없이 긴 구간 — 보조 분해 대상
    bounds = [0] + sorted(cuts) + [h]
    aux_targets = [[a, b] for a, b in zip(bounds, bounds[1:]) if b - a > AUX_LEN]
    for a, b in aux_targets:
        for y in aux_ws_merge(a, b, blanks, cols):
            if all(abs(y - c) >= MIN_SECTION for c in cuts) and \
               MIN_SECTION <= y - a and b - y >= MIN_SECTION:
                cuts[y] = "aux_ws"

    # 섹션 기록
    bounds = [0] + sorted(cuts) + [h]
    crop_dir = out_dir / "crops" / path.stem
    crop_dir.mkdir(parents=True, exist_ok=True)
    sections = []
    for i, (y0, y1) in enumerate(zip(bounds, bounds[1:]), 1):
        img.crop((0, y0, w, y1)).save(crop_dir / f"{i:03d}.jpg", quality=92)
        sections.append({
            "index": i, "top_offset": y0, "range": [y0, y1], "height": y1 - y0,
            "cut_source": "시작" if y0 == 0 else cuts[y0],
            "forced": False,
            "crop": f"crops/{path.stem}/{i:03d}.jpg",
        })

    (out_dir / "sections").mkdir(parents=True, exist_ok=True)
    (out_dir / "sections" / f"{path.stem}.json").write_text(
        json.dumps({"image": path.name, "variant": VARIANT, "size": [w, h],
                    "cuts": sorted(cuts), "cut_sources": {str(k): v for k, v in cuts.items()},
                    "snap_failed": failed, "forced_cuts": [], "sections": sections},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (out_dir / "plan").mkdir(parents=True, exist_ok=True)
    color_cuts = sorted(y for y, s in cuts.items() if s == "color")
    (out_dir / "plan" / f"{path.stem}.json").write_text(
        json.dumps({"image": path.name, "size": [w, h], "changes": snaps,
                    "color_cuts": color_cuts, "snap_failed": failed,
                    "aux_targets": aux_targets},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    visualize(img, cuts, failed, out_dir / "vis" / f"{path.stem}.jpg")

    return {
        "image": path.name, "size": [w, h], "sections": len(sections),
        "color_changes": len(changes),
        "snap_blank": sum(1 for s in snaps if s["how"] == "여백"),
        "snap_edge": sum(1 for s in snaps if s["how"] == "경계선"),
        "snap_failed": len(failed),
        "aux_targets": len(aux_targets),
        "aux_cuts": sum(1 for s in cuts.values() if s == "aux_ws"),
        "max_height": max(s["height"] for s in sections),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    paths = ([p for p in SRC.rglob("*.jpg") if p.name in args.images] if args.images
             else sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name)))
    out_dir = RESULTS / VARIANT

    print(f"[{VARIANT}]")
    t0 = time.perf_counter()
    per = []
    for p in paths:
        r = process(p, out_dir)
        per.append(r)
        print(f"  {r['image']:<26} {r['size'][0]}x{r['size'][1]:<6} 섹션 {r['sections']:>3}  "
              f"색변화 {r['color_changes']:>2} (여백 {r['snap_blank']} · 경계선 {r['snap_edge']} · "
              f"실패 {r['snap_failed']})  보조 {r['aux_targets']}구간→{r['aux_cuts']}절단")

    meta = {
        "variant": VARIANT,
        "cfg": {"Q": Q, "min_share": MIN_SHARE, "min_run": MIN_RUN, "delta": DELTA,
                "wide_gap": WIDE_GAP, "snap": SNAP, "edge_jump": EDGE_JUMP,
                "aux_len": AUX_LEN, "min_piece": MIN_PIECE, "merge_delta": MERGE_DELTA,
                "max_merged": MAX_MERGED, "min_section": MIN_SECTION},
        "images": len(per),
        "total_sections": sum(r["sections"] for r in per),
        "total_forced": 0,
        "color_changes": sum(r["color_changes"] for r in per),
        "snap_blank": sum(r["snap_blank"] for r in per),
        "snap_edge": sum(r["snap_edge"] for r in per),
        "snap_failed": sum(r["snap_failed"] for r in per),
        "aux_targets": sum(r["aux_targets"] for r in per),
        "aux_cuts": sum(r["aux_cuts"] for r in per),
        "max_section_height": max(r["max_height"] for r in per),
        "total_sec": round(time.perf_counter() - t0, 2),
        "per_image": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"[{VARIANT}] 완료 — 섹션 {meta['total_sections']} · 색변화 {meta['color_changes']} "
          f"(여백 {meta['snap_blank']} · 경계선 {meta['snap_edge']} · 실패 {meta['snap_failed']}) · "
          f"보조 {meta['aux_targets']}구간 → {meta['aux_cuts']}절단 · {meta['total_sec']}s")


if __name__ == "__main__":
    main()
