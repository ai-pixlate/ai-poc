"""번역 길이 팽창률 — 골든 샘플 폭 측정기 (계획 단계 7).

번역은 `run_llm.py --input golden`이 이미 했다. 여기는 전부 로컬 계산, 비용 0.
측정 조건·폰트 가정·variant 정의는 run.py 것을 그대로 불러 쓴다(같은 과업 폴더).

12장과 다른 점은 입력 단위뿐이다.
    · 문서 = 섹션(102개 중 조판 대상 블록이 있는 96개)
    · 원문 줄 수는 단계 2 `llm_assist` 블록에서 읽는다

입력
    translations/golden.json                                   번역문·bbox
    poc/golden/2_block_role/results/llm_assist/blocks/*.json   원문 줄 수

출력
    results/golden/{variant}/golden.json   세그먼트별 측정치
    results/golden/{variant}/meta.json     집계

사용법
    python run_golden.py --variant all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import run as R  # 같은 과업 폴더 — 폭 측정·집계 로직을 그대로 쓴다

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TRANS = HERE / "translations" / "golden.json"
GOLDEN_BLOCKS = ROOT / "poc" / "golden" / "2_block_role" / "results" / "llm_assist" / "blocks"
OUT = HERE / "results" / "golden"
# 계획 단계 7 — 이 4조건만 잰다
VARIANTS = ("nowrap", "wrap_allowed", "wrap_and_shrink", "wrap_grow_20")


def golden_line_counts() -> dict:
    """원문 줄 수. id는 `{섹션}-{블록번호}` 형식이다."""
    out = {}
    for path in sorted(GOLDEN_BLOCKS.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        for i, b in enumerate(d["blocks"], 1):
            out[f"{d['section']}-{i:02d}"] = b["text"].count("\n") + 1
    return out


def run_variant(name: str, segs: list, lines_map: dict) -> dict:
    cfg = R.VARIANTS[name]
    out_dir = OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    rows = [R.measure(s, cfg, lines_map.get(s["id"], 1)) for s in segs]
    over = sum(1 for r in rows if r["overflow"])
    by_scale = {f"{int(s * 100)}%": sum(1 for r in rows if r["fit_scale"] == s)
                for s in cfg["shrink"]}
    needs = [r["need_scale"] for r in rows]
    cum = {}
    for th in (1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5):
        ok = sum(1 for n in needs if n is not None and n >= th)
        cum[f"{int(th * 100)}%"] = round(ok / max(1, len(rows)), 3)
    grows = [r["need_grow"] for r in rows]
    grows80 = [r["need_grow_at_80"] for r in rows]
    cum_g = {f"{g}배": round(sum(1 for x in grows if x is not None and x <= g) / max(1, len(rows)), 3)
             for g in R.GROW_STEPS}
    cum_g80 = {f"{g}배": round(sum(1 for x in grows80 if x is not None and x <= g) / max(1, len(rows)), 3)
               for g in R.GROW_STEPS}

    # role별 초과 — 배지·버튼처럼 밀 자리가 없는 역할을 갈라 보려는 것
    by_role = {}
    for r in rows:
        k = r.get("role") or "미상"
        s = by_role.setdefault(k, {"segments": 0, "overflow": 0})
        s["segments"] += 1
        s["overflow"] += int(r["overflow"])
    for s in by_role.values():
        s["rate"] = round(s["overflow"] / max(1, s["segments"]), 3)

    # 섹션별 초과 — 긴 본문 섹션에서 달라지는지 보려는 것
    by_sec = {}
    for r in rows:
        s = by_sec.setdefault(r["image"], {"segments": 0, "overflow": 0})
        s["segments"] += 1
        s["overflow"] += int(r["overflow"])
    for s in by_sec.values():
        s["rate"] = round(s["overflow"] / max(1, s["segments"]), 3)

    ok_g = [x for x in grows if x is not None]
    info = {
        "variant": name, "cfg": cfg, "sample": "golden",
        "assumptions": {"font": R.FONT_CANDIDATES[0], "em_ratio": R.EM_RATIO,
                        "line_gap": R.LINE_GAP, "letter_spacing": 0},
        "sections": len(by_sec), "segments": len(rows), "overflow": over,
        "overflow_rate": round(over / max(1, len(rows)), 3),
        "fit_by_scale": by_scale,
        "absorb_cum_by_min_scale": cum,
        "unfittable_even_at_30pct": sum(1 for n in needs if n is None),
        "absorb_cum_by_grow": cum_g,
        "absorb_cum_by_grow_at_80": cum_g80,
        "grow_median": sorted(ok_g)[len(ok_g) // 2] if ok_g else None,
        "ratio_median": round(sorted(r["ratio"] for r in rows)[len(rows) // 2], 2),
        "ratio_max": max(r["ratio"] for r in rows),
        "by_role": by_role, "by_section": by_sec,
        "total_sec": round(time.perf_counter() - t0, 2),
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "golden.json").write_text(
        json.dumps({"input": "golden", "variant": name, "segments": rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {name:<16} 세그 {len(rows)}  초과 {over} ({over / max(1, len(rows)):.0%})  "
          f"배율 중앙 {info['ratio_median']}", flush=True)
    return info


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all", help=f"{', '.join(VARIANTS)}, all")
    args = ap.parse_args()

    if not TRANS.exists():
        raise SystemExit(f"{TRANS} 없음 — run_llm.py --input golden 먼저")
    segs = json.loads(TRANS.read_text(encoding="utf-8"))["segments"]
    lines_map = golden_line_counts()
    miss = [s["id"] for s in segs if s["id"] not in lines_map]
    if miss:
        raise SystemExit(f"원문 줄 수 없음: {miss[:5]} ...({len(miss)})")

    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    print(f"[golden] 세그먼트 {len(segs)} · 섹션 {len({s['image'] for s in segs})}")
    for n in names:
        if n not in R.VARIANTS:
            raise SystemExit(f"모르는 variant: {n}")
        run_variant(n, segs, lines_map)


if __name__ == "__main__":
    main()
