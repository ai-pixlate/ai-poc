"""제품 라벨 판정 — LLM variant 실행기.

제품 용기·패키지에 인쇄된 글자를 배경 위 텍스트와 구분한다.
라벨로 판정된 블록은 하류에서 번역·인페인팅 대상에서 통째로 빠진다.

variant
    role_ext       텍스트 + 좌표만 준다. 역할 분류를 확장하는 방식.
    vlm_relation   원본 이미지를 함께 준다. 객체-텍스트 관계를 보게 하는 방식.

입력
    ../block_role/results/llm_assist/blocks/{stem}.json   (채택 블록)

출력
    results/{variant}/blocks/{stem}.json   is_product_label 필드 추가
    results/{variant}/vis/{stem}.jpg       라벨 판정분을 빨강, 나머지를 파랑
    results/{variant}/meta.json            토큰·비용 실측
    cache/{model}/{variant}/{stem}.json    API 응답 원본

판정
    **미탐 0 우선.** 오탐(라벨이 아닌데 라벨로 봄)은 번역이 누락돼 검수에서
    복구되지만, 미탐(라벨인데 놓침)은 제품 사진 위 글자가 지워져 복구 불가다.
    등급은 사람이 매긴다. 이 코드는 판정하지 않는다.

사용법
    python run_llm.py --variant role_ext --dry-run
    python run_llm.py --variant role_ext --images 11.jpg
    python run_llm.py --variant all
"""

from __future__ import annotations

import argparse
import base64
import io as _io
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
SRC = ROOT / "poc" / "block_role" / "results" / "llm_assist" / "blocks"
RESULTS = HERE / "results"
CACHE = HERE / "cache"

# 번역·역할 분류에서 확정된 모델. 가격은 100만 토큰당 USD (프로모션가)
MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

# 이미지를 함께 보낼 때 긴 변을 이 크기로 줄인다. 토큰을 줄이면서
# 용기 윤곽과 글자 위치 관계는 남는 수준.
VLM_MAX_SIDE = 1024

VARIANTS = {
    "role_ext": {"image": False},
    "vlm_relation": {"image": True},
}

_COMMON = """너는 화장품 상세페이지의 텍스트 블록을 두 가지로 나눈다.

**제품 라벨** — 제품 용기·튜브·파우치·종이 패키지에 **인쇄된** 글자.
  그 물건을 사진으로 찍었기 때문에 보이는 글자다.
  예) 병에 인쇄된 브랜드명·제품명·용량 표기·성분 표기

**배경 텍스트** — 페이지에 올린 글자. 디자이너가 얹은 것이다.
  예) 헤드라인, 설명 문장, 배지·버튼 안의 문구, 가격 표기

판단이 애매하면 **제품 라벨 쪽으로 답한다.** 배경 텍스트를 라벨로 잘못 보면
번역이 하나 빠질 뿐이지만, 라벨을 놓치면 제품 사진의 글자가 지워져
되돌릴 수 없다.

출력은 JSON 하나. 설명을 붙이지 않는다.
{"blocks": [{"id": 1, "is_product_label": true}, {"id": 2, "is_product_label": false}]}

입력의 모든 id가 정확히 한 번씩 나와야 한다."""

SYSTEM = {
    "role_ext": _COMMON + """

블록의 텍스트와 좌표만 준다. 이미지는 주지 않는다.
글자 내용, 크기, 서로의 위치 관계로 판단하라.""",
    "vlm_relation": _COMMON + """

원본 이미지를 함께 준다. 블록의 bbox가 이미지의 어느 자리인지 보고,
그 자리에 제품 용기가 있는지 확인한 뒤 판단하라.""",
}


# ---------------------------------------------------------------- 유틸
# block_role 과업의 것을 복사했다. 과업 간 코드는 공유하지 않는다(CLAUDE.md).

def union_box(boxes: list[list[int]]) -> list[int]:
    return [
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    ]


def _font(size: int):
    for name in ("malgun.ttf", "NanumGothic.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def dump_json(path: Path, payload: dict) -> None:
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


def visualize(img_path: Path, blocks: list[dict], out_path: Path) -> None:
    """라벨 판정분은 빨강, 배경 텍스트는 파랑. 판정 결과가 한눈에 갈리게 한다."""
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = max(13, min(img.width, img.height) // 55)
    font = _font(size)
    pad, box_h = size // 3, size + size // 2

    for i, b in enumerate(blocks, 1):
        label = b["is_product_label"]
        color = (220, 30, 30) if label else (30, 90, 220)
        draw.rectangle(b["bbox"], outline=color, width=3)
        x1, y1, x2, _ = b["bbox"]
        text = f"{i} {'라벨' if label else '배경'}"
        box_w = int(draw.textlength(text, font=font)) + 2 * pad

        if y1 - box_h >= 0:
            left, top = x1, y1 - box_h
        elif x1 - box_w >= 0:
            left, top = x1 - box_w, y1
        else:
            left, top = min(x2, img.width - box_w), y1
        left = max(0, min(left, img.width - box_w))
        top = max(0, min(top, img.height - box_h))

        draw.rectangle([left, top, left + box_w, top + box_h], fill=color)
        draw.text((left + pad, top + pad // 2), text, fill=(255, 255, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)


# ---------------------------------------------------------------- 호출

def payload(blocks: list[dict], size: tuple[int, int]) -> str:
    items = [
        {"id": i, "bbox": b["bbox"], "font_h": b["font_h"], "text": b["text"]}
        for i, b in enumerate(blocks, 1)
    ]
    return json.dumps(
        {"image_size": [size[0], size[1]], "blocks": items}, ensure_ascii=False, indent=1
    )


def image_data_url(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    if max(img.size) > VLM_MAX_SIDE:
        r = VLM_MAX_SIDE / max(img.size)
        img = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    buf = _io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def call(client, variant: str, prompt: str, img_path: Path | None):
    content: list | str = prompt
    if img_path is not None:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data_url(img_path)}},
        ]
    res = client.chat.completions.create(
        model=MODEL["model_id"],
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM[variant]},
            {"role": "user", "content": content},
        ],
    )
    usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
    return json.loads(res.choices[0].message.content), usage


