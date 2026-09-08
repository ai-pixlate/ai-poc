"""줄·문단 병합 + 역할 분류 — `llm_assist` variant 실행기.

휴리스틱 결과를 LLM이 보정한다. 좌표 규칙이 만든 블록 목록을 주고
① 같은 문단인데 갈린 것을 묶고 ② 역할 5종을 다시 매기게 한다.

**분할은 시키지 않는다.** 판정 실측에서 과분할 3건 / 과병합 1건으로
부족한 쪽이 병합이었다. 분할까지 열면 실패 축이 섞여 원인이 안 갈린다.

입력
    results/heuristic_v2/blocks/{stem}.json   (채택 후보 variant)

출력
    results/llm_assist/blocks/{stem}.json     보정 결과 (형식 동일)
    results/llm_assist/vis/{stem}.jpg
    results/llm_assist/meta.json              토큰·비용 실측 포함
    cache/{model}/{stem}.json                 API 응답 원본

사용법
    python run_llm.py --images 6.jpg      # 선실측 1장
    python run_llm.py                     # 전체
    python run_llm.py --dry-run           # 호출 없이 프롬프트 크기만 잰다
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as H  # noqa: E402  — 시각화·덤프를 그대로 쓴다

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMAGES = ROOT / "data" / "images"
RESULTS = HERE / "results"
SRC = RESULTS / "heuristic_v2" / "blocks"
CACHE = HERE / "cache"
VARIANT = "llm_assist"

# 번역 과업에서 확정된 모델. 가격은 100만 토큰당 USD (프로모션가, 2026-12-31까지)
MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

SYSTEM = """너는 화장품 상세페이지의 텍스트 블록을 정리한다.

좌표 규칙이 1차로 묶은 블록 목록을 준다. 두 가지를 한다.

1. 같은 문단인데 갈린 블록을 묶는다.
   - 이어 읽어야 뜻이 사는 것, 같은 배지·박스 안에 있는 것을 묶는다.
   - 서로 다른 배경·도형 위에 있으면 묶지 않는다.
   - **블록을 쪼개지는 않는다.** 주어진 블록이 최소 단위다.

2. 역할을 매긴다. 다섯 가지만 쓴다.
   - 제목: 그 구간을 대표하는 문구. 없으면 무슨 얘긴지 모른다. 서술어가 없다.
   - 본문: 설명 문장.
   - 캡션: 이미지·아이콘·제품에 딸린 짧은 부속 문구.
   - 가격: 통화·할인율처럼 값이 현지화 규칙을 타는 것. `1+1` 같은 판촉 표기는 제목이다.
   - 주의문구: 안전·규제·사용상 경고.

제품 용기나 패키지에 인쇄된 글자도 위 다섯 중 하나로 매긴다. 별도 유형을 만들지 않는다.

출력은 JSON 하나. 설명을 붙이지 않는다.
{"blocks": [{"members": [1, 2], "role": "제목"}, {"members": [3], "role": "본문"}]}

