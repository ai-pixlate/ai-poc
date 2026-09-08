"""C. 로컬라이징 번역 — 번역 실행기.

사용법
    python run.py --model claude                          # 기본 dry-run. 건수만 확인
    python run.py --model claude --execute                # 실제 호출 (비용 발생)
    python run.py --model claude --variant v1_exception   # 프롬프트 변형별 분리 저장

출력
    results/{variant}/{model}/{stem}.json   번역 결과
    cache/{model}/{stem}.json               API 응답 캐시 (v0_baseline)
    cache/{variant}/{model}/{stem}.json     API 응답 캐시 (그 외 variant)

안전장치
    - 기본이 --dry-run이다. --execute를 명시해야 호출한다.
    - config의 미확정 항목이 남아 있으면 --execute를 거부한다.
    - 캐시가 있으면 호출하지 않는다 (CLAUDE.md: API 응답은 로컬 캐싱, 재실행 시 캐시 우선).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

import config
import prompts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_env() -> None:
    """.env를 읽어 환경변수에 넣는다. 키는 여기서만 온다 — 하드코딩 금지."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def prompt_fingerprint(system: str, user: str) -> str:
    """프롬프트 지문. 규제 표나 프롬프트 문안이 바뀌면 캐시를 무효화해야 한다.

    파일명만으로 캐시하면 규제 표를 고친 뒤에도 옛 번역을 재사용해,
    '어떤 표로 만든 결과인지' 알 수 없게 된다.
    """
    return hashlib.sha256((system + "\x00" + user).encode("utf-8")).hexdigest()[:16]


