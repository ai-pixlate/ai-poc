"""브랜드 로고 제외 — 요약표 생성기.

기계가 셀 수 있는 것과 사람이 봐야 하는 것을 나눈다.

기계 집계 — 정답 없이도 확실한 것
    **확정 오탐** = 남의 브랜드 페이지에서 임계를 넘은 매칭.
    `b.clinicx` 로고가 goodal 페이지에서 나왔다면 볼 것도 없이 오탐이다.

사람 판정 — 자기 브랜드 페이지
    찾음·놓침·오탐. 로고가 실제로 몇 번 나오는지는 사람이 세야 한다.
    제품 패키지 위 로고는 라벨 판정 소관이라 세지 않는다.

**이미 채워진 칸은 재실행해도 보존한다.**

텍스트 대조 (`run_text.py`)
    OCR 텍스트를 브랜드명과 대조. 상품마다 자기 브랜드명만 대조하므로 "남의 페이지"
    축이 없다. 통과 목록(기계)과 판정표(사람)를 따로 둔다.

--sample golden
    results/golden/block_exact/meta.json 을 읽어 summary_golden.md 를 만든다.
    기존 정답(페이지 로고 7개)과 기계 대조 결과라 사람이 채울 칸 없음 — 대지로 확인만.
    출력은 과업 폴더에 나오고 poc/golden/move.py 4 로 옮긴다.

사용법
    python compare.py
    python compare.py --sample golden
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

# 로고 → 그 로고의 브랜드 페이지 폴더
HOME = {"b.clinicx": "images_A000000213548", "goodal": "images_A000000219554",
        "goodal_serif": "images_A000000219554"}
ORDER = ("template_gray", "template_gray_lo", "template_edge", "template_edge_lo", "feature_orb")
TEXT_ORDER = ("text_exact", "text_fuzzy", "text_contains", "line_exact", "block_exact")
COUNT_COLS = ["찾음", "놓침", "오탐", "비고"]


def variants() -> list[str]:
    return [v for v in ORDER if (RESULTS / v / "meta.json").exists()]


def read_filled() -> tuple[dict, dict]:
    """(템플릿 판정표, 텍스트 판정표) 채워진 칸."""
    if not OUT.exists():
        return {}, {}
    got, got_text = {}, {}
    width_text = 3 + len(COUNT_COLS) + 1  # 이미지 variant 통과 | 판정 4칸 | 시각화
    width = 4 + len(COUNT_COLS) + 1  # 이미지 로고 variant 통과 | 판정 4칸 | 시각화
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) == width_text and c[0].endswith(".jpg") and c[1].strip("`") in TEXT_ORDER:
            vals = c[3:3 + len(COUNT_COLS)]
            if any(vals):
                got_text[(c[0], c[1].strip("`"))] = vals
            continue
        if len(c) != width or not c[0].endswith(".jpg") or not c[2].startswith("`"):
            continue
        vals = c[4:4 + len(COUNT_COLS)]
        if any(vals):
            got[(c[0], c[1].strip("`"), c[2].strip("`"))] = vals
    return got, got_text


def main_default() -> None:
    names = variants()
    if not names:
        raise SystemExit("실행 결과 없음 — run.py 를 먼저 돌릴 것")
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in names}
    filled, filled_text = read_filled()
    text_names = [v for v in TEXT_ORDER if (RESULTS / v / "meta.json").exists()]

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

    # 4. 텍스트 대조
    if text_names:
        tm = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in text_names}
        m0 = tm[text_names[0]]
        L += ["## 4. 텍스트 대조 — 실행 조건", "",
              f"OCR은 텍스트 추출 확정 조건(`baseline`)을 **{m0['tile']}px 띠 · {m0['overlap']}px 겹침**으로 "
              f"돌려 합침. variant 공통 캐시 `results/_ocr/`.", "",
              "| variant | 대조 방식 | 통과 | OCR (공통) | 대조 |", "|---|---|---|---|---|"]
        how_t = {"text_exact": "정규화 텍스트 == 브랜드명", "text_fuzzy": "유사도 ≥ 0.8",
                 "text_contains": "브랜드명 포함 (대조군)",
                 "line_exact": "줄 병합 후 == 브랜드명", "block_exact": "줄·문단 병합 후 == 브랜드명"}
        for v in text_names:
            L.append(f"| `{v}` | {how_t[v]} | {tm[v]['total_pass']} | {tm[v]['ocr_sec']}s | {tm[v]['match_sec']}s |")
        L += ["", "브랜드명 사전 (**가정** — 페이지에서 확인한 표기)", "",
              "| 상품 폴더 | 표기 |", "|---|---|"]
        for f, keys in m0["brands"].items():
            L.append(f"| {f} | " + " · ".join(f"`{k}`" for k in keys) + " |")
        L.append("")

        def load_t(v, img):
            return json.loads((RESULTS / v / "matches" / f"{Path(img).stem}.json")
                              .read_text(encoding="utf-8"))["matches"]

        # 통과 목록 — region 단위로 어느 variant가 통과시켰는지
        L += ["## 5. 텍스트 대조 — 통과 목록 (기계 집계)", "",
              "통과 region 전체. 잘라 모은 대지는 `results/{variant}/hits.jpg`.", "",
              "| 이미지 | y | 텍스트 | " + " | ".join(f"`{v}`" for v in text_names) + " |",
              "|---|---|---|" + "---|" * len(text_names)]
        t_images = [p["image"] for p in m0["per_image"]]
        for img in t_images:
            rows = {}
            for v in text_names:
                for m in load_t(v, img):
                    rows.setdefault(tuple(m["bbox"]), {"text": m["text"], "by": {}})["by"][v] = m["ratio"]
            for k in sorted(rows, key=lambda b: b[1]):
                r = rows[k]
                marks = [("✓" if r["by"][v] == 1.0 else f"✓ {r['by'][v]}") if v in r["by"] else ""
                         for v in text_names]
                txt = r["text"].strip().replace("|", "\\|").replace("\n", " / ")
                L.append(f"| {img} | {k[1]} | {txt} | " + " | ".join(marks) + " |")
        L.append("")

        L += ["## 6. 텍스트 대조 — 판정표", "",
              "**채울 칸은 `찾음`·`놓침`·`오탐`.** 기준은 3장과 같음 — 페이지 디자인에 올린 로고만 셈. "
              "패키지 위 로고는 세지 않음.", "",
              "| 이미지 | variant | 통과 | " + " | ".join(COUNT_COLS) + " | 시각화 |",
              "|---|---|---|" + "---|" * len(COUNT_COLS) + "---|"]
        per_t = {v: {p["image"]: p for p in tm[v]["per_image"]} for v in text_names}
        for img in t_images:
            for v in text_names:
                n = per_t[v][img]["pass"]
                vals = filled_text.get((img, v), [""] * len(COUNT_COLS))
                vis = f"`results/{v}/vis/{Path(img).stem}.jpg`" if n else "—"
                L.append(f"| {img} | `{v}` | {n} | " + " | ".join(vals) + f" | {vis} |")
        L.append("")

    # 7. 집계
    L += ["## 7. 집계", ""]
    if not filled and not filled_text:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L += ["| variant | 찾음 | 놓침 | 오탐 | 매칭 실패율 |", "|---|---|---|---|---|"]

        def tally(rows):
            f = m = o = 0
            for vals in rows:
                try:
                    f, m, o = f + int(vals[0] or 0), m + int(vals[1] or 0), o + int(vals[2] or 0)
                except ValueError:
                    continue
            return f, m, o

        groups = [(v, [vals for (_, _, var), vals in filled.items() if var == v]) for v in names]
        groups += [(v, [vals for (_, var), vals in filled_text.items() if var == v]) for v in text_names]
        for v, rows in groups:
            if not rows:
                L.append(f"| `{v}` | _판정 전_ | | | |")
                continue
            f, m, o = tally(rows)
            rate = m / (f + m) if (f + m) else 0
            L.append(f"| `{v}` | {f} | {m} | **{o}** | {rate:.0%} |")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}")


# ── 골든 샘플 — 단계 4 재확인 ───────────────────────────────────────────

GOLDEN = RESULTS / "golden" / "block_exact"
GOLDEN_OUT = HERE / "summary_golden.md"


def g_text(s: str | None) -> str:
    return (s or "—").replace("|", "\\|").replace("\n", " / ").strip()


def main_golden() -> None:
    p = GOLDEN / "meta.json"
    if not p.exists():
        raise SystemExit(f"{p} 없음 — run_text.py --sample golden 먼저")
    m = json.loads(p.read_text(encoding="utf-8"))
    c, prev = m["counts"], m["prev"]
    rel = "results/golden/block_exact"

    L = ["# 브랜드 로고 제외 — 골든 샘플 재확인", "",
         "> `compare.py --sample golden`이 생성함. 계획 `PoC_골든샘플_재실행_계획.md` 단계 4. 12장·34장 결과(`summary.md`)는 건드리지 않음.",
         "> **기계 대조** — 기존 정답(페이지 로고 7개 · 5장)과 페이지 좌표 IoU ≥ 0.5로 맞춤. 사람이 채울 칸 없음, 대지로 확인만.",
         ""]

    L += ["## 1. 실행 조건", "", "| 항목 | 값 |", "|---|---|",
          "| 규칙 | `block_exact` — 블록 텍스트 전체 == 브랜드명(NFKC · 소문자 · 공백·문장부호 제거) |",
          "| 입력 | 단계 2 `llm_assist` 블록 · 단계 3 라벨 정답(패키지 위 로고 = 라벨 소관, 세지 않음) |",
          "| 기존 결과 | 병합 1단계 `heuristic_v2` 블록 기준 — 결과 문서 6장 |",
          f"| 섹션 · 블록 | {m['sections']} · {m.get('blocks', m.get('units'))} |",
          f"| 브랜드명 통과 | {m['pass']} (라벨 블록 {m['pass_label']} · 라벨 밖 {m['pass'] - m['pass_label']}) |",
          f"| 대조 소요 | {m['match_sec']}s |",
          "| 브랜드명 사전 | " + " · ".join(f"{k.replace('images_', '')} `{'` `'.join(v)}`" for k, v in m["brands"].items()) + " |",
          ""]

    L += ["## 2. 기계 대조 결과", "",
          "| 블록 기준 | 찾음 | 놓침 | 오탐 | 종결 기준 (놓침·오탐이 기존보다 늘지 않음) |", "|---|---|---|---|---|",
          f"| 기존 `heuristic_v2` | {prev['found']} | {prev['missed']} | {prev['false']} | — |",
          f"| **이번 `llm_assist`** | **{c['found']}** | **{c['missed']}** | **{c['false']}** | **{m['gate']}** |", ""]

    L += ["## 3. 페이지 로고 7개", "",
          f"대지 `{rel}/logos.jpg` — 초록 찾음 · 빨강 놓침 · 파랑 = 로고를 품은 `llm_assist` 블록.", "",
          "| # | 페이지 | y | 로고 | 기존 | 이번 | 품은 블록 | 블록 텍스트 |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(m["page_logos"], 1):
        host = f"`{r['host_section']}` #{r['host_block']}" if r["host_section"] else "없음"
        mark = "**놓침**" if r["status"] == "놓침" else "찾음"
        L.append(f"| {i} | {r['image'][:-4]} | {r['bbox'][1]} | `{r['text']}` | {r['prev_block_exact']} | {mark} | {host} | {g_text(r['host_text'])} |")
    L.append("")

    L += ["## 4. 브랜드명 통과 블록", "",
          "| 섹션 | 블록 | y (페이지) | 텍스트 | 구분 |", "|---|---|---|---|---|"]
    logo_keys = {(r["host_section"], r["host_block"]) for r in m["page_logos"] if r["status"] == "찾음"}
    rows = [(h, "라벨 소관(패키지)") for h in m["package_hits"]] + [(h, "오탐") for h in m["false_hits"]]
    for r in m["page_logos"]:
        if r["status"] == "찾음":
            rows.append(({"section": r["host_section"], "block": r["host_block"], "page_bbox": r["host_page_bbox"],
                          "text": r["host_text"]}, "페이지 로고 찾음"))
    for h, kind in sorted(rows, key=lambda x: (x[0]["section"], x[0]["block"])):
        L.append(f"| `{h['section']}` | {h['block']} | {h['page_bbox'][1]} | {g_text(h['text'])} | {kind} |")
    L.append("")

    missed = [r for r in m["page_logos"] if r["status"] == "놓침"]
    if missed:
        L += ["## 5. 놓침 원인", "", "| 페이지 | y | 기존 | 품은 블록 텍스트 | 원인 |", "|---|---|---|---|---|"]
        for r in missed:
            why = ("기존부터 놓침 — 공동 로고가 옆 글자와 묶임" if r["prev_block_exact"] == "놓침"
                   else "**새 놓침** — LLM 보정이 로고를 옆 글자와 한 블록으로 묶음")
            L.append(f"| {r['image'][:-4]} | {r['bbox'][1]} | {r['prev_block_exact']} | {g_text(r['host_text'])} | {why} |")
        L += ["", "> 계획서 단계 4 근거(결과 문서 9장 한계 3 · 10장 19번) — LLM 보정이 로고를 옆 글자와 묶으면 놓침이 늘 수 있음.", ""]

    alt_p = RESULTS / "golden" / "region_exact" / "meta.json"
    if alt_p.exists():
        a = json.loads(alt_p.read_text(encoding="utf-8"))
        ac = a["counts"]
        L += ["## 6. 대안 단위 — 영역 단위 대조(`region_exact`)", "",
              "놓침 원인이 **블록 병합**이므로, 병합 앞 단계인 단계 1 OCR 영역에 같은 완전 일치 규칙을 적용해 비교함.",
              "라벨 소관 판단은 같은 기준(단계 3 정답 블록)을 씀.", "",
              "| 대조 단위 | 찾음 | 놓침 | 오탐 | 종결 기준 |", "|---|---|---|---|---|",
              f"| `block_exact` — 단계 2 블록 (확정) | {c['found']} | **{c['missed']}** | {c['false']} | {m['gate']} |",
              f"| `region_exact` — 단계 1 영역 | {ac['found']} | {ac['missed']} | **{ac['false']}** | {a['gate']} |", "",
              f"- 영역 단위는 콜라보 로고(`celimax×`)를 되찾아 **놓침 {c['missed']} → {ac['missed']}**",
              f"- 대신 **제목 첫 줄이 브랜드명인 블록에서 오탐 {ac['false']}건** — 제목 절반이 번역에서 빠짐",
              f"- `Good all goodal`은 **OCR이 한 영역으로 읽어** 영역 단위로도 못 잡음 — 병합 탓이 아님", ""]
        if a["false_hits"]:
            L += ["| 섹션 | 영역 | 텍스트 | 소속 블록 텍스트 |", "|---|---|---|---|"]
            blk = ROOT / "poc" / "golden" / "2_block_role" / "results" / "llm_assist" / "blocks"
            for h in a["false_hits"]:
                bt, bf = "—", blk / f"{h['section']}.json"
                if bf.exists() and h.get("block"):
                    bt = json.loads(bf.read_text(encoding="utf-8"))["blocks"][h["block"] - 1]["text"]
                L.append(f"| `{h['section']}` | {h.get('region', '—')} | {g_text(h['text'])} | {g_text(bt)} |")
            L.append("")
        L += ["**맞교환이 구조적임** — 단위를 키우면 로고가 옆 글자와 묶여 놓치고, 줄이면 제목이 끊겨 오탐이 남.",
              "두 단위 모두 종결 기준(놓침 ≤ 1 · 오탐 0)을 동시에 만족하지 못함.", "",
              "| | 남는 결과 | 후단 영향 |", "|---|---|---|",
              "| 놓침 | 로고가 번역 대상에 남음 | 브랜드명이 번역되거나 그대로 남음 — 검수에서 걸러짐 |",
              "| 오탐 | 제목 첫 줄이 번역에서 빠짐 | **제목이 반쪽만 번역됨** — 눈에 띄고 복구 비용이 큼 |", "",
              "→ 오탐이 더 나쁘므로 **`block_exact` 유지가 맞음.** 영역 단위는 채택하지 않음", ""]
    GOLDEN_OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {GOLDEN_OUT}  (찾음 {c['found']} · 놓침 {c['missed']} · 오탐 {c['false']} → {m['gate']})")


def main() -> None:
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", choices=("default", "golden"), default="default")
    args = ap.parse_args()
    if args.sample == "golden":
        main_golden()
    else:
        main_default()


if __name__ == "__main__":
    main()
