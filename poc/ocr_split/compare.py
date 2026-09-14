"""긴 이미지 분할 경계 — 비교기.

정답 OCR이 없으므로 **다른 분할 방식을 참조로** 삼는다. 어떤 이음선 근처의 글자는,
그 자리가 조각 한가운데인 다른 variant에서는 온전히 읽혔을 것이다.

이음선 대조 (variant V의 이음선 c마다)
    참조 = c에서 가장 가까운 조각 경계가 REF_CLEAR px 이상 떨어진 다른 variant
           (full_page 제외 — 축소돼 참조로 못 씀). 우선순위 REF_ORDER
    참조 region 중 c를 가로지르는 것(위아래로 각 3px 이상)을 V에서 찾음
        온전   V에 IoU ≥ 0.5 region이 있음
        잘림   겹치는 region은 있으나 IoU < 0.5 — 조각에 걸려 반쪽만 읽힘
        누락   겹치는 region이 없음

기계 집계
    경계 닿음   조각 위아래 경계에 닿은 region 수 — 잘림 의심
    중복        같은 텍스트 · IoU > 0.5 인 region 쌍
    전체 일치율 기준 variant(`tile_2000_ov300`) region 중 IoU ≥ 0.5로 찾은 비율.
               기준 자신은 `unit_ws_std`와 대조. 축소 영향을 봄

출력
    summary.md
    results/_issues/{variant}.jpg   잘림·누락 사례 — 빨강 이음선 · 초록 참조 · 주황 V

사용법
    python compare.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

VARIANTS = ("full_page", "tile_2000", "tile_2000_ov300", "unit_ws_std", "section_vlm2")
REF_ORDER = ("unit_ws_std", "tile_2000_ov300", "section_vlm2", "tile_2000")
BASE = "tile_2000_ov300"
REF_CLEAR = 300
CROSS = 3


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", s).lower())


def iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def load(v: str, stem: str) -> dict:
    return json.loads((RESULTS / v / "regions" / f"{stem}.json").read_text(encoding="utf-8"))


def edges(d: dict) -> list[int]:
    return sorted({t for t, _ in d["chunks"][1:]} | {b for _, b in d["chunks"][:-1]})


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sheet(items: list[dict], out: Path) -> None:
    if not items:
        return
    cw, ch, cols = 420, 240, 4
    font = _font(13)
    rows = (len(items) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cw, rows * ch), (120, 120, 120))
    cache: dict[str, Image.Image] = {}
    for i, it in enumerate(items):
        if it["stem"] not in cache:
            cache[it["stem"]] = Image.open(next(SRC.rglob(f"{it['stem']}.jpg"))).convert("RGB")
        im = cache[it["stem"]]
        rx0, ry0, rx1, ry1 = it["ref"]["bbox"]
        pad = 50
        box = (max(0, rx0 - pad), max(0, ry0 - pad), min(im.width, rx1 + pad), min(im.height, ry1 + pad))
        crop = im.crop(box)
        d = ImageDraw.Draw(crop)
        d.rectangle([rx0 - box[0], ry0 - box[1], rx1 - box[0], ry1 - box[1]], outline=(20, 170, 60), width=2)
        for m in it["got"]:
            x0, y0, x1, y1 = m["bbox"]
            d.rectangle([x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]], outline=(240, 140, 0), width=2)
        d.line([0, it["seam"] - box[1], crop.width, it["seam"] - box[1]], fill=(230, 0, 0), width=2)
        r = min((cw - 4) / crop.width, (ch - 40) / crop.height, 1.5)
        crop = crop.resize((max(1, int(crop.width * r)), max(1, int(crop.height * r))))
        tile = Image.new("RGB", (cw - 2, ch - 2), (255, 255, 255))
        tile.paste(crop, (0, 38))
        td = ImageDraw.Draw(tile)
        td.text((3, 1), f"{i} {it['stem'][-10:]} {it['kind']} 이음선 y{it['seam']} (참조 {it['ref_v']})",
                fill=(200, 0, 0), font=font)
        got = " | ".join(m["text"] for m in it["got"])[:34]
        td.text((3, 19), f"참조「{it['ref']['text'][:14]}」 V「{got}」", fill=(0, 0, 0), font=font)
        canvas.paste(tile, ((i % cols) * cw, (i // cols) * ch))
    canvas.save(out, quality=88)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    names = [v for v in VARIANTS if (RESULTS / v / "meta.json").exists()]
    metas = {v: json.loads((RESULTS / v / "meta.json").read_text(encoding="utf-8")) for v in names}
    stems = [Path(p["image"]).stem for p in metas[names[0]]["per_image"]]
    data = {v: {s: load(v, s) for s in stems} for v in names}
    heights = {s: data[names[0]][s]["height"] for s in stems}

    rows, issues_by_v, seam_detail = {}, {}, {}
    for v in names:
        n_seam = n_cross = n_ok = n_cut = n_miss = n_touch = n_dup = 0
        issues = []
        for s in stems:
            d = data[v][s]
            regs = d["regions"]
            n_touch += sum(1 for r in regs if r["edge_touch"])
            for i in range(len(regs)):
                for j in range(i + 1, len(regs)):
                    if norm(regs[i]["text"]) and norm(regs[i]["text"]) == norm(regs[j]["text"]) \
                            and iou(regs[i]["bbox"], regs[j]["bbox"]) > 0.5:
                        n_dup += 1
            for c in d["seams"]:
                n_seam += 1
                ref_v = next((r for r in REF_ORDER if r != v and r in names and
                              all(abs(c - e) >= REF_CLEAR for e in edges(data[r][s]))), None)
                if ref_v is None:
                    continue
                for rr in data[ref_v][s]["regions"]:
                    y0, y1 = rr["bbox"][1], rr["bbox"][3]
                    if not (y0 <= c - CROSS and y1 >= c + CROSS):
                        continue
                    n_cross += 1
                    over = [m for m in regs if iou(m["bbox"], rr["bbox"]) > 0]
                    if any(iou(m["bbox"], rr["bbox"]) >= 0.5 for m in over):
                        n_ok += 1
                        continue
                    kind = "잘림" if over else "누락"
                    n_cut += kind == "잘림"
                    n_miss += kind == "누락"
                    issues.append({"stem": s, "seam": c, "ref_v": ref_v, "ref": rr, "got": over, "kind": kind})
        # 전체 일치율
        ref_for = "unit_ws_std" if v == BASE else BASE
        tot = hit = 0
        long_tot = long_hit = 0
        if ref_for in names:
            for s in stems:
                ref = data[ref_for][s]["regions"]
                mine = data[v][s]["regions"]
                for rr in ref:
                    ok = any(iou(m["bbox"], rr["bbox"]) >= 0.5 for m in mine)
                    tot += 1
                    hit += ok
                    if heights[s] > 4000:
                        long_tot += 1
                        long_hit += ok
        m = metas[v]
        rows[v] = {"chunks": sum(p["chunks"] for p in m["per_image"]),
                   "max_chunk": max(p["max_chunk"] for p in m["per_image"]),
                   "regions": m["total_regions"], "sec": m["total_sec"],
                   "seams": n_seam, "cross": n_cross, "ok": n_ok, "cut": n_cut, "miss": n_miss,
                   "touch": n_touch, "dup": n_dup, "ref_for": ref_for,
                   "match": hit / tot if tot else 0, "long_match": long_hit / long_tot if long_tot else 0}
        issues_by_v[v] = issues
        (RESULTS / "_issues").mkdir(parents=True, exist_ok=True)
        sheet(issues, RESULTS / "_issues" / f"{v}.jpg")

    long_imgs = [s for s in stems if heights[s] > 4000]
    L = ["# 긴 이미지 분할 경계 — 실행 결과", "",
         "> `compare.py`가 생성함. 골든 샘플 34장 · 비용 0. 판정 칸은 아래 사례 대지를 보고 채움.",
         "> 검출기 입력 긴 변 상한 **4,000px** — 넘으면 통째로 축소됨.",
         "> **별도 과업 아님** — 섹션 분해 부속 확인. 결론은 `PoC_추가검증_결과.md` 5장 · 10장 27번.", "",
         "## 1. 분할 방식", "",
         "| variant | 방식 | 조각 | 최대 조각 | region | 소요 |", "|---|---|---|---|---|---|"]
    how = {"full_page": "자르지 않음", "tile_2000": "2,000px 띠 · 겹침 없음",
           "tile_2000_ov300": "2,000px 띠 · 300px 겹침 · 중심 규칙",
           "unit_ws_std": "여백마다(`ws_std` 처리 단위)", "section_vlm2": "의미 섹션(`color_snap_vlm2`)"}
    for v in names:
        r = rows[v]
        L.append(f"| `{v}` | {how[v]} | {r['chunks']} | {r['max_chunk']:,}px | {r['regions']:,} | {r['sec']}s |")
    errs = [(v, s, e) for v in names for s in stems for e in data[v][s].get("errors", [])]
    if errs:
        L += ["", "**실행 오류** — 조각을 읽지 못해 region 0으로 셈.", "",
              "| variant | 이미지 | 조각 범위 | 오류 |", "|---|---|---|---|"]
        for v, s, e in errs:
            L.append(f"| `{v}` | {s} | {e['range'][0]:,}~{e['range'][1]:,}px | `{e['error']}` |")
    L += ["", "## 2. 이음선 대조 (기계 집계)", "",
          f"이음선마다 **그 자리가 조각 한가운데인 다른 variant**(경계에서 {REF_CLEAR}px 이상)를 참조로 삼아, "
          "이음선을 가로지르는 참조 글자를 찾음.", "",
          "| variant | 이음선 | 가로지르는 참조 글자 | 온전 | **잘림** | **누락** | 경계 닿음 | 중복 |",
          "|---|---|---|---|---|---|---|---|"]
    for v in names:
        r = rows[v]
        L.append(f"| `{v}` | {r['seams']} | {r['cross']} | {r['ok']} | **{r['cut']}** | **{r['miss']}** | "
                 f"{r['touch']} | {r['dup']} |")
    L += ["", "- **잘림** = 겹치는 region은 있으나 IoU < 0.5 — 반쪽만 읽힘",
          "- **누락** = 겹치는 region 없음", "- **경계 닿음** = 조각 위아래 끝 2px 안에 닿은 region — 잘림 의심",
          "- **중복** = 같은 텍스트 · IoU > 0.5 쌍", "",
          "## 3. 전체 일치율 (기계 집계 — 축소 영향)", "",
          f"기준 `{BASE}` region을 IoU ≥ 0.5로 찾은 비율. 기준 자신은 `unit_ws_std`와 대조. "
          f"4,000px 초과 이미지 {len(long_imgs)}장은 따로 봄.", "",
          "| variant | 대조 대상 | 전체 | 4,000px 초과 이미지 |", "|---|---|---|---|"]
    for v in names:
        r = rows[v]
        L.append(f"| `{v}` | `{r['ref_for']}` | {r['match']:.1%} | {r['long_match']:.1%} |")
    L += ["", "## 4. 사례 판정", "",
          "`results/_issues/{variant}.jpg` — 빨강 이음선 · 초록 참조 region · 주황 이 variant region. "
          "**채울 칸은 `실제 문제`**(글자가 실제로 잘리거나 빠졌으면 O, 참조 쪽 오검출·박스 크기 차이면 X).", "",
          "| variant | # | 이미지 | 이음선 y | 유형 | 참조 텍스트 | 이 variant 텍스트 | 실제 문제 |",
          "|---|---|---|---|---|---|---|---|"]
    for v in names:
        for i, it in enumerate(issues_by_v[v]):
            got = " / ".join(m["text"].replace("|", "/") for m in it["got"]) or "—"
            L.append(f"| `{v}` | {i} | {it['stem']} | {it['seam']} | {it['kind']} | "
                     f"{it['ref']['text'].replace('|', '/')} | {got} |  |")
    L.append("")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"작성: {OUT}")
    for v in names:
        r = rows[v]
        print(f"  {v:<16} 이음선 {r['seams']:>3} 가로지름 {r['cross']:>3} 온전 {r['ok']:>3} 잘림 {r['cut']:>3} "
              f"누락 {r['miss']:>3} 닿음 {r['touch']:>3} 중복 {r['dup']:>2} 일치 {r['match']:.1%} 긴 {r['long_match']:.1%}")


if __name__ == "__main__":
    main()
