"""번역 길이 팽창률 — 폭 측정 variant 실행기.

번역문을 원본 박스에 얹었을 때 넘치는지 잰다. 번역은 `run_llm.py`가 이미 했다.
전부 로컬 계산, 비용 0.

variant — 조판이 무엇까지 허용하는가
    nowrap           한 줄 가정. 번역문 폭이 박스 폭을 넘으면 초과.
    wrap_allowed     줄바꿈 허용. 줄을 접은 뒤 총 높이가 박스 높이를 넘으면 초과.
    wrap_and_shrink  줄바꿈 + 폰트 축소(100·95·90·85·80%). 다 해도 안 들어가면 초과.

**판정 대상은 `wrap_and_shrink`의 잔여 초과율**이다. 개발계획서 §4.3이 묻는
값은 흡수 전 초과율이 아니라 조정 상한으로도 흡수되지 않는 비율이다.

폭 추정 가정 (전부 이 파일 상단 상수에서만 바꾼다)
    폰트      대상 언어가 영어라 Arial. 없으면 DejaVuSans
    줄 높이   원본 = bbox 높이 / 원문 줄 수
    em 크기   줄 높이 × EM_RATIO. OCR bbox는 글자 획 높이라 em보다 작다
    줄 간격   렌더 줄 높이 = em × LINE_GAP
    자간      0 — 조정하지 않음

이 가정이 바뀌면 초과율이 통째로 움직인다. 결과 문서에 그대로 남길 것.

입력
    translations/{input}.json          run_llm.py 산출
    ../product_label/results/vlm_relation/blocks/*.json   원문 줄 수(block 입력)

출력
    results/{variant}/{input}.json     세그먼트별 측정치
    results/{variant}/meta.json        집계

사용법
    python run.py --variant all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TRANS = HERE / "translations"
BLOCKS = ROOT / "poc" / "product_label" / "results" / "vlm_relation" / "blocks"
RESULTS = HERE / "results"

FONT_CANDIDATES = ("arial.ttf", "DejaVuSans.ttf", "malgun.ttf")
EM_RATIO = 1.35     # 줄 높이 → em. OCR bbox 높이는 글자 획 높이(≈0.74em)
LINE_GAP = 1.20     # 렌더 줄 높이 = em × 이 값
SHRINK_STEPS = (1.0, 0.95, 0.90, 0.85, 0.80)
# 필요 축소율 탐색 범위. 0.30까지 줄여도 안 들어가면 조판으로 흡수 불가로 본다.
NEED_STEPS = tuple(round(1.0 - 0.05 * i, 2) for i in range(15))   # 1.00 → 0.30

VARIANTS = {
    "nowrap": {"wrap": False, "shrink": (1.0,)},
    "wrap_allowed": {"wrap": True, "shrink": (1.0,)},
    "wrap_and_shrink": {"wrap": True, "shrink": SHRINK_STEPS},
}


def load_font(px: int) -> ImageFont.FreeTypeFont:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, max(1, px))
        except OSError:
            continue
    raise SystemExit(f"폰트를 찾지 못함: {FONT_CANDIDATES}")


def wrap_lines(text: str, font: ImageFont.FreeTypeFont, max_w: float) -> list[str] | None:
    """공백 기준 그리디 줄바꿈. 단어 하나가 박스보다 넓으면 None."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    if font.getlength(cur) > max_w:
        return None
    for w in words[1:]:
        if font.getlength(w) > max_w:
            return None
        trial = f"{cur} {w}"
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def fits(text: str, box_w: int, box_h: int, em: int, scale: float, wrap: bool) -> bool:
    """이 배율로 박스에 들어가는가."""
    px = max(1, round(em * scale))
    f = load_font(px)
    if not wrap:
        return f.getlength(text) <= box_w
    lines = wrap_lines(text, f, box_w)
    if lines is None:
        return False
    return len(lines) * px * LINE_GAP <= box_h + 1


def source_lines(seg: dict, n_lines: dict[str, int]) -> int:
    return n_lines.get(seg["id"], 1)


