"""골든 샘플 결과 이동 — 과업 폴더 → poc/golden/{단계}_{과업}/.

코드의 출력 경로는 그대로 둔다(2026-09-15 결정). 결과가 나오면 이 스크립트로 옮긴다.

    poc/{과업}/results/golden/{variant}/  →  poc/golden/{단계}_{과업}/results/{variant}/
    poc/{과업}/summary_golden.md          →  poc/golden/{단계}_{과업}/summary.md
                                             (문서 안 링크 results/golden/ → results/)

재실행할 때는 --restore로 과업 폴더에 되돌린 뒤 실행하고 다시 옮긴다.
compare.py가 기존 summary_golden.md에서 채운 등급을 회수하기 때문.

summary는 git 추적 파일이면 git mv로 옮긴다. results/는 .gitignore 대상.
이미 있는 대상은 덮어쓰지 않고 멈춘다.

사용법
    python poc/golden/move.py 1             # 단계 1 결과 → poc/golden/1_B_ocr/
    python poc/golden/move.py 2 --restore   # 단계 2 결과 → poc/block_role/ 로 되돌림
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POC = ROOT / "poc"

# 계획 3장 실행 순서
STAGES = {
    1: "B_ocr",
    2: "block_role",
    3: "product_label",
    4: "logo_match",
    5: "E1_inpaint",
    6: "style_extract",
    7: "length_expansion",
}


def tracked(path: Path) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=ROOT, capture_output=True)
    return r.returncode == 0


def move_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if tracked(src):
        subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True)
    else:
        shutil.move(str(src), str(dst))


def move_children(src: Path, dst: Path) -> list[str]:
    """src 아래 항목을 dst 아래로. 하나라도 대상이 있으면 아무것도 옮기지 않는다."""
    if not src.exists():
        return []
    children = sorted(src.iterdir())
    clash = [str(dst / c.name) for c in children if (dst / c.name).exists()]
    if clash:
        raise SystemExit(f"이미 있음 — 덮어쓰지 않음: {clash}")
    dst.mkdir(parents=True, exist_ok=True)
    for c in children:
        shutil.move(str(c), str(dst / c.name))
    src.rmdir()
    return [c.name for c in children]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=int, choices=sorted(STAGES))
    ap.add_argument("--restore", action="store_true", help="poc/golden → 과업 폴더로 되돌림")
    args = ap.parse_args()

    task = STAGES[args.stage]
    home_results, home_summary = POC / task / "results" / "golden", POC / task / "summary_golden.md"
    dest = HERE / f"{args.stage}_{task}"
    dest_results, dest_summary = dest / "results", dest / "summary.md"

    if not args.restore:
        if not home_results.exists() and not home_summary.exists():
            raise SystemExit(f"옮길 결과 없음: {home_results} · {home_summary}")
        if home_summary.exists() and dest_summary.exists():
            raise SystemExit(f"이미 있음 — 덮어쓰지 않음: {dest_summary}")
        names = move_children(home_results, dest_results)
        if home_summary.exists():
            move_file(home_summary, dest_summary)
            text = dest_summary.read_text(encoding="utf-8")
            dest_summary.write_text(text.replace("results/golden/", "results/"), encoding="utf-8")
        print(f"단계 {args.stage} {task} → {dest.relative_to(ROOT)}  results: {names or '없음'}"
              f" · summary: {'이동' if dest_summary.exists() else '없음'}")
        return

    if not dest.exists():
        raise SystemExit(f"되돌릴 결과 없음: {dest}")
    if dest_summary.exists() and home_summary.exists():
        raise SystemExit(f"이미 있음 — 덮어쓰지 않음: {home_summary}")
    names = move_children(dest_results, home_results)
    if dest_summary.exists():
        move_file(dest_summary, home_summary)
        text = home_summary.read_text(encoding="utf-8")
        # 경로 앞이 글자·/·. 이면 다른 폴더 경로(poc/ocr_split/results 등)라 건드리지 않는다
        home_summary.write_text(re.sub(r"(?<![\w/.])results/(?!golden/)", "results/golden/", text), encoding="utf-8")
    if dest.exists() and not any(dest.iterdir()):
        dest.rmdir()
    print(f"단계 {args.stage} {dest.relative_to(ROOT)} → poc/{task}  results: {names or '없음'}"
          f" · summary: {'되돌림' if home_summary.exists() else '없음'}")


if __name__ == "__main__":
    main()
