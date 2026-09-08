"""줄·문단 병합 + 역할 분류 — variant 실행기.

사용법
    python run.py --variant heuristic_v1
    python run.py --variant all
    python run.py --variant heuristic_v1 --images 1.jpg 2.jpg

입력
    ../B_ocr/results/baseline/regions/{stem}.json   (텍스트 인식 결과)

출력
    results/{variant}/blocks/{stem}.json   블록 단위 결과
    results/{variant}/vis/{stem}.jpg       블록 박스 + role 색상 시각화
    results/{variant}/meta.json            실행 조건·집계

검증 질문
    좌표 규칙만으로 블록 1건 = 문단 1개가 성립하는가.
    제목·본문·캡션·가격·주의문구 5종을 가르는가.

판정
    사람이 vis/ 를 보고 과분할·과병합·역할 오분류 건수를 직접 센다.
    이 코드는 등급을 매기지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
SRC = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"
RESULTS = HERE / "results"

ROLES = ["제목", "본문", "캡션", "가격", "주의문구"]
ROLE_COLOR = {
    "제목": (220, 30, 30),
    "본문": (30, 90, 220),
    "캡션": (20, 150, 90),
    "가격": (235, 130, 0),
    "주의문구": (140, 60, 190),
}

# variant = 실험 조건명.
#   line_gap : 같은 줄로 볼 가로 간격 상한 (글자 높이 배수)
#   para_gap : 같은 문단으로 볼 세로 간격 상한 (줄 높이 배수)
#   h_ratio  : 병합을 허용할 글자 높이 비율 상한 (큰 글자와 잔글씨를 섞지 않기 위함)
#   overlap  : 문단 병합에 요구하는 가로 겹침 비율
#   gutter   : 세로 여백(단 경계)을 넘는 줄 병합 금지 여부
VARIANTS: dict[str, dict] = {
    "heuristic_v1": dict(line_gap=1.0, para_gap=0.8, h_ratio=2.0, overlap=0.4, gutter=False),
    # v2 — 임계를 좁히고 다단 열 분리를 켠다. v1의 과병합을 줄이는 방향.
    "heuristic_v2": dict(line_gap=0.7, para_gap=0.6, h_ratio=1.5, overlap=0.5, gutter=True),
}


# ---------------------------------------------------------------- 좌표 유틸

def h_of(r: dict) -> int:
    return r["bbox"][3] - r["bbox"][1]


def v_overlap(a: list[int], b: list[int]) -> float:
    """세로 겹침 / 짧은 쪽 높이."""
    top, bot = max(a[1], b[1]), min(a[3], b[3])
    return max(0, bot - top) / max(1, min(a[3] - a[1], b[3] - b[1]))


def h_overlap(a: list[int], b: list[int]) -> float:
    """가로 겹침 / 좁은 쪽 폭."""
    left, right = max(a[0], b[0]), min(a[2], b[2])
    return max(0, right - left) / max(1, min(a[2] - a[0], b[2] - b[0]))


def union_box(boxes: list[list[int]]) -> list[int]:
    return [
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    ]


def gutters(regions: list[dict], width: int) -> list[tuple[int, int]]:
    """세로 여백 구간 — 어느 영역도 걸치지 않는 x 구간.

    다단 레이아웃에서 좌우 단의 같은 높이 줄이 한 줄로 붙는 것을 막는 데 쓴다.
    """
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
    # 양끝 여백과 자잘한 틈은 단 경계가 아니다.
    min_w = max(20, width // 16)
    return [(a, b) for a, b in out if b - a >= min_w and a > 0 and b < width]


# ---------------------------------------------------------------- 병합

def merge_lines(regions: list[dict], cfg: dict, gut: list[tuple[int, int]]) -> list[list[int]]:
    """가로로 이어지는 영역을 한 줄로 묶는다. 반환은 region 인덱스 그룹."""
    order = sorted(range(len(regions)), key=lambda i: regions[i]["bbox"][0])
    lines: list[list[int]] = []
    for i in order:
        ri = regions[i]
        for line in lines:
            rj = regions[line[-1]]  # 줄의 오른쪽 끝과만 비교한다
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
    # 줄 자체는 위→아래, 왼→오른쪽 순으로
    lines.sort(key=lambda ln: (regions[ln[0]]["bbox"][1], regions[ln[0]]["bbox"][0]))
    return lines


def merge_paragraphs(regions: list[dict], lines: list[list[int]], cfg: dict) -> list[list[int]]:
    """세로로 이어지는 줄을 한 문단으로 묶는다. 반환은 줄 인덱스 그룹."""
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
            # 왼끝이 맞거나(좌정렬) 가로로 충분히 겹치면 같은 문단으로 본다
            if h_overlap(a, b) < cfg["overlap"] and abs(a[0] - b[0]) > base * 0.5:
                continue
            g.append(k)
            break
        else:
            groups.append([k])
    return groups


# ---------------------------------------------------------------- 역할 분류

PRICE = re.compile(r"(₩|\d[\d,]*\s*원|\d+\s*%|\d+\s*개월)")
CAUTION = re.compile(
    r"(주의|경고|유의|금지|삼가|반드시|보관|상담|문의|알레르기|이상|증상|전문의|"
    r"직사광선|어린이|사용을 중지|※)"
)


def classify(block: dict, stats: dict) -> str:
    """규칙 기반 역할 판정 — 5종.

    좌표·글자 크기만으로 가르는 것이 이 과업의 검증 대상이므로
    텍스트 패턴은 가격·주의문구 2종에만 쓴다.
    """
    text = block["text"]
    fh = block["font_h"]

    if PRICE.search(text) and len(text) <= 40:
        return "가격"
    if CAUTION.search(text):
        return "주의문구"
    if fh >= stats["h_big"] and block["n_lines"] <= 2:
        return "제목"
    if fh <= stats["h_small"] and len(text) <= 25:
        return "캡션"
    return "본문"


# ---------------------------------------------------------------- 실행

def build_blocks(regions: list[dict], cfg: dict, width: int) -> list[dict]:
    gut = gutters(regions, width) if cfg["gutter"] else []
    lines = merge_lines(regions, cfg, gut)
    groups = merge_paragraphs(regions, lines, cfg)

    heights = sorted(h_of(r) for r in regions)
    n = len(heights)
    stats = {
        "h_big": heights[int(n * 0.75)] if n else 0,
        "h_small": heights[int(n * 0.25)] if n else 0,
    }

    blocks = []
    for g in groups:
        member_lines = [lines[k] for k in g]
        ids = [i for ln in member_lines for i in ln]
        line_texts = [" ".join(regions[i]["text"] for i in ln) for ln in member_lines]
        box = union_box([regions[i]["bbox"] for i in ids])
        heights_here = sorted(h_of(regions[i]) for i in ids)
        block = {
            "bbox": box,
            "text": "\n".join(line_texts),
            "role": None,
            "font_h": heights_here[len(heights_here) // 2],
            "n_lines": len(member_lines),
            "regions": sorted(ids),
        }
        block["role"] = classify(block, stats)
        blocks.append(block)

    blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return blocks


def dump_json(path: Path, payload: dict) -> None:
    """블록 1건을 한 줄에. 본문의 줄바꿈은 \\n 으로 남는다."""
    body = ",\n  ".join(
        json.dumps(b, ensure_ascii=False, separators=(", ", ": ")) for b in payload["blocks"]
    )
    head = {k: v for k, v in payload.items() if k != "blocks"}
    lines = [
        "{",
        *(f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in head.items()),
        ' "blocks": [',
        f"  {body}" if body else "",
        " ]",
        "}",
    ]
    path.write_text("\n".join(l for l in lines if l != ""), encoding="utf-8")


def _font(size: int):
    # 역할명이 한글이라 한글 폰트를 먼저 찾는다.
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def visualize(img_path: Path, regions: list[dict], blocks: list[dict], out_path: Path) -> None:
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(13, min(img.width, img.height) // 55)
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    # 원본 인식 영역은 회색 실선 — 어디가 병합됐는지 눈으로 세기 위함
    for r in regions:
        draw.rectangle(r["bbox"], outline=(170, 170, 170), width=1)

    for i, b in enumerate(blocks, 1):
        color = ROLE_COLOR[b["role"]]
        draw.rectangle(b["bbox"], outline=color, width=3)
        x1, y1, x2, _ = b["bbox"]
        label = f"{i} {b['role']}"
        box_w = int(draw.textlength(label, font=font)) + 2 * pad

        # 라벨이 글자를 덮으면 판정을 못 한다. 위 → 왼쪽 → 오른쪽 순으로 자리를 찾는다.
        if y1 - box_h >= 0:
            left, top = x1, y1 - box_h
        elif x1 - box_w >= 0:
            left, top = x1 - box_w, y1
        else:
            left, top = min(x2, img.width - box_w), y1
        left = max(0, min(left, img.width - box_w))
        top = max(0, min(top, img.height - box_h))

        draw.rectangle([left, top, left + box_w, top + box_h], fill=color)
        draw.text((left + pad, top + pad // 2), label, fill=(255, 255, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


def run_variant(name: str, stems: list[str]) -> None:
    if name not in VARIANTS:
        raise SystemExit(f"모르는 variant: {name}. 가능: {', '.join(VARIANTS)}, all")
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    (out_dir / "blocks").mkdir(parents=True, exist_ok=True)
    (out_dir / "vis").mkdir(parents=True, exist_ok=True)

    print(f"[{name}] {cfg}")
    per_image, roles_total = [], {r: 0 for r in ROLES}
    t_all = time.perf_counter()
    for stem in stems:
        regions = json.loads((SRC / f"{stem}.json").read_text(encoding="utf-8"))["regions"]
        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        with Image.open(img_path) as im:
            width = im.width

        t0 = time.perf_counter()
        blocks = build_blocks(regions, cfg, width)
        elapsed = time.perf_counter() - t0

        dump_json(
            out_dir / "blocks" / f"{stem}.json",
            {"image": img_path.name, "variant": name, "regions_in": len(regions), "blocks": blocks},
        )
        visualize(img_path, regions, blocks, out_dir / "vis" / f"{stem}.jpg")

        counts = {r: sum(1 for b in blocks if b["role"] == r) for r in ROLES}
        for r in ROLES:
            roles_total[r] += counts[r]
        per_image.append(
            {"image": img_path.name, "regions": len(regions), "blocks": len(blocks),
             "roles": counts, "sec": round(elapsed, 3)}
        )
        tail = " ".join(f"{r}{counts[r]}" for r in ROLES if counts[r])
        print(f"  {img_path.name:<10} 영역 {len(regions):>3} → 블록 {len(blocks):>3}   {tail}")

    meta = {
        "variant": name,
        "cfg": cfg,
        "source": "poc/B_ocr/results/baseline",
        "images": len(stems),
        "total_regions": sum(p["regions"] for p in per_image),
        "total_blocks": sum(p["blocks"] for p in per_image),
        "roles": roles_total,
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 영역 {meta['total_regions']} → 블록 {meta['total_blocks']},"
          f" {meta['total_sec']}s\n")


def main() -> None:
    # 콘솔 기본 코드페이지가 cp949라 한글·기호 출력에서 죽는다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None, help="파일명 또는 stem")
    args = ap.parse_args()

    if args.images:
        stems = [Path(n).stem for n in args.images]
    else:
        stems = sorted((p.stem for p in SRC.glob("*.json")), key=lambda s: (len(s), s))
    missing = [s for s in stems if not (SRC / f"{s}.json").exists()]
    if missing:
        raise SystemExit(f"인식 결과 없음: {missing} — 텍스트 인식을 먼저 실행할 것")

    for name in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        run_variant(name, stems)


if __name__ == "__main__":
    main()
