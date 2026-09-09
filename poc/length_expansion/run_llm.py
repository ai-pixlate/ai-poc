"""번역 길이 팽창률 — 번역 실행기 (유료).

폭 측정에 쓸 번역문을 만든다. 판정은 하지 않는다.

입력 2종
    block  채택 파이프라인 그대로 — `product_label`의 `vlm_relation` 블록 중
           **라벨이 아니고 한글을 포함한** 것. bbox는 블록 박스(조판 단위).
    region `poc/C_translate/evalset_ocr.json` — 인식 영역 단위. 라벨이 섞여 있고
           박스가 조판 단위와 다르다. **단위 차이가 초과율에 얼마나 영향을 주는지**
           보려고 함께 잰다.

출력
    translations/{input}.json   세그먼트별 원문·번역문·bbox
    translations/{input}.meta.json  토큰·비용 실측
    cache/{model}/{input}/{stem}.json  API 응답 원본

사용법
    python run_llm.py --input all --dry-run
    python run_llm.py --input block
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt as P  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LABELS = ROOT / "poc" / "product_label" / "results" / "vlm_relation" / "blocks"
EVALSET = ROOT / "poc" / "C_translate" / "evalset_ocr.json"
OUT = HERE / "translations"
CACHE = HERE / "cache"

MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

HANGUL = re.compile(r"[가-힣]")


def load_block_docs() -> list[dict]:
    """채택 블록에서 번역 대상만 추린다. 라벨과 한글 없는 블록은 뺀다."""
    docs = []
    for path in sorted(LABELS.glob("*.json"), key=lambda p: (len(p.stem), p.stem)):
        blocks = json.loads(path.read_text(encoding="utf-8"))["blocks"]
        segs, context = [], []
        for i, b in enumerate(blocks, 1):
            flat = b["text"].replace("\n", " ")
            context.append(flat)
            if b["is_product_label"] or not HANGUL.search(b["text"]):
                continue
            segs.append({"id": f"{path.stem}-{i:02d}", "text": flat,
                         "bbox": b["bbox"], "role": b.get("role"),
                         "src_lines": b["text"].count("\n") + 1})
        if segs:
            docs.append({"image": f"{path.stem}.jpg", "segments": segs, "page_text": context})
    return docs


def load_region_docs() -> list[dict]:
    d = json.loads(EVALSET.read_text(encoding="utf-8"))
    docs = []
    for doc in d["documents"]:
        segs = [
            {"id": s["id"], "text": s["manual_fix"] or s["source"], "bbox": s["bbox"],
             "role": None}
            for s in doc["segments"]
        ]
        docs.append({"image": doc["image"], "segments": segs, "page_text": doc["page_text"]})
    return docs


LOADERS = {"block": load_block_docs, "region": load_region_docs}


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# 글자 수 상한 = 박스가 담을 수 있는 총 가로 길이 ÷ 영문 평균 글자 폭.
# 영문 평균 글자 폭은 em의 약 0.5배로 본다(Arial 기준 근사).
def max_chars(seg: dict, src_lines: int) -> int:
    x1, y1, x2, y2 = seg["bbox"]
    em = (y2 - y1) / max(1, src_lines) * 1.35
    return max(4, round((x2 - x1) * src_lines / (0.5 * em)))


def run_input(name: str, dry: bool, no_cache: bool, pvariant: str = "default") -> None:
    docs = LOADERS[name]()
    n_seg = sum(len(d["segments"]) for d in docs)
    print(f"[{name}] 문서 {len(docs)} · 세그먼트 {n_seg}")

    client = None
    if not dry:
        load_env()
        key = os.environ.get(MODEL["env_key"])
        if not key:
            raise SystemExit(f"{MODEL['env_key']} 없음 — .env 확인")
        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=MODEL["base_url"])
        OUT.mkdir(parents=True, exist_ok=True)
        (CACHE / MODEL["model_id"]).mkdir(parents=True, exist_ok=True)

    chars, tok_in, tok_out, rows = 0, 0, 0, []
    t_all = time.perf_counter()
    for doc in docs:
        segs = []
        for s in doc["segments"]:
            item = {"id": s["id"], "text": s["text"]}
            if pvariant == "compress":
                item["max_chars"] = max_chars(s, s.get("src_lines", 1))
            segs.append(item)
        system, user = P.build(segs, doc["page_text"], pvariant)
        chars += len(system) + len(user)

        if dry:
            print(f"  {doc['image']:<8} 세그 {len(segs):>3}  프롬프트 {len(system) + len(user):>5}자")
            continue

        stem = Path(doc["image"]).stem
        cache_dir = CACHE / MODEL["model_id"] / (name if pvariant == "default"
                                                 else f"{name}_{pvariant}")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{stem}.json"
        if cache_path.exists() and not no_cache:
            c = json.loads(cache_path.read_text(encoding="utf-8"))
            payload, usage, hit = c["payload"], c["usage"], " (캐시)"
        else:
            res = client.chat.completions.create(
                model=MODEL["model_id"],
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            payload = json.loads(res.choices[0].message.content)
            usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
            cache_path.write_text(
                json.dumps({"model": MODEL["model_id"], "payload": payload, "usage": usage},
                           ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            hit = ""

        got = {t["id"]: t["translation"] for t in payload.get("translations", [])}
        missing = [s["id"] for s in doc["segments"] if s["id"] not in got]
        if missing:
            raise ValueError(f"{doc['image']} 번역 누락: {missing}")
        for s in doc["segments"]:
            rows.append({**s, "image": doc["image"], "target": got[s["id"]]})

        tok_in += usage["in"]
        tok_out += usage["out"]
        print(f"  {doc['image']:<8} 세그 {len(segs):>3}  in {usage['in']} out {usage['out']}{hit}")

    if dry:
        print(f"  → 총 {chars:,}자. 호출 없음\n")
        return

    out_name = name if pvariant == "default" else f"{name}_{pvariant}"
    cost = tok_in / 1e6 * MODEL["price_in"] + tok_out / 1e6 * MODEL["price_out"]
    (OUT / f"{out_name}.json").write_text(
        json.dumps({"input": out_name, "prompt": pvariant, "model": MODEL["model_id"],
                    "segments": rows},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (OUT / f"{out_name}.meta.json").write_text(
        json.dumps({"input": out_name, "prompt": pvariant,
                    "model": MODEL["model_id"], "documents": len(docs),
                    "segments": len(rows), "tokens": {"in": tok_in, "out": tok_out},
                    "cost_usd": round(cost, 4),
                    "total_sec": round(time.perf_counter() - t_all, 2),
                    "prompt_rule_4": pvariant,
                    "run_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"[{out_name}] 완료 — 세그먼트 {len(rows)}, in {tok_in} out {tok_out}, ${cost:.4f}\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="block, region, all")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--prompt", default="default", help="default 또는 compress")
    args = ap.parse_args()

    names = list(LOADERS) if args.input == "all" else [args.input]
    for n in names:
        if n not in LOADERS:
            raise SystemExit(f"모르는 입력: {n}. 가능: {', '.join(LOADERS)}, all")
        run_input(n, args.dry_run, args.no_cache, args.prompt)


if __name__ == "__main__":
    main()
