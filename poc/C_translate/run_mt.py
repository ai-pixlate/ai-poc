"""C. 로컬라이징 번역 — 번역 전용 모델 참고 측정.

⚠️ **벤치마크 후보가 아니다.** 문서 2.3의 과업은 "범용 LLM 선정"이고 D(규제 판단)가
   통합돼 있다. Qwen-MT는 그 조건을 못 맞춘다.

    - 시스템 프롬프트 불가 → prompts.py를 쓸 수 없음 (문서에 명시된 제약)
    - JSON 구조화 출력 불가 → 해당 평가 축 N/A
    - 세그먼트 단위 호출 → 같은 페이지 문맥을 함께 넘길 수 없음

   그래도 재는 이유: 전용 모델의 번역 품질·비용·속도를 알아야 "번역과 규제 판단을
   두 단계로 분리하는 설계"를 검토할 수 있다. 결과는 반드시 **참고 측정**으로 분리 표기.

규제 표는 이 모델의 고유 기능인 `terms`(용어집)로 전달한다. 프롬프트로 지시할 수
없으므로 이것이 유일한 경로이며, 다른 후보와 조건이 다르다는 점을 감안할 것.

사용법
    python run_mt.py                 # dry-run
    python run_mt.py --execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import config
from run import load_env

HERE = Path(__file__).resolve().parent
MODEL_ID = "qwen-mt-plus"
OUT_NAME = "qwen_mt_ref"        # _ref = 참고 측정. 벤치마크 폴더와 구분
SRC_LANG, TGT_LANG = "Korean", "English"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evalset", default="evalset.json")
    ap.add_argument("--execute", action="store_true", help="실제 API 호출 (비용 발생)")
    args = ap.parse_args()

    ev = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))
    n_seg = ev["counts"]["segments"]
    cache_dir = HERE / "cache" / OUT_NAME
    out_dir = HERE / "results" / OUT_NAME

    terms = [{"source": r["금지표현"], "target": r["대체표현"]}
             for r in (config.REGULATION_TABLE or [])]
    # 용어집이 바뀌면 옛 번역을 재사용하면 안 된다. run.py와 같은 방식으로 지문을 둔다.
    terms_fp = hashlib.sha256(
        json.dumps(terms, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    # 집계도 지문을 확인한다. 파일 존재만 세면 용어집을 고친 뒤
    # "캐시 64건"이라 해놓고 실제로는 89건을 호출하는 어긋남이 생긴다.
    n_cached = sum(
        1 for s in (x for d in ev["documents"] for x in d["segments"])
        if (cache_dir / f"{s['id']}.json").exists()
        and json.loads((cache_dir / f"{s['id']}.json").read_text(encoding="utf-8")).get("terms_fp") == terms_fp
    )

    print(f"[{OUT_NAME}] {MODEL_ID}")
    print(f"  세그먼트 {n_seg}개 — 캐시 {n_cached}건, 호출 필요 {n_seg - n_cached}건")
    print(f"  {SRC_LANG} → {TGT_LANG}, 규제 표는 terms 용어집으로 전달")
    print("  ⚠️ 참고 측정 — 벤치마크 후보 아님 (시스템 프롬프트·JSON 출력 불가)")

    if not args.execute:
        print("\n--dry-run (기본). 호출하려면 --execute")
        return

    load_env()
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise SystemExit("DASHSCOPE_API_KEY 없음. .env에 넣을 것")

    from openai import OpenAI, RateLimitError

    client = OpenAI(api_key=key, base_url=config.MODELS["qwen"]["base_url"], timeout=180)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    ti = to = 0
    t_all = time.perf_counter()
    for doc in ev["documents"]:
        stem = Path(doc["image"]).stem
        rows = []
        for s in doc["segments"]:
            cp = cache_dir / f"{s['id']}.json"
            p = None
            if cp.exists():
                prev = json.loads(cp.read_text(encoding="utf-8"))
                if prev.get("terms_fp") == terms_fp:
                    p = prev
            if p is None:
                text = s["manual_fix"] or s["source"]
                t0 = time.perf_counter()
                # 세그먼트 단위라 호출이 89회다. 연속 호출은 레이트 리밋에 걸리므로
                # 429일 때만 지수 백오프로 재시도한다.
                r = None
                for attempt in range(6):
                    try:
                        r = client.chat.completions.create(
                            model=MODEL_ID,
                            messages=[{"role": "user", "content": text}],
                            extra_body={"translation_options": {
                                "source_lang": SRC_LANG, "target_lang": TGT_LANG, "terms": terms}},
                        )
                        break
                    except RateLimitError:
                        wait = 2 ** attempt
                        print(f"    레이트 리밋 — {wait}s 대기 후 재시도 ({attempt + 1}/6)")
                        time.sleep(wait)
                if r is None:
                    raise SystemExit(f"재시도 한도 초과: {s['id']}")
                u = r.usage
                p = {"translation": r.choices[0].message.content or "",
                     "usage": {"input": u.prompt_tokens, "output": u.completion_tokens},
                     "sec": round(time.perf_counter() - t0, 2),
                     "terms_fp": terms_fp}
                cp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
            ti += p["usage"]["input"]
            to += p["usage"]["output"]
            rows.append({"id": s["id"], "translation": p["translation"], "note": ""})
        (out_dir / f"{stem}.json").write_text(json.dumps({
            "image": doc["image"], "model": OUT_NAME,
            "kind": "참고 측정 — 벤치마크 후보 아님",
            "model_id": MODEL_ID, "translations": rows,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {stem:<18} {len(rows)}건")

    elapsed = time.perf_counter() - t_all
    q = config.MODELS["qwen"]
    # qwen-mt-plus 단가는 문서에 공개돼 있지 않다. qwen3.8-max 단가로 상한을 잡는다.
    cost = ti / 1e6 * q["price_in"] + to / 1e6 * q["price_out"]
    meta = {"model_id": MODEL_ID, "kind": "참고 측정",
            "segments": n_seg, "input_tokens": ti, "output_tokens": to,
            "total_sec": round(elapsed, 1),
            "cost_upper_bound_usd": round(cost, 4),
            "cost_note": "qwen-mt-plus 단가 미공개. qwen3.8-max 단가($2/$6)로 계산한 상한",
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n입력 {ti:,} · 출력 {to:,} · 소요 {elapsed:.0f}s")
    print(f"비용 상한 {cost:.4f}$ (단가 미공개, qwen3.8-max 기준 추정)")


if __name__ == "__main__":
    main()
