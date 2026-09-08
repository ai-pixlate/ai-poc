"""E1. 원문 지우기 — 대조 이미지 + 빈 등급표 생성기.

사용법
    python compare.py
    python compare.py --mask-tag d25

출력
    results/compare/{stem}.jpg   원본 | 마스크 | variant별 결과 를 가로로 붙인 판
    summary.md                   실행 요약 + 빈 등급표

등급 칸은 비워둔다. 채우는 건 사람 몫.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

LABEL_H = 34
GRADE_COLS = ["등급", "비고"]

# 채택 후보에서 제외된 variant. 판정 기록은 남기되 이후 작업에서 빼둔다.
EXCLUDED: dict[str, str] = {
    "ns": "LaMa 대비 열위 — 판정 완료 후 제외 (2026-08-20)",
    "telea": "LaMa 대비 열위 — 판정 완료 후 제외 (2026-08-20)",
}


def read_existing_grades() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 등급을 회수한다.

    재생성으로 사람이 매긴 등급이 날아가면 안 된다.
    행 형식: | {이미지} | `{variant}` | {등급} | {비고} | {대조} |
    """
    if not OUT.exists():
        return {}
    grades: dict[tuple[str, str], list[str]] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(GRADE_COLS) + 3:
            continue
        img, variant = cells[0], cells[1]
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[2 : 2 + len(GRADE_COLS)]
        if any(vals):
            grades[(img, variant.strip("`"))] = vals
    return grades


def ratio(values: list[str]) -> str:
    """A+B 비율. `-`는 분모에서 뺀다. 미판정이 있으면 진행률만 표시."""
    graded = [v.upper() for v in values if v.upper() in {"A", "B", "C"}]
    skipped = sum(1 for v in values if v == "-")
    total = len(values) - skipped
    if total == 0:
        return "-"
    if len(graded) < total:
        return f"판정 {len(graded)}/{total}"
    ab = sum(1 for v in graded if v in {"A", "B"})
    return f"{ab}/{total} ({ab / total * 100:.0f}%)"