members는 입력 블록 번호다. 입력의 모든 번호가 정확히 한 번씩 나와야 한다."""


def payload(blocks: list[dict], size: tuple[int, int]) -> str:
    items = []
    for i, b in enumerate(blocks, 1):
        items.append(
            {
                "id": i,
                "bbox": b["bbox"],
                "font_h": b["font_h"],
                "text": b["text"],
            }
        )
    return json.dumps(
        {"image_size": [size[0], size[1]], "blocks": items}, ensure_ascii=False, indent=1
    )


def call(client, prompt: str) -> tuple[dict, dict]:
    res = client.chat.completions.create(
        model=MODEL["model_id"],
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    usage = {
        "in": res.usage.prompt_tokens,
        "out": res.usage.completion_tokens,
    }
    return json.loads(res.choices[0].message.content), usage


def apply(blocks: list[dict], plan: dict) -> list[dict]:
    """LLM 응답을 블록에 적용한다. 계약 위반은 조용히 넘기지 않는다."""
    groups = plan.get("blocks")
    if not isinstance(groups, list):
        raise ValueError(f"blocks 배열 없음: {list(plan)}")

    seen: list[int] = []
    out = []
    for g in groups:
        ids = [int(x) for x in g["members"]]
        role = g["role"]
        if role not in H.ROLES:
            raise ValueError(f"모르는 역할: {role}")
        seen += ids
        members = [blocks[i - 1] for i in ids]
        box = H.union_box([m["bbox"] for m in members])
        regions = sorted(r for m in members for r in m["regions"])
        hs = sorted(m["font_h"] for m in members)
        out.append(
            {
                "bbox": box,
                "text": "\n".join(m["text"] for m in members),
                "role": role,
                "font_h": hs[len(hs) // 2],
                "n_lines": sum(m["n_lines"] for m in members),
                "regions": regions,
                "from": ids,
            }
        )
    if sorted(seen) != list(range(1, len(blocks) + 1)):
        raise ValueError(
            f"입력 블록이 정확히 한 번씩 나오지 않음 — 입력 {len(blocks)}개, 응답 {sorted(seen)}"
        )
    out.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return out


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true", help="호출 없이 프롬프트 크기만 잰다")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    stems = (
        [Path(n).stem for n in args.images]
        if args.images
        else sorted((p.stem for p in SRC.glob("*.json")), key=lambda s: (len(s), s))
    )
    cache_dir = CACHE / MODEL["model_id"]
    out_dir = RESULTS / VARIANT
    if not args.dry_run:
        (out_dir / "blocks").mkdir(parents=True, exist_ok=True)
        (out_dir / "vis").mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

    client = None
    if not args.dry_run:
        load_env()
        key = os.environ.get(MODEL["env_key"])
        if not key:
            raise SystemExit(f"{MODEL['env_key']} 없음 — .env 확인")
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=MODEL["base_url"])

    per_image, tok_in, tok_out, chars = [], 0, 0, 0
    roles_total = {r: 0 for r in H.ROLES}
    t_all = time.perf_counter()

    for stem in stems:
        src = json.loads((SRC / f"{stem}.json").read_text(encoding="utf-8"))
        blocks = src["blocks"]
        img_path = next(p for p in IMAGES.iterdir() if p.stem == stem)
        with Image.open(img_path) as im:
            size = im.size
        prompt = payload(blocks, size)
        chars += len(prompt) + len(SYSTEM)

        if args.dry_run:
            print(f"  {img_path.name:<10} 블록 {len(blocks):>3}  프롬프트 {len(prompt):>5}자")
            continue

        cache_path = cache_dir / f"{stem}.json"
        if cache_path.exists() and not args.no_cache:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            plan, usage, sec = cached["plan"], cached["usage"], 0.0
            hit = " (캐시)"
        else:
            t0 = time.perf_counter()
            plan, usage = call(client, prompt)
            sec = time.perf_counter() - t0
            cache_path.write_text(
                json.dumps(
                    {"model": MODEL["model_id"], "plan": plan, "usage": usage},
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
            hit = ""

        new = apply(blocks, plan)
        tok_in += usage["in"]
        tok_out += usage["out"]

        H.dump_json(
            out_dir / "blocks" / f"{stem}.json",
            {
                "image": img_path.name,
                "variant": VARIANT,
                "regions_in": src["regions_in"],
                "blocks": new,
            },
        )
        regions = json.loads(
            (ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions" / f"{stem}.json")
            .read_text(encoding="utf-8")
        )["regions"]
        H.visualize(img_path, regions, new, out_dir / "vis" / f"{stem}.jpg")

        counts = {r: sum(1 for b in new if b["role"] == r) for r in H.ROLES}
        for r in H.ROLES:
            roles_total[r] += counts[r]
        per_image.append(
            {
                "image": img_path.name,
                "regions": src["regions_in"],
                "blocks": len(new),
                "from_blocks": len(blocks),
                "roles": counts,
                "tokens": usage,
                "sec": round(sec, 2),
            }
        )
        tail = " ".join(f"{r}{counts[r]}" for r in H.ROLES if counts[r])
        print(
            f"  {img_path.name:<10} 블록 {len(blocks):>3} → {len(new):>3}   {tail}"
            f"   in {usage['in']} out {usage['out']}{hit}"
        )

    if args.dry_run:
        print(f"\n총 {chars:,}자 (system 포함). 호출 없음")
        return

    cost = tok_in / 1e6 * MODEL["price_in"] + tok_out / 1e6 * MODEL["price_out"]
    meta = {
        "variant": VARIANT,
        "cfg": {"model": MODEL["model_id"], "temperature": 0, "source": "heuristic_v2"},
        "source": "poc/block_role/results/heuristic_v2",
        "images": len(per_image),
        "total_regions": sum(p["regions"] for p in per_image),
        "total_blocks": sum(p["blocks"] for p in per_image),
        "roles": roles_total,
        "tokens": {"in": tok_in, "out": tok_out},
        "cost_usd": round(cost, 4),
        "total_sec": round(time.perf_counter() - t_all, 2),
        "per_image": per_image,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        f"[{VARIANT}] 완료 — 블록 {meta['total_blocks']}, "
        f"in {tok_in} out {tok_out}, ${cost:.4f}, {meta['total_sec']}s"
    )


if __name__ == "__main__":
    main()
