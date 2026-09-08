"""C. 로컬라이징 번역 — 호출 전 건수·비용 추정.

CLAUDE.md 규칙: 유료 API 호출 전 예상 건수·비용을 보고하고 확인받는다.
이 스크립트가 그 보고서를 만든다. **API를 호출하지 않는다.**

사용법
    python estimate_cost.py
    python estimate_cost.py --target-lang 영어      # config 미설정 시 임시 지정

토큰 수는 문자 수 기반 근사다. 정확한 값이 필요하면 Anthropic count_tokens로
Claude 분만 실측할 수 있으나, 이 규모(총 929자)에서는 근사로 충분하다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import prompts

HERE = Path(__file__).resolve().parent

# 한국어·CJK는 문자당 토큰이 영문보다 많다. 보수적으로 잡아 과소추정을 피한다.
TOK_PER_CHAR = 0.9
# 번역 출력은 원문 대비 이 배수로 잡는다(영문화 시 문자 수가 늘어남)
OUT_RATIO = 2.0


def approx_tokens(text: str) -> int:
    return max(1, int(len(text) * TOK_PER_CHAR))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evalset", default="evalset.json")
    ap.add_argument("--target-lang", default=None, help="config.TARGET_LANG 임시 대체")
    args = ap.parse_args()

    target = args.target_lang or config.TARGET_LANG or "_미정_"
    data = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))
    docs = data["documents"]

    # 번역 — 문서 1건당 1회 호출
    t_in = t_out = 0
    for d in docs:
        system, user = prompts.build_translate(d, target, config.REGULATION_TABLE)
        t_in += approx_tokens(system) + approx_tokens(user)
        t_out += int(sum(approx_tokens(s["manual_fix"] or s["source"]) for s in d["segments"]) * OUT_RATIO)

    # 채점 — 후보 모델 수만큼, 문서 1건당 1회
    scale = config.JUDGE_SCALE or 5
    j_in = j_out = 0
    for d in docs:
        pairs = [{"id": s["id"], "source": s["source"], "translation": "x" * len(s["source"]) * 2}
                 for s in d["segments"]]
        system, user = prompts.build_judge(pairs, target, scale, config.REGULATION_TABLE)
        j_in += approx_tokens(system) + approx_tokens(user)
        j_out += 60 * len(d["segments"])   # 세그먼트당 점수 4개 + 사유

    print(f"평가셋: 문서 {len(docs)}개 / 세그먼트 {data['counts']['segments']}개")
    print(f"목표 언어: {target}")
    print()
    print("호출 건수")
    print(f"  번역   후보 4종 × 문서 {len(docs)}건 = {4 * len(docs)}회")
    print(f"  채점   judge 1종 × 후보 4종 × 문서 {len(docs)}건 = {4 * len(docs)}회")
    print(f"  합계   {8 * len(docs)}회")
    print()
    print("모델별 예상 비용 (번역 1회분)")
    print(f"  {'모델':<10}{'입력tok':>9}{'출력tok':>9}{'비용USD':>12}")
    total_known = 0.0
    for name, m in config.MODELS.items():
        if m["price_in"] is None:
            print(f"  {name:<10}{t_in:>9}{t_out:>9}{'가격 미정':>12}")
            continue
        cost = t_in / 1e6 * m["price_in"] + t_out / 1e6 * m["price_out"]
        total_known += cost
        print(f"  {name:<10}{t_in:>9}{t_out:>9}{cost:>11.4f}$")

    jm = config.MODELS[config.JUDGE_MODEL]
    if jm["price_in"] is not None:
        jcost = (j_in / 1e6 * jm["price_in"] + j_out / 1e6 * jm["price_out"]) * 4
        total_known += jcost
        print(f"\n채점 ({config.JUDGE_MODEL}, 후보 4종분): {jcost:.4f}$")

    print(f"\n가격이 확인된 모델만 합산: {total_known:.4f}$")
    unknown = [n for n, m in config.MODELS.items() if m["price_in"] is None]
    if unknown:
        print(f"⚠️ 가격 미정: {', '.join(unknown)} — config.MODELS에 채운 뒤 다시 추정할 것")

    missing = config.missing_settings()
    if missing:
        print("\n⚠️ 실행 전 확정 필요")
        for m in missing:
            print(f"   - {m}")


if __name__ == "__main__":
    main()
