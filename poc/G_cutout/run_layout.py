"""누끼 — 재배치 요소 분리 실행기 (`.venv-g`에서 실행).

목적 정정(2026-09-14) — 누끼는 **세로 상세페이지를 가로로 재배치**하기 위한 요소 분리다.
대상은 제품만이 아니라 **사람도 포함**. 페이지 글자는 조판으로 다시 그리므로 요소에서 빠져야 한다.

이번 비교 — **원본 섹션 vs 글자 지운 섹션**을 같은 배경제거 모델에 넣어,
글자 파편이 전경에서 사라지는지 본다. 입력 준비는 prep_erase.py.

variant
    birefnet_raw      섹션 원본 → `birefnet-general`
    birefnet_erased   글자 지운 섹션(LaMa) → `birefnet-general`

⚠️ rembg는 입력을 1024×1024로 줄여 추론한다. 세로로 긴 섹션은 세로가 더 많이 눌린다 — 두 variant 공통 조건.

출력
    results/{variant}/rgba/{section}.png   투명 PNG
    results/{variant}/mask/{section}.png   마스크
    results/{variant}/meta.json            섹션별 소요 · 전경 비율 · 덩어리 수

사용법
    python run_layout.py --variant all
    python run_layout.py --variant birefnet_raw --limit 3
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SECTIONS = ROOT / "poc" / "section_split" / "results" / "color_snap_vlm2"
ERASED = HERE / "results" / "_erase" / "erased"
RESULTS = HERE / "results"

MODEL = "birefnet-general"
# variant → 글자 지운 입력 폴더 (None = 섹션 원본)
VARIANTS = {
    "birefnet_raw": None,
    "birefnet_erased": "_erase",
    # 인식 신뢰도 0.5 미만·빈 텍스트 박스는 지우지 않음 — 1차에서 얼굴·물방울을 오검출해 지웠다
    "birefnet_erased_s50": "_erase_s50",
}
BIG = 0.005   # 섹션 면적의 0.5% 이상인 덩어리만 '큰 덩어리'로 셈


def inputs(variant: str) -> list[tuple[str, Path]]:
    items = []
    for sp in sorted((SECTIONS / "sections").glob("*.json")):
        sec = json.loads(sp.read_text(encoding="utf-8"))
        for s in sec["sections"]:
            name = f"{sp.stem}_{s['index']:03d}"
            src = VARIANTS[variant]
            items.append((name, SECTIONS / s["crop"] if src is None else RESULTS / src / "erased" / f"{name}.png"))
    return items


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from rembg import new_session, remove

    session = new_session(MODEL)
    for v in (VARIANTS if args.variant == "all" else [args.variant]):
        out = RESULTS / v
        for sub in ("rgba", "mask"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        items = inputs(v)[: args.limit]
        missing = [str(p) for _, p in items if not p.exists()]
        if missing:
            raise SystemExit(f"입력 없음 {len(missing)}건 — prep_erase.py 먼저. 예: {missing[0]}")
        rows, t_all = [], time.perf_counter()
        for name, path in items:
            t0 = time.perf_counter()
            rgba = np.array(Image.open(io.BytesIO(remove(path.read_bytes(), session=session))).convert("RGBA"))
            sec = time.perf_counter() - t0
            bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
            alpha = bgra[:, :, 3]
            cv2.imwrite(str(out / "rgba" / f"{name}.png"), bgra)
            cv2.imwrite(str(out / "mask" / f"{name}.png"), alpha)
            fg = alpha > 127
            n, _, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8))
            big = int((stats[1:, cv2.CC_STAT_AREA] >= BIG * fg.size).sum()) if n > 1 else 0
            rows.append({"section": name, "sec": round(sec, 2), "foreground_pct": round(float(fg.mean() * 100), 1),
                         "components": n - 1, "big_components": big})
            print(f"  [{v}] {name:<24} {sec:>5.1f}s  전경 {rows[-1]['foreground_pct']:>5.1f}%  "
                  f"덩어리 {n - 1:>4}  큰 {big:>2}", flush=True)
        meta = {"variant": v, "model": MODEL, "sections": len(rows), "big_ratio": BIG,
                "total_sec": round(time.perf_counter() - t_all, 2), "per_section": rows,
                "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{v}] 완료 — {len(rows)}섹션 · {meta['total_sec']}s\n", flush=True)


if __name__ == "__main__":
    main()