def measure(seg: dict, cfg: dict, src_lines: int) -> dict:
    x1, y1, x2, y2 = seg["bbox"]
    box_w, box_h = x2 - x1, y2 - y1
    line_h = box_h / max(1, src_lines)
    em = max(1, round(line_h * EM_RATIO))

    base = load_font(em)
    width100 = base.getlength(seg["target"])
    # 배율은 **박스가 담을 수 있는 총 길이** 대비로 낸다.
    # 원문이 2줄이면 박스는 두 줄치를 담으므로 분모가 box_w × 줄 수다.
    ratio = width100 / max(1, box_w * src_lines)

    fitted = None
    for scale in cfg["shrink"]:
        if fits(seg["target"], box_w, box_h, em, scale, wrap=cfg["wrap"]):
            fitted = scale
            break

    # 얼마나 줄이면 들어가는가 — 조정 상한을 정하는 데 쓰는 값
    need = None
    for scale in NEED_STEPS:
        if fits(seg["target"], box_w, box_h, em, scale, wrap=True):
            need = scale
            break

    return {
        "id": seg["id"],
        "image": seg["image"],
        "role": seg.get("role"),
        "source": seg["text"],
        "target": seg["target"],
        "box": [box_w, box_h],
        "src_lines": src_lines,
        "em": em,
        "width100": round(width100, 1),
        "ratio": round(ratio, 2),
        "fit_scale": fitted,      # None이면 이 variant 조건에서 초과
        "need_scale": need,       # 줄바꿈 허용 시 들어가는 최소 배율. None이면 0.30에도 불가
        "overflow": fitted is None,
    }


def block_line_counts() -> dict[str, int]:
    """block 입력의 원문 줄 수. id는 `{stem}-{블록번호}` 형식이다."""
    out: dict[str, int] = {}
    for path in BLOCKS.glob("*.json"):
        for i, b in enumerate(json.loads(path.read_text(encoding="utf-8"))["blocks"], 1):
            out[f"{path.stem}-{i:02d}"] = b["text"].count("\n") + 1
    return out


def run_variant(name: str, inputs: list[str]) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    out_dir.mkdir(parents=True, exist_ok=True)
    lines_map = block_line_counts()

    print(f"[{name}] {cfg}")
    meta = {"variant": name, "cfg": cfg,
            "assumptions": {"font": FONT_CANDIDATES[0], "em_ratio": EM_RATIO,
                            "line_gap": LINE_GAP, "letter_spacing": 0},
            "inputs": {}, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    t0 = time.perf_counter()

    for inp in inputs:
        src = json.loads((TRANS / f"{inp}.json").read_text(encoding="utf-8"))
        rows = [
            measure(s, cfg, source_lines(s, lines_map) if inp == "block" else 1)
            for s in src["segments"]
        ]
        over = sum(1 for r in rows if r["overflow"])
        by_scale = {
            f"{int(s * 100)}%": sum(1 for r in rows if r["fit_scale"] == s)
            for s in cfg["shrink"]
        }
        (out_dir / f"{inp}.json").write_text(
            json.dumps({"input": inp, "variant": name, "segments": rows},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        needs = [r["need_scale"] for r in rows]
        cum = {}
        for th in (1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5):
            ok = sum(1 for n in needs if n is not None and n >= th)
            cum[f"{int(th * 100)}%"] = round(ok / max(1, len(rows)), 3)
        meta["inputs"][inp] = {
            "segments": len(rows), "overflow": over,
            "overflow_rate": round(over / max(1, len(rows)), 3),
            "fit_by_scale": by_scale,
            "absorb_cum_by_min_scale": cum,
            "unfittable_even_at_30pct": sum(1 for n in needs if n is None),
            "ratio_median": round(sorted(r["ratio"] for r in rows)[len(rows) // 2], 2),
            "ratio_max": max(r["ratio"] for r in rows),
        }
        print(f"  {inp:<7} 세그 {len(rows):>3}  초과 {over:>3} "
              f"({over / max(1, len(rows)):.0%})  배율 중앙 {meta['inputs'][inp]['ratio_median']}")

    meta["total_sec"] = round(time.perf_counter() - t0, 2)
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--inputs", nargs="*", default=None)
    args = ap.parse_args()

    inputs = args.inputs or sorted(p.stem for p in TRANS.glob("*.json") if ".meta" not in p.name)
    if not inputs:
        raise SystemExit(f"{TRANS} 에 번역 결과 없음 — run_llm.py 를 먼저 돌릴 것")

    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, inputs)


if __name__ == "__main__":
    main()