def extract_json(text: str) -> dict:
    """모델이 코드펜스나 군더더기를 붙여도 JSON 본문을 건진다."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:200]}")
    return json.loads(m.group(0))


def call_anthropic(model_id: str, system: str, user: str) -> tuple[str, dict]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model_id,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    return text, usage


def call_openai(model_id: str, system: str, user: str,
                base_url: str | None = None, api_key_env: str = "OPENAI_API_KEY",
                extra_body: dict | None = None) -> tuple[str, dict]:
    """OpenAI 및 OpenAI 호환 엔드포인트(DashScope 등) 공용.

    extra_body — 벤더 고유 파라미터. DashScope의 `enable_thinking`이 여기로 간다.
    ⚠️ 이걸 쓰면 **타 벤더와 조건이 달라진다.** 결과 표에 반드시 별도 표기할 것.
    """
    import os

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get(api_key_env), base_url=base_url) if base_url else OpenAI()
    kw = {"extra_body": extra_body} if extra_body else {}
    resp = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        **kw,
    )
    text = resp.choices[0].message.content or ""
    u = resp.usage
    usage = {"input": u.prompt_tokens, "output": u.completion_tokens} if u else {}
    return text, usage


def call_model(name: str, system: str, user: str) -> tuple[str, dict]:
    spec = config.MODELS[name]
    if spec["model_id"] is None:
        raise SystemExit(f"[{name}] model_id 미정 — config.MODELS를 채울 것")
    if spec["vendor"] == "anthropic":
        return call_anthropic(spec["model_id"], system, user)
    if spec["vendor"] == "openai":
        return call_openai(spec["model_id"], system, user)
    if spec["vendor"] in ("alibaba", "google"):
        # DashScope·Gemini 모두 OpenAI 호환 API를 제공하므로 같은 클라이언트를 쓴다.
        return call_openai(spec["model_id"], system, user,
                           base_url=spec["base_url"], api_key_env=spec["env_key"],
                           extra_body=spec.get("extra_body"))
    raise NotImplementedError(
        f"[{name}] {spec['vendor']} 어댑터 미구현.\n"
        "  키 확보 시점에 해당 벤더 SDK를 확인하고 여기에 추가할 것.\n"
        "  검증 없이 미리 적으면 틀린 코드가 남는다."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(config.MODELS))
    ap.add_argument("--evalset", default="evalset.json")
    ap.add_argument("--execute", action="store_true", help="실제 API 호출 (비용 발생)")
    ap.add_argument("--target-lang", default=None)
    ap.add_argument("--variant", default="v0_baseline",
                    help="프롬프트 변형 이름. 결과를 results/{variant}/{model}/ 에 분리 저장")
    ap.add_argument("--docs", nargs="*", default=None,
                    help="문서 일부만 실행 (선실측용). 예: --docs 09_regulation_edge")
    args = ap.parse_args()

    target = args.target_lang or config.TARGET_LANG
    missing = config.missing_settings()

    data = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))
    docs = data["documents"]

    # 신규 모델은 1문서만 먼저 돌려 출력 길이를 실측한 뒤 전체를 추정한다.
    # 문자수 근사 추정은 `qwen3.8-max`에서 543% 빗나갔다 — 출력의 91%가 추론 토큰이었다.
    # 프로브 결과는 캐시에 남아 본 실행에서 그대로 재사용되므로 버려지지 않는다.
    if args.docs:
        docs = [d for d in docs if Path(d["image"]).stem in args.docs]
        if not docs:
            raise SystemExit(f"--docs 에 해당하는 문서 없음: {args.docs}")
    out_dir = HERE / "results" / args.variant / args.model

    # 캐시 경로만 variant를 다르게 다룬다.
    #   v0_baseline  → cache/{model}/        기존 캐시를 그대로 재사용한다.
    #                  프롬프트가 현행 그대로라 지문이 일치하며, 평가셋 v3에서
    #                  내용이 안 바뀐 문서 8건이 무료로 재사용된다.
    #   그 외 variant → cache/{variant}/{model}/
    #                  variant끼리 같은 파일을 서로 덮어써 캐시가 무의미해지는 것을 막는다.
    cache_dir = (HERE / "cache" / args.model if args.variant == "v0_baseline"
                 else HERE / "cache" / args.variant / args.model)

    # 캐시 집계도 프롬프트 지문을 확인한다. 파일 존재만 세면 규제 표를 고친 뒤
    # dry-run이 "호출 2건"이라 하고 실제로는 10건을 호출하는 어긋남이 생긴다.
    cached = 0
    for d in docs:
        cp = cache_dir / f"{Path(d['image']).stem}.json"
        if not cp.exists():
            continue
        s, u = prompts.build_translate(d, target, config.REGULATION_TABLE, args.variant)
        if json.loads(cp.read_text(encoding="utf-8")).get("prompt_fp") == prompt_fingerprint(s, u):
            cached += 1
    todo = len(docs) - cached

    print(f"[{args.variant} / {args.model}] 문서 {len(docs)}건 — 캐시 {cached}건, 호출 필요 {todo}건")
    print(f"  목표 언어: {target or '_미정_'}")

    if not args.execute:
        print("\n--dry-run (기본). 실제 호출하지 않았음.")
        print("  비용 추정은 estimate_cost.py 참조. 호출하려면 --execute")
        if missing:
            print("\n⚠️ 실행 전 확정 필요")
            for m in missing:
                print(f"   - {m}")
        return

    if missing:
        raise SystemExit("확정되지 않은 설정이 있어 실행을 막는다:\n  - " + "\n  - ".join(missing))

    load_env()
    if not os.environ.get(config.MODELS[args.model]["env_key"]):
        raise SystemExit(f"{config.MODELS[args.model]['env_key']} 없음. .env에 넣을 것")

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    for d in docs:
        stem = Path(d["image"]).stem
        cp = cache_dir / f"{stem}.json"
        system, user = prompts.build_translate(d, target, config.REGULATION_TABLE, args.variant)
        fp = prompt_fingerprint(system, user)

        payload = None
        if cp.exists():
            cached_payload = json.loads(cp.read_text(encoding="utf-8"))
            if cached_payload.get("prompt_fp") == fp:
                payload = cached_payload
                print(f"  {d['image']:<10} 캐시 사용")
            else:
                print(f"  {d['image']:<10} 프롬프트 변경됨 — 캐시 무효, 재호출")

        if payload is None:
            t0 = time.perf_counter()
            text, usage = call_model(args.model, system, user)
            payload = {"raw": text, "usage": usage, "sec": round(time.perf_counter() - t0, 2),
                       "prompt_fp": fp}
            cp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {d['image']:<10} 호출 {payload['sec']}s  in{usage['input']}/out{usage['output']}")

        try:
            parsed = extract_json(payload["raw"])
        except (ValueError, json.JSONDecodeError) as e:
            # 구조화 출력 안정성도 평가 항목이다(문서 2.3). 실패를 지우지 말고 남긴다.
            parsed = {"translations": [], "parse_error": str(e)}
        (out_dir / f"{stem}.json").write_text(
            json.dumps({"image": d["image"], "model": args.model, **parsed},
                       ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[{args.variant} / {args.model}] 완료 → {out_dir}")


if __name__ == "__main__":
    main()