def labeled(img: np.ndarray, text: str) -> np.ndarray:
    """패널 위에 제목 띠를 붙인다."""
    bar = np.full((LABEL_H, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return np.vstack([bar, img])


def imread(path: Path, flag=cv2.IMREAD_COLOR) -> np.ndarray | None:
    if not path.exists():
        return None
    return cv2.imdecode(np.fromfile(str(path), np.uint8), flag)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mask-tag", default="d15")
    args = ap.parse_args()

    mask_dir = RESULTS / "masks" / args.mask_tag
    if not (mask_dir / "meta.json").exists():
        raise SystemExit(f"마스크 없음: {mask_dir}")
    mask_meta = json.loads((mask_dir / "meta.json").read_text(encoding="utf-8"))

    variants = sorted(
        p.name for p in RESULTS.iterdir()
        if p.is_dir() and p.name not in {"masks", "compare"} and (p / "meta.json").exists()
    )
    if not variants:
        raise SystemExit("실행된 variant 없음. run.py 먼저 실행")
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in variants}

    kept = read_existing_grades()
    out_dir = RESULTS / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)

    stems = sorted((p.stem for p in mask_dir.glob("*.png")), key=lambda s: (len(s), s))
    made = []
    for stem in stems:
        src = next((imread(IMAGES / f"{stem}{e}") for e in (".jpg", ".jpeg", ".png") if (IMAGES / f"{stem}{e}").exists()), None)
        if src is None:
            continue
        mask = imread(mask_dir / f"{stem}.png", cv2.IMREAD_GRAYSCALE)
        panels = [labeled(src, "original"), labeled(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), f"mask {args.mask_tag}")]
        for v in variants:
            r = imread(RESULTS / v / f"{stem}.jpg")
            if r is not None:
                panels.append(labeled(r, v))
        sheet = np.hstack(panels)
        cv2.imwrite(str(out_dir / f"{stem}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
        made.append(stem)

    L: list[str] = []
    L.append("# E1. 원문 지우기 — 후보 비교")
    L.append("")
    L.append("> 자동 생성 파일. `compare.py` 재실행 시 덮어씀.")
    L.append("")
    L.append("## 1. 실행 요약")
    L.append("")
    L.append(f"- 마스크: `{args.mask_tag}` — B baseline poly를 글자 높이의 "
             f"**{mask_meta['dilate_ratio'] * 100:.0f}%**(최소 {mask_meta['dilate_min_px']}px)만큼 팽창")
    L.append(f"- 대상: {mask_meta['images']}장, 총 {mask_meta['total_regions']}개 영역")
    L.append("")
    L.append("| variant | 엔진 | 이미지 | 소요(s) | 파라미터 |")
    L.append("|---|---|---|---|---|")
    for v in variants:
        m = metas[v]
        par = ", ".join(f"{k}={val}" for k, val in m["params"].items())
        L.append(f"| `{v}` | {m['engine']} | {m['images']} | {m['total_sec']} | {par} |")
    L.append("")
    L.append("## 2. 판정표 (육안 A/B/C — 빈 칸 채울 것)")
    L.append("")
    L.append("**등급 기준** (PoC 문서 2.2)")
    L.append("")
    L.append("| 등급 | 기준 |")
    L.append("|---|---|")
    L.append("| **A** | 원문 흔적 없음, 배경과 자연스럽게 이어짐 |")
    L.append("| **B** | 자세히 봐야 티가 남 — 번역문을 얹으면 가려질 수준, 검수로 흡수 가능 |")
    L.append("| **C** | 원문이 읽히거나 왜곡·얼룩이 눈에 띔 |")
    L.append("")
    L.append("> **Go/No-Go**: 사진·그라데이션 배경 영역의 A+B 비율 70% 이상 → 사진 배경도 MVP 포함.")
    L.append("")
    L.append("| 이미지 | variant | " + " | ".join(GRADE_COLS) + " | 대조 |")
    L.append("|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for stem in made:
        for v in variants:
            vals = kept.get((f"{stem}.jpg", v), [" "] * len(GRADE_COLS))
            L.append(f"| {stem}.jpg | `{v}` | " + " | ".join(vals) + f" | [보기](results/compare/{stem}.jpg) |")
    L.append("")
    L.append("**집계** — 위 판정표에서 자동 계산됨. 직접 채우지 말 것")
    L.append("")
    L.append("| variant | A | B | C | A+B 비율 | 70% 통과 |")
    L.append("|---|---|---|---|---|---|")
    for v in variants:
        vals = [kept.get((f"{stem}.jpg", v), [""] * len(GRADE_COLS))[0] for stem in made]
        up = [x.upper() for x in vals]
        cnt = {g: up.count(g) for g in "ABC"}
        r = ratio(vals)
        gate = "판정 미완" if "판정" in r or r == "-" else ("O" if int(r.split("(")[1].rstrip("%)")) >= 70 else "X")
        mark = " *(제외)*" if v in EXCLUDED else ""
        L.append(f"| `{v}`{mark} | {cnt['A']} | {cnt['B']} | {cnt['C']} | {r} | {gate} |")
    L.append("")
    if EXCLUDED:
        L.append("**제외 variant**")
        L.append("")
        L.append("| variant | 사유 |")
        L.append("|---|---|")
        for v, why in EXCLUDED.items():
            if v in variants:
                L.append(f"| `{v}` | {why} |")
        L.append("")
    L.append("> ⚠️ 위 표는 **이미지 단위**다. 문서 2.2가 확정한 E1 판정 단위는 **영역 단위**이므로,")
    L.append("> 이 비율을 문서의 Go/No-Go 70%와 같은 값으로 취급하지 말 것. 판단 참고치로만 쓴다.")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"대조 이미지 {len(made)}장 → {out_dir}")
    print(f"작성 완료: {OUT}")
    print(f"  판정 {len(kept)}행 보존됨" if kept else "  판정 없음 (빈 표)")


if __name__ == "__main__":
    main()
