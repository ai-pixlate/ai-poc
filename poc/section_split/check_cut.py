"""섹션 분해 — 블록 관통 검사 · top_offset 검산.

절단선이 글자를 가르는지 센다. 섹션별 OCR 대신 **브랜드 로고 제외 과업이 만든
골든 샘플 전체 OCR 캐시**를 입력으로 읽는다(2,000px 띠 · 300px 겹침, 텍스트 추출
확정 조건). 전부 로컬, 비용 0.

검사 단위
    region   OCR 한 줄. 절단선이 가로지르면 **글자 자체가 잘림**
    block    `heuristic_v2` 줄·문단 병합 블록(poc/block_role/run.py 복사).
             가로지르면 **문단이 두 섹션으로 갈림**. 병합이 여백을 넘어 과병합한
             경우도 여기 걸리므로 hits 대지로 확인

관통 판정 — 박스가 절단선 위아래로 각각 MARGIN px 이상 걸칠 때.
OCR 박스는 글자보다 몇 px 크게 잡히므로 경계에 스친 것은 세지 않는다.

top_offset 검산
    ① 섹션이 0부터 이미지 끝까지 빈틈·겹침 없이 이어지는가
    ② top_offset == range[0]
    ③ 크롭 이미지 높이 == 섹션 높이
    ④ 섹션 안에 온전히 든 region을 크롭 로컬 좌표로 바꾼 뒤 top_offset을 더해 원본 y가 복원되는가

출력
    results/_cut_check/{variant}.json        관통 목록 · 검산 결과
    results/_cut_check/{variant}_hits.jpg    관통 사례를 절단선과 함께 잘라 모은 대지

사용법
    python check_cut.py
    python check_cut.py --variant color_snap_vlm2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
RESULTS = HERE / "results"
OCR = ROOT / "poc" / "logo_match" / "results" / "_ocr"
OUT = RESULTS / "_cut_check"

VARIANTS = ("color_snap_vlm", "color_snap_vlm2", "color_snap_ws", "gap_major", "ws_std", "ws_edge")
MARGIN = 3

# poc/block_role/run.py `heuristic_v2` — 복사
MERGE_CFG = dict(line_gap=0.7, para_gap=0.6, h_ratio=1.5, overlap=0.5, gutter=True)


# ── 병합 (poc/block_role/run.py 복사 — 역할 분류는 뺌) ─────────────────

def h_of(r: dict) -> int:
    return r["bbox"][3] - r["bbox"][1]


def v_overlap(a: list[int], b: list[int]) -> float:
    top, bot = max(a[1], b[1]), min(a[3], b[3])
    return max(0, bot - top) / max(1, min(a[3] - a[1], b[3] - b[1]))


def h_overlap(a: list[int], b: list[int]) -> float:
    left, right = max(a[0], b[0]), min(a[2], b[2])
    return max(0, right - left) / max(1, min(a[2] - a[0], b[2] - b[0]))


def union_box(boxes: list[list[int]]) -> list[int]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def gutters(regions: list[dict], width: int) -> list[tuple[int, int]]:
    cover = bytearray(width)
    for r in regions:
        x1, x2 = max(0, r["bbox"][0]), min(width, r["bbox"][2])
        for x in range(x1, x2):
            cover[x] = 1
    out, run = [], None
    for x in range(width):
        if not cover[x]:
            run = x if run is None else run
        elif run is not None:
            out.append((run, x))
            run = None
    if run is not None:
        out.append((run, width))
    min_w = max(20, width // 16)
    return [(a, b) for a, b in out if b - a >= min_w and a > 0 and b < width]


def merge_lines(regions: list[dict], cfg: dict, gut: list[tuple[int, int]]) -> list[list[int]]:
    order = sorted(range(len(regions)), key=lambda i: regions[i]["bbox"][0])
    lines: list[list[int]] = []
    for i in order:
        ri = regions[i]
        for line in lines:
            rj = regions[line[-1]]
            a, b = rj["bbox"], ri["bbox"]
            gap = b[0] - a[2]
            base = min(h_of(ri), h_of(rj))
            if v_overlap(a, b) < 0.5:
                continue
            if not (-base * 0.5 <= gap <= base * cfg["line_gap"]):
                continue
            if max(h_of(ri), h_of(rj)) / max(1, base) > cfg["h_ratio"]:
                continue
            if cfg["gutter"] and any(a[2] <= g0 and g1 <= b[0] for g0, g1 in gut):
                continue
            line.append(i)
            break
        else:
            lines.append([i])
    lines.sort(key=lambda ln: (regions[ln[0]]["bbox"][1], regions[ln[0]]["bbox"][0]))
    return lines


def merge_paragraphs(regions: list[dict], lines: list[list[int]], cfg: dict) -> list[list[int]]:
    boxes = [union_box([regions[i]["bbox"] for i in ln]) for ln in lines]
    heights = [max(h_of(regions[i]) for i in ln) for ln in lines]
    groups: list[list[int]] = []
    for k in range(len(lines)):
        for g in groups:
            j = g[-1]
            a, b = boxes[j], boxes[k]
            gap = b[1] - a[3]
            base = min(heights[j], heights[k])
            if not (-base * 0.3 <= gap <= base * cfg["para_gap"]):
                continue
            if max(heights[j], heights[k]) / max(1, base) > cfg["h_ratio"]:
                continue
            if h_overlap(a, b) < cfg["overlap"] and abs(a[0] - b[0]) > base * 0.5:
                continue
            g.append(k)
            break
        else:
            groups.append([k])
    return groups


def build_blocks(regions: list[dict], width: int) -> list[dict]:
    gut = gutters(regions, width)
    lines = merge_lines(regions, MERGE_CFG, gut)
    out = []
    for g in merge_paragraphs(regions, lines, MERGE_CFG):
        ids = [i for k in g for i in lines[k]]
        out.append({"bbox": union_box([regions[i]["bbox"] for i in ids]),
                    "text": " / ".join(" ".join(regions[i]["text"] for i in lines[k]) for k in g)})
    return out


# ── 검사 ─────────────────────────────────────────────────────────────

def crossings(units: list[dict], cuts: list[int]) -> list[dict]:
    hits = []
    for u in units:
        y0, y1 = u["bbox"][1], u["bbox"][3]
        for c in cuts:
            if y0 <= c - MARGIN and y1 >= c + MARGIN:
                hits.append({"cut": c, "bbox": u["bbox"], "text": u["text"],
                             "above": c - y0, "below": y1 - c})
    return hits


def verify_offsets(sec: dict, regions: list[dict], vdir: Path) -> list[str]:
    errs = []
    secs = sec["sections"]
    h = sec["size"][1]
    if secs[0]["range"][0] != 0 or secs[-1]["range"][1] != h:
        errs.append(f"양끝 불일치 {secs[0]['range'][0]}~{secs[-1]['range'][1]} / 높이 {h}")
    for a, b in zip(secs, secs[1:]):
        if a["range"][1] != b["range"][0]:
            errs.append(f"섹션 {a['index']}·{b['index']} 사이 빈틈/겹침 {a['range'][1]}→{b['range'][0]}")
    for s in secs:
        if s["top_offset"] != s["range"][0]:
            errs.append(f"섹션 {s['index']} top_offset {s['top_offset']} ≠ range {s['range'][0]}")
        with Image.open(vdir / s["crop"]) as im:
            if im.height != s["height"] or s["height"] != s["range"][1] - s["range"][0]:
                errs.append(f"섹션 {s['index']} 크롭 높이 {im.height} ≠ {s['height']}")
    # ④ 로컬 좌표 왕복
    for r in regions:
        y0, y1 = r["bbox"][1], r["bbox"][3]
        own = [s for s in secs if s["range"][0] <= y0 and y1 <= s["range"][1]]
        for s in own:
            local = y0 - s["top_offset"]
            if not (0 <= local <= s["height"]) or local + s["top_offset"] != y0:
                errs.append(f"region y{y0} 로컬 {local} 복원 실패")
    return errs


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hit_sheet(items: list[tuple[str, str, dict]], out: Path) -> None:
    if not items:
        return
    cw, ch, cols = 420, 230, 4
    font = _font(13)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (120, 120, 120))
    cache: dict[str, Image.Image] = {}
    for i, (stem, unit, h) in enumerate(items):
        path = next(SRC.rglob(f"{stem}.jpg"))
        if stem not in cache:
            cache[stem] = Image.open(path).convert("RGB")
        im = cache[stem]
        x0, y0, x1, y1 = h["bbox"]
        pad = 60
        box = (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))
        crop = im.crop(box)
        d = ImageDraw.Draw(crop)
        d.rectangle([x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]], outline=(20, 170, 60), width=2)
        cy = h["cut"] - box[1]
        d.line([0, cy, crop.width, cy], fill=(230, 0, 0), width=3)
        r = min((cw - 4) / crop.width, (ch - 40) / crop.height, 1.5)
        crop = crop.resize((max(1, int(crop.width * r)), max(1, int(crop.height * r))))
        tile = Image.new("RGB", (cw - 2, ch - 2), (255, 255, 255))
        tile.paste(crop, (0, 38))
        td = ImageDraw.Draw(tile)
        td.text((3, 1), f"{i} {stem[-10:]} {unit} 절단 y{h['cut']} 위{h['above']}·아래{h['below']}",
                fill=(200, 0, 0), font=font)
        td.text((3, 19), h["text"][:40], fill=(0, 0, 0), font=font)
        sheet.paste(tile, ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)


def run(variant: str) -> dict:
    vdir = RESULTS / variant
    report = {"variant": variant, "margin": MARGIN, "images": [], "totals": {}}
    items = []
    n_cuts = n_reg_hit = n_blk_hit = n_err = 0
    for sp in sorted((vdir / "sections").glob("*.json")):
        sec = json.loads(sp.read_text(encoding="utf-8"))
        stem = sp.stem
        regions = json.loads((OCR / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
        cuts = sec["cuts"]
        blocks = build_blocks(regions, sec["size"][0])
        rh, bh = crossings(regions, cuts), crossings(blocks, cuts)
        errs = verify_offsets(sec, regions, vdir)
        report["images"].append({"image": sec["image"], "cuts": len(cuts), "regions": len(regions),
                                 "blocks": len(blocks), "region_hits": rh, "block_hits": bh,
                                 "offset_errors": errs})
        items += [(stem, "region", h) for h in rh] + [(stem, "block", h) for h in bh]
        n_cuts += len(cuts)
        n_reg_hit += len(rh)
        n_blk_hit += len(bh)
        n_err += len(errs)
    report["totals"] = {"cuts": n_cuts, "region_hits": n_reg_hit, "block_hits": n_blk_hit,
                        "cuts_with_hit": len({(s, h["cut"]) for s, _, h in items}),
                        "offset_errors": n_err}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{variant}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    hit_sheet(items, OUT / f"{variant}_hits.jpg")
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all", help=f"{', '.join(VARIANTS)}, all")
    args = ap.parse_args()
    names = [v for v in VARIANTS if (RESULTS / v / "sections").exists()] if args.variant == "all" else [args.variant]

    print(f"| variant | 절단 | 관통 절단선 | region 관통 | block 관통 | top_offset 오류 |")
    for v in names:
        t = run(v)["totals"]
        print(f"| {v} | {t['cuts']} | {t['cuts_with_hit']} | {t['region_hits']} | {t['block_hits']} | {t['offset_errors']} |")
    for v in names:
        rep = json.loads((OUT / f"{v}.json").read_text(encoding="utf-8"))
        for im in rep["images"]:
            for kind in ("region_hits", "block_hits"):
                for h in im[kind]:
                    print(f"  {v:<16} {im['image']:<22} {kind[:-5]:<6} 절단 y{h['cut']:<6} "
                          f"위{h['above']:>4} 아래{h['below']:>4}  {h['text'][:50]}")
            for e in im["offset_errors"]:
                print(f"  {v:<16} {im['image']:<22} 검산 오류: {e}")


if __name__ == "__main__":
    main()