def apply(blocks: list[dict], plan: dict) -> list[dict]:
    """응답을 블록에 붙인다. 계약 위반은 조용히 넘기지 않는다."""
    got = plan.get("blocks")
    if not isinstance(got, list):
        raise ValueError(f"blocks 배열 없음: {list(plan)}")
    flags: dict[int, bool] = {}
    for g in got:
        flags[int(g["id"])] = bool(g["is_product_label"])
    if sorted(flags) != list(range(1, len(blocks) + 1)):
        raise ValueError(f"id가 정확히 한 번씩 나오지 않음 — 입력 {len(blocks)}개, 응답 {sorted(flags)}")
    out = []
    for i, b in enumerate(blocks, 1):
        out.append({**b, "is_product_label": flags[i]})
    return out


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def run_variant(name: str, stems: list[str], dry: bool, no_cache: bool) -> None:
    spec = VARIANTS[name]
    out_dir = RESULTS / name
    cache_dir = CACHE / MODEL["model_id"] / name
    if not dry:
        (out_dir / "blocks").mkdir(parents=True, exist_ok=True)
        (out_dir / "vis").mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

    client = None
    if not dry:
        load_env()
        key = os.environ.get(MODEL["env_key"])
        if not key:
            raise SystemExit(f"{MODEL['env_key']} 없음 — .env 확인")
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=MODEL["base_url"])

    print(f"[{name}] 이미지 {'포함' if spec['image'] else '미포함'}")
    per_image, tok_in, tok_out, chars = [], 0, 0, 0
    t_all = time.perf_counter()

    for stem in stems:
        src = json.loads((SRC / f"{stem}.json").read_text(encoding="utf-8"))
        blocks = src["blocks"]
        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        with Image.open(img_path) as im:
            size = im.size
        prompt = payload(blocks, size)
        chars += len(prompt) + len(SYSTEM[name])

        if dry:
            extra = f"  이미지 {VLM_MAX_SIDE}px 동봉" if spec["image"] else ""
            print(f"  {img_path.name:<10} 블록 {len(blocks):>3}  프롬프트 {len(prompt):>5}자{extra}")
            continue

        cache_path = cache_dir / f"{stem}.json"
        if cache_path.exists() and not no_cache:
            c = json.loads(cache_path.read_text(encoding="utf-8"))
            plan, usage, sec, hit = c["plan"], c["usage"], 0.0, " (캐시)"
        else:
            t0 = time.perf_counter()
            plan, usage = call(client, name, prompt, img_path if spec["image"] else None)
            sec, hit = time.perf_counter() - t0, ""
            cache_path.write_text(
                json.dumps({"model": MODEL["model_id"], "variant": name, "plan": plan,
                            "usage": usage}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )

        new = apply(blocks, plan)
        tok_in += usage["in"]
        tok_out += usage["out"]
        n_label = sum(1 for b in new if b["is_product_label"])

        dump_json(
            out_dir / "blocks" / f"{stem}.json",
            {"image": img_path.name, "variant": name, "blocks_in": len(blocks),
             "labels": n_label, "blocks": new},
        )
        visualize(img_path, new, out_dir / "vis" / f"{stem}.jpg")

        per_image.append({"image": img_path.name, "blocks": len(new), "labels": n_label,
                          "tokens": usage, "sec": round(sec, 2)})
        print(f"  {img_path.name:<10} 블록 {len(new):>3}  라벨 {n_label:>3}"
              f"   in {usage['in']} out {usage['out']}{hit}")

    if dry:
        print(f"  → 텍스트 {chars:,}자. 호출 없음\n")
        return

    cost = tok_in / 1e6 * MODEL["price_in"] + tok_out / 1e6 * MODEL["price_out"]
    meta = {
        "variant": name,
        "cfg": {"model": MODEL["model_id"], "temperature": 0,
                "image": spec["image"], "image_max_side": VLM_MAX_SIDE if spec["image"] else None},
        "source": "poc/block_role/results/llm_assist",
        "images": len(per_image),
        "total_blocks": sum(p["blocks"] for p in per_image),
        "total_labels": sum(p["labels"] for p in per_image),
        "tokens": {"in": tok_in, "out": tok_out},
        "cost_usd": round(cost, 4),
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[{name}] 완료 — 블록 {meta['total_blocks']} 중 라벨 {meta['total_labels']}, "
          f"in {tok_in} out {tok_out}, ${cost:.4f}, {meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    stems = (
        [Path(n).stem for n in args.images]
        if args.images
        else sorted((p.stem for p in SRC.glob("*.json")), key=lambda s: (len(s), s))
    )
    missing = [s for s in stems if not (SRC / f"{s}.json").exists()]
    if missing:
        raise SystemExit(f"상류 블록 없음: {missing} — block_role 의 llm_assist 를 먼저 실행할 것")

    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for n in names:
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, stems, args.dry_run, args.no_cache)


if __name__ == "__main__":
    main()
