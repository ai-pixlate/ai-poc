"""F. 배경 가공 — 대조 이미지 + 빈 등급표 생성기.

사용법
    python compare.py

출력
    results/compare/{stem}.jpg   E1 결과 | variant별 보정 결과를 가로로 붙인 판
    summary.md                   실행 요약 + 빈 판정표

F는 Go/No-Go 대상이 아니라 개선 폭 확인 과업이라(문서 2.5),
등급이 아니라 **개선 여부**를 묻는다. 채우는 건 사람 몫이며 재실행해도 보존한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E1_SRC = ROOT / "poc" / "E1_inpaint" / "results" / "lama"
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

LABEL_H = 36
GRADE_COLS = ["개선 여부", "비고"]

# 문서 2.5 "처리 유형"과의 대응
KIND = {
    "ring_lama": "지운 자국 보정 — LaMa 재적용 (경계 링 마스크)",
    "seamless": "색상·톤 정합 — OpenCV 포아송 블렌딩",
    "feather": "이음새 제거 — 마스크 경계 블러·알파 혼합",
}


def labeled(img: np.ndarray, text: str) -> np.ndarray:
    bar = np.full((LABEL_H, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return np.vstack([bar, img])


def imread(p: Path):
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR) if p.exists() else None


def read_existing_grades() -> dict[tuple[str, str], list[str]]:
    """사람이 채운 칸을 재생성에서 지키기 위해 회수한다."""
    if not OUT.exists():
        return {}
    kept: dict[tuple[str, str], list[str]] = {}
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
            kept[(img, variant.strip("`"))] = vals
    return kept


def main() -> None:
    variants = sorted(p.name for p in RESULTS.iterdir()
                      if p.is_dir() and p.name != "compare" and (p / "meta.json").exists())
    if not variants:
        raise SystemExit("실행된 variant 없음. run.py 먼저 실행")
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in variants}
    kept = read_existing_grades()

    out_dir = RESULTS / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)

    stems = sorted((p.stem for p in E1_SRC.glob("*.jpg")), key=lambda s: (len(s), s))
    made = []
    for stem in stems:
        src = imread(E1_SRC / f"{stem}.jpg")
        if src is None:
            continue
        panels = [labeled(src, "E1 lama (input)")]
        for v in variants:
            r = imread(RESULTS / v / f"{stem}.jpg")
            if r is not None:
                panels.append(labeled(r, f"F  {v}"))
        cv2.imwrite(str(out_dir / f"{stem}.jpg"), np.hstack(panels), [cv2.IMWRITE_JPEG_QUALITY, 90])
        made.append(stem)

    L: list[str] = []
    L.append("# F. 배경 가공 — 보정 기법 비교")
    L.append("")
    L.append("> 자동 생성 파일. `compare.py` 재실행 시 덮어씀 (채운 칸은 보존됨).")
    L.append("")
    L.append("## 1. 실행 요약")
    L.append("")
    L.append(f"- 입력: `poc/E1_inpaint/results/lama/` (E1 채택 결과), 마스크 `d15`")
    L.append("- F는 Go/No-Go 대상이 아니라 **개선 폭 확인** 과업 (문서 2.5)")
    L.append("")
    L.append("| variant | 처리 유형 (문서 2.5) | 이미지 | 소요(s) |")
    L.append("|---|---|---|---|")
    for v in variants:
        m = metas[v]
        L.append(f"| `{v}` | {KIND.get(v, '-')} | {m['images']} | {m['total_sec']} |")
    L.append("")
    L.append("> 문서 2.5의 \"조각 이음새 제거\"는 A(리플로우)로 조각을 이어붙인 결과가 입력인데")
    L.append("> A가 미착수라 대상이 없다. `feather`는 그 대신 **인페인팅 경계의 이음새**를 다룬다.")
    L.append("")
    L.append("## 2. 판정표 (개선 여부 — 빈 칸 채울 것)")
    L.append("")
    L.append("| 표기 | 뜻 |")
    L.append("|---|---|")
    L.append("| **O** | E1 결과보다 나아짐 |")
    L.append("| **=** | 차이 없음 |")
    L.append("| **X** | 오히려 나빠짐 |")
    L.append("")
    L.append("| 이미지 | variant | " + " | ".join(GRADE_COLS) + " | 대조 |")
    L.append("|---|---|" + "---|" * len(GRADE_COLS) + "---|")
    for stem in made:
        for v in variants:
            vals = kept.get((f"{stem}.jpg", v), [" "] * len(GRADE_COLS))
            L.append(f"| {stem}.jpg | `{v}` | " + " | ".join(vals) + f" | [보기](results/compare/{stem}.jpg) |")
    L.append("")
    L.append("**집계** — 위 표에서 자동 계산됨")
    L.append("")
    L.append("| variant | O | = | X | 미판정 |")
    L.append("|---|---|---|---|---|")
    for v in variants:
        vals = [kept.get((f"{stem}.jpg", v), [""] * len(GRADE_COLS))[0].upper() for stem in made]
        L.append(f"| `{v}` | {vals.count('O')} | {vals.count('=')} | {vals.count('X')} | "
                 f"{sum(1 for x in vals if x not in {'O', '=', 'X'})} |")
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"대조 이미지 {len(made)}장 → {out_dir}")
    print(f"작성 완료: {OUT}")
    print(f"  판정 {len(kept)}행 보존됨" if kept else "  판정 없음 (빈 표)")


if __name__ == "__main__":
    main()
