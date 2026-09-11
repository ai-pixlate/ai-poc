"""브랜드 로고 제외 — 요약표 생성기.

기계가 셀 수 있는 것과 사람이 봐야 하는 것을 나눈다.

기계 집계 — 정답 없이도 확실한 것
    **확정 오탐** = 남의 브랜드 페이지에서 임계를 넘은 매칭.
    `b.clinicx` 로고가 goodal 페이지에서 나왔다면 볼 것도 없이 오탐이다.

사람 판정 — 자기 브랜드 페이지
    찾음·놓침·오탐. 로고가 실제로 몇 번 나오는지는 사람이 세야 한다.
    제품 패키지 위 로고는 라벨 판정 소관이라 세지 않는다.

**이미 채워진 칸은 재실행해도 보존한다.**

사용법
    python compare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

# 로고 → 그 로고의 브랜드 페이지 폴더
HOME = {"b.clinicx": "images_A000000213548", "goodal": "images_A000000219554",
        "goodal_serif": "images_A000000219554"}
ORDER = ("template_gray", "template_gray_lo", "template_edge", "template_edge_lo", "feature_orb")
COUNT_COLS = ["찾음", "놓침", "오탐", "비고"]


def variants() -> list[str]:
    return [v for v in ORDER if (RESULTS / v / "meta.json").exists()]


def read_filled() -> dict[tuple[str, str, str], list[str]]:
    if not OUT.exists():
        return {}
    got = {}
    width = 4 + len(COUNT_COLS) + 1  # 이미지 로고 variant 통과 | 판정 4칸 | 시각화
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != width or not c[0].endswith(".jpg") or not c[2].startswith("`"):
            continue
        vals = c[4:4 + len(COUNT_COLS)]
        if any(vals):
            got[(c[0], c[1].strip("`"), c[2].strip("`"))] = vals
    return got


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    names = variants()
    if not names:
        raise SystemExit("실행 결과 없음 — run.py 를 먼저 돌릴 것")
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in names}
    filled = read_filled()

    def load(v, img):
        return json.loads((RESULTS / v / "matches" / f"{Path(img).stem}.json")
                          .read_text(encoding="utf-8"))["matches"]

    per = {v: {p["image"]: p for p in metas[v]["per_image"]} for v in names}
    images = [p["image"] for p in metas[names[0]]["per_image"]]
    folder = {p["image"]: p["brand_folder"] for p in metas[names[0]]["per_image"]}

    L = ["# 브랜드 로고 제외 — 실행 결과", "",
         "> 이 파일은 `compare.py`가 생성함. **자기 브랜드 페이지의 찾음·놓침·오탐만 사람이 채움.**",
         "> ⚠️ 등록 로고 파일이 없어 **페이지에서 잘라낸 임시 템플릿**을 씀. 원래 자리는 평가에서 뺌.",
         ""]

    L += ["## 1. 실행 조건", "",
          "| variant | 방식 | 임계 | 소요 |", "|---|---|---|---|"]
    how = {"template_gray": "다중 스케일 밝기 매칭(NCC)", "template_edge": "윤곽선끼리 매칭",
           "feature_orb": "ORB 특징점 + 호모그래피",
           "template_gray_lo": "밝기 매칭 · **임계만 낮춤**", "template_edge_lo": "윤곽선 매칭 · **임계만 낮춤**"}
    for v in names:
        cfg = metas[v]["cfg"]
        thr = cfg.get("thresh", cfg.get("min_inliers"))
        unit = "점수" if "thresh" in cfg else "인라이어"
        L.append(f"| `{v}` | {how[v]} | {unit} ≥ {thr} | {metas[v]['total_sec']}s |")
    L += ["", f"템플릿 — " + " · ".join(f"`{k}`" for k in HOME) +
          ". 배율 0.4~2.0배. `results/_templates/`에 저장.", ""]

    # 2. 확정 오탐
    L += ["## 2. 확정 오탐 (기계 집계)", "",
          "**남의 브랜드 페이지에서 임계를 넘은 매칭.** 정답 없이도 오탐임이 확실함.", "",
          "| variant | " + " | ".join(f"`{k}` 확정 오탐" for k in HOME) + " | 합계 | 자기 페이지 통과 |",
          "|---|" + "---|" * (len(HOME) + 2)]
    for v in names:
        cells, tot, own = [], 0, 0
        for logo, home in HOME.items():
            n = 0
            for img in images:
                for m in load(v, img):
                    if m["logo"] != logo or not m["pass"] or m["is_source"]:
                        continue
                    if folder[img] == home:
                        own += 1
                    else:
                        n += 1
            cells.append(str(n))
            tot += n
        L.append(f"| `{v}` | " + " | ".join(cells) + f" | **{tot}** | {own} |")
    L += ["", "**확정 오탐이 0이 아닌 variant는 탈락 후보임** — 판정 기준상 오탐이 놓침보다 나쁨.", ""]

    # 3. 판정표 — 자기 브랜드 페이지만
    L += ["## 3. 판정표 — 자기 브랜드 페이지", "",
          "**채울 칸은 `찾음`·`놓침`·`오탐` 3개.** `vis/`에서 초록=임계 통과, 주황=미달, 회색=템플릿 원래 자리.",
          "", "- **찾음** = 페이지 디자인에 올린 로고를 초록 박스로 잡은 수",
          "- **놓침** = 실제 로고인데 초록 박스가 없는 수",
          "- **오탐** = 로고가 아닌 곳에 초록 박스가 있는 수",
          "- 제품 패키지 위 로고는 **세지 않음** — 라벨 판정 소관", "",
          "| 이미지 | 로고 | variant | 통과 | " + " | ".join(COUNT_COLS) + " | 시각화 |",
          "|---|---|---|---|" + "---|" * len(COUNT_COLS) + "---|"]
    for logo, home in HOME.items():
        for img in images:
            if folder[img] != home:
                continue
            for v in names:
                n = per[v][img]["by_logo"].get(logo, 0)
                vals = filled.get((img, logo, v), [""] * len(COUNT_COLS))
                L.append(f"| {img} | `{logo}` | `{v}` | {n} | " + " | ".join(vals)
                         + f" | `results/{v}/vis/{Path(img).stem}.jpg` |")
    L.append("")

    # 4. 집계
    L += ["## 4. 집계", ""]
    if not filled:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L += ["| variant | 찾음 | 놓침 | 오탐 | 매칭 실패율 |", "|---|---|---|---|---|"]
        for v in names:
            f = m = o = 0
            for (img, logo, var), vals in filled.items():
                if var != v:
                    continue
                try:
                    f, m, o = f + int(vals[0] or 0), m + int(vals[1] or 0), o + int(vals[2] or 0)
                except ValueError:
                    continue
            rate = m / (f + m) if (f + m) else 0
            L.append(f"| `{v}` | {f} | {m} | **{o}** | {rate:.0%} |")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}")


if __name__ == "__main__":
    main()
