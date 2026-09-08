"""C. 로컬라이징 번역 — LLM-as-judge (블라인드 분야별 채점 · 2종 교차).

사용법
    python judge.py --target gemini                    # dry-run. 호출하지 않음
    python judge.py --target gemini --execute          # JUDGE_MODELS 2종으로 채점
    python judge.py --target gemini --docs 10_longform # 선실측용 일부만
    python judge.py --target gemini --report           # 집계만 다시
    python judge.py --finals gemini claude gpt_sol ... # 결승 종합 문서

출력
    scores/{variant}__{target}__by_{judge}/{stem}.json   문서별 점수
    scores/detail/{variant}__{target}__cross.md          교차 대조 (대상별)
    scores/FINALS.md                                    **결승 종합** (--finals)
    cache/judge_{judge}_{variant}__{target}/{stem}.json

설계 3원칙 (PLAN.md 18번)
    ① **블라인드** — 어떤 모델의 번역인지 judge에게 알려주지 않는다.
       편향을 측정이 아니라 차단한다. 플래그 방식에서 claude judge가 자기 벤더에
       관대한 것이 실측됐다(8건 vs 평균 13.2건).
    ② **토큰량·시간을 넘기지 않는다** — 실측값이 이미 있고, 출력 토큰 수가
       모델을 식별하는 지문이 되어 블라인드를 깬다.
    ③ **평균을 LLM에게 시키지 않는다** — 분야별 점수만 받는다. 평균·가중·순위는
       전부 로컬이다. LLM이 평균을 내면 심각한 결함 1건이 0.06점으로 묻힌다.

집계 원칙
    - 분야별 평균과 **저점 분포**(`JUDGE_LOW`점 이하 건수)를 **함께** 낸다.
      평균만 보면 128건 중 3건이 2점이어도 9.81점이라 결함이 사라진다.
    - **종합 점수를 만들지 않는다.** 분야 간 가중은 팀이 정할 사안이다
      (법정 고지문 파괴와 어투 어색을 같은 무게로 섞을 수 없다).
    - `compliance`는 점수가 아니라 판정이다. 조건부 항목이라 평균에 넣으면
      문장마다 분모가 달라진다.

안전장치는 run.py와 같다 — 기본 dry-run, 캐시 우선, 프롬프트 지문으로 캐시 무효화.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
import time

import config
import prompts
from synthetic_source import TRAPS
from run import call_model, extract_json, load_env, prompt_fingerprint

HERE = Path(__file__).resolve().parent
AXES = list(prompts.JUDGE_AXES)
COMPLIANCE = ("정당", "부당", "해당없음")


def tag(variant: str, target: str) -> str:
    """경로용 라벨. `/`를 쓰면 폴더가 갈라져 집계가 꼬인다."""
    return f"{variant}__{target}"


def load_pairs(evalset: dict, variant: str, target: str) -> dict[str, list[dict]]:
    """문서별 (원문, 번역문) 쌍. 번역이 없는 세그먼트는 건너뛴다."""
    res_dir = HERE / "results" / variant / target
    out = {}
    for doc in evalset["documents"]:
        stem = Path(doc["image"]).stem
        p = res_dir / f"{stem}.json"
        if not p.exists():
            continue
        tr = {t["id"]: t.get("translation", "") for t in
              json.loads(p.read_text(encoding="utf-8")).get("translations", [])}
        pairs = [{"id": s["id"], "source": s["manual_fix"] or s["source"],
                  "translation": tr[s["id"]]}
                 for s in doc["segments"] if tr.get(s["id"])]
        if pairs:
            out[stem] = pairs
    return out


def load_rows(variant: str, target: str, judge: str) -> dict[str, dict]:
    """{세그먼트 id: 채점 결과}. 옛 형식(5점 척도·플래그)은 걸러낸다."""
    d = HERE / "scores" / f"{tag(variant, target)}__by_{judge}"
    rows = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        rows += json.loads(f.read_text(encoding="utf-8")).get("scores", [])
    return {r["id"]: r for r in rows
            if all(isinstance(r.get(a), (int, float)) for a in AXES)}


def axis_stats(rows: dict[str, dict], ids: list[str]) -> dict[str, dict]:
    """분야별 평균·최저·저점 건수. **종합 점수는 만들지 않는다.**"""
    out = {}
    for a in AXES:
        v = [rows[i][a] for i in ids if i in rows]
        out[a] = {"mean": statistics.mean(v) if v else None,
                  "min": min(v) if v else None,
                  "low": sum(1 for x in v if x <= config.JUDGE_LOW),
                  "n": len(v)}
    return out


def ambiguous_ids() -> set[str]:
    """`양립` 유형 세그먼트 — 치환·유지 둘 다 정답으로 인정한 자리.

    judge 프롬프트의 `정당` 예시 목록에는 이 유형이 없어 judge가 한쪽을 `부당`으로
    본다. **미결 항목에 대한 우리 선택을 judge가 그대로 반영하게 되므로 집계에서 뺀다.**
    """
    return {sid for sid, (_, exp) in TRAPS.items() if exp == "양립"}


def compliance_counts(rows: dict[str, dict], ids: list[str]) -> dict[str, int]:
    """`양립` 세그먼트는 세지 않는다."""
    amb = ambiguous_ids()
    c = {k: 0 for k in COMPLIANCE}
    for i in ids:
        if i in amb:
            continue
        v = (rows.get(i) or {}).get("compliance")
        if v in c:
            c[v] += 1
    return c


def score(judge: str, variant: str, target: str,
          pairs_by_doc: dict[str, list[dict]], execute: bool) -> None:
    """채점자 1종으로 채점. 캐시 키에 채점자·variant·대상을 모두 넣는다."""
    cache_dir = HERE / "cache" / f"judge_{judge}_{tag(variant, target)}"
    sc_dir = HERE / "scores" / f"{tag(variant, target)}__by_{judge}"

    cached = 0
    for stem, pairs in pairs_by_doc.items():
        cp = cache_dir / f"{stem}.json"
        if not cp.exists():
            continue
        sy, us = prompts.build_judge(pairs, config.TARGET_LANG, config.REGULATION_TABLE)
        if json.loads(cp.read_text(encoding="utf-8")).get("prompt_fp") == prompt_fingerprint(sy, us):
            cached += 1
    print(f"  [{judge}] 문서 {len(pairs_by_doc)}건 — 캐시 {cached}건, "
          f"호출 필요 {len(pairs_by_doc) - cached}건")
    if not execute:
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    sc_dir.mkdir(parents=True, exist_ok=True)
    for stem, pairs in pairs_by_doc.items():
        cp = cache_dir / f"{stem}.json"
        system, user = prompts.build_judge(pairs, config.TARGET_LANG, config.REGULATION_TABLE)
        fp = prompt_fingerprint(system, user)

        payload = None
        if cp.exists():
            cached_payload = json.loads(cp.read_text(encoding="utf-8"))
            # 지문이 다르면 채점 문안이 바뀐 것이다. run.py와 같은 규칙.
            if cached_payload.get("prompt_fp") == fp:
                payload = cached_payload
            else:
                print(f"    {stem:<20} 프롬프트 변경됨 — 캐시 무효, 재채점")
        if payload is None:
            t0 = time.perf_counter()
            text, usage = call_model(judge, system, user)
            payload = {"raw": text, "usage": usage, "prompt_fp": fp,
                       "sec": round(time.perf_counter() - t0, 2)}
            cp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"    {stem:<20} {payload['sec']}s")

        try:
            parsed = extract_json(payload["raw"])
        except (ValueError, json.JSONDecodeError) as e:
            # 구조화 출력 안정성도 기록 항목이다. 실패를 지우지 말고 남긴다.
            parsed = {"scores": [], "parse_error": str(e)}
        (sc_dir / f"{stem}.json").write_text(
            json.dumps({"document": stem, "target": target, "variant": variant,
                        "judge": judge, **parsed}, ensure_ascii=False, indent=1),
            encoding="utf-8")


def esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def cross_report(variant: str, target: str, judges: list[str], evalset: dict) -> None:
    """2종 교차 — 분야별 점수 차이 · 저점 판정 일치율 · 저점 상세."""
    if len(judges) < 2:
        print("  교차 불가 — 채점자 2종이 필요하다")
        return
    ja, jb = judges[0], judges[1]
    ra, rb = load_rows(variant, target, ja), load_rows(variant, target, jb)
    if not ra or not rb:
        print(f"  채점 결과 부족 — {ja}:{len(ra)} / {jb}:{len(rb)}")
        return

    src = {s["id"]: (s["manual_fix"] or s["source"])
           for d in evalset["documents"] for s in d["segments"]}
    tr = {}
    for d in evalset["documents"]:
        p = HERE / "results" / variant / target / f"{Path(d['image']).stem}.json"
        if p.exists():
            for t in json.loads(p.read_text(encoding="utf-8")).get("translations", []):
                tr[t["id"]] = t.get("translation", "")

    common = [i for i in src if i in ra and i in rb]
    sa, sb = axis_stats(ra, common), axis_stats(rb, common)

    # 저점(JUDGE_LOW 이하) 판정이 일치하는가 — 두 채점자가 같은 곳을 문제로 보는가
    low = lambda r, i: any(r[i][a] <= config.JUDGE_LOW for a in AXES)
    agree = sum(1 for i in common if low(ra, i) == low(rb, i))
    rate = agree / len(common) if common else 0.0
    both_low = [i for i in common if low(ra, i) and low(rb, i)]
    one_low = [i for i in common if low(ra, i) != low(rb, i)]

    L = [f"# C. judge 교차 — `{variant}` / `{target}`", "",
         "> 자동 생성. `judge.py` 재실행 시 덮어씀.",
         "> **블라인드 채점.** judge는 어느 모델의 번역인지 모른다.", "",
         f"- 채점자: `{ja}` × `{jb}` / 공통 세그먼트 {len(common)}개",
         f"- **저점 판정 일치율: {rate * 100:.0f}%** "
         f"({config.JUDGE_LOW}점 이하를 '문제 있음'으로 볼 때)", ""]
    if rate < config.JUDGE_AGREEMENT_MIN:
        L += [f"> ⚠️ **일치율이 {config.JUDGE_AGREEMENT_MIN * 100:.0f}% 미만이다. "
              "judge 축을 판정에서 제외하고 육안으로 넘긴다.**", ""]

    L += ["## 1. 분야별 점수", "",
          f"| 분야 | `{ja}` 평균 | `{jb}` 평균 | 차이 | `{ja}` 저점 | `{jb}` 저점 | 최저 |",
          "|---|---|---|---|---|---|---|"]
    for a in AXES:
        m1, m2 = sa[a]["mean"], sb[a]["mean"]
        d = f"{abs(m1 - m2):.2f}" if m1 is not None and m2 is not None else "—"
        L.append(f"| `{a}` | {m1:.2f} | {m2:.2f} | {d} | {sa[a]['low']} | {sb[a]['low']} | "
                 f"{min(sa[a]['min'], sb[a]['min'])} |")
    L += ["", f"> `저점` = {config.JUDGE_LOW}점 이하 건수. **평균과 함께 봐야 한다** — "
          "평균만 보면 128건 중 3건이 2점이어도 9.81점이라 결함이 사라진다.",
          "> **종합 점수는 만들지 않는다.** 분야 간 가중은 팀이 정할 사안이다.", ""]

    L += ["## 2. 규제 미준수 정당성 (`compliance`)", "",
          f"| 판정 | `{ja}` | `{jb}` |", "|---|---|---|"]
    ca, cb = compliance_counts(ra, common), compliance_counts(rb, common)
    for k in COMPLIANCE:
        L.append(f"| {k} | {ca[k]} | {cb[k]} |")
    L += ["", "> `부당` = 바꿔야 할 자리인데 안 바꿈. **이것만 실제 위반이다.**",
          "> `정당` = 바꾸면 안 되는 자리였거나 **규제 표 자체가 모순**인 경우.", ""]

    if both_low:
        L += ["## 3. 두 채점자 모두 저점 — 판정 반영분", "",
              f"| 세그먼트 | 원문 | 번역 | `{ja}` | `{jb}` | 근거 |",
              "|---|---|---|---|---|---|"]
        for i in both_low:
            f1 = "/".join(str(ra[i][a]) for a in AXES)
            f2 = "/".join(str(rb[i][a]) for a in AXES)
            L.append(f"| {i} | {esc(src.get(i))} | {esc(tr.get(i))} | {f1} | {f2} | "
                     f"{esc(ra[i].get('reason'))} |")
        L += ["", f"> 점수 표기 순서: {' / '.join(f'`{a}`' for a in AXES)}", ""]

    if one_low:
        L += ["## 4. 한쪽만 저점 — 참고", "",
              "> **육안 재채점 대상이 아니다**(PLAN.md 20번 ②). 불일치가 적은 모델을 우선한다.", "",
              f"| 세그먼트 | 원문 | `{ja}` | `{jb}` |", "|---|---|---|---|"]
        for i in one_low:
            f1 = "/".join(str(ra[i][a]) for a in AXES)
            f2 = "/".join(str(rb[i][a]) for a in AXES)
            L.append(f"| {i} | {esc(src.get(i))} | {f1} | {f2} |")
        L.append("")

    out = HERE / "scores" / "detail" / f"{tag(variant, target)}__cross.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"  교차 대조 → {out.name}  (일치율 {rate * 100:.0f}%, "
          f"양측 저점 {len(both_low)}건, 한쪽 저점 {len(one_low)}건)")


def finals(variant: str, targets: list[str], judges: list[str], evalset: dict) -> None:
    """결승 종합 — `scores/FINALS.md`. 분야별 평균은 두 채점자 평균으로 낸다."""
    import compare as C

    ja, jb = judges[0], judges[1]
    src_ids = [s["id"] for d in evalset["documents"] for s in d["segments"]]
    rows = []
    for t in targets:
        ra, rb = load_rows(variant, t, ja), load_rows(variant, t, jb)
        if not ra or not rb:
            continue
        common = [i for i in src_ids if i in ra and i in rb]
        sa, sb = axis_stats(ra, common), axis_stats(rb, common)
        low = lambda r, i: any(r[i][a] <= config.JUDGE_LOW for a in AXES)
        agree = sum(1 for i in common if low(ra, i) == low(rb, i))
        u = C.usage_of(f"{variant}/{t}")
        spec = config.MODELS[t]
        rows.append({
            "t": t, "id": spec["model_id"], "n": len(common),
            "rate": agree / len(common) if common else 0,
            "both_low": sum(1 for i in common if low(ra, i) and low(rb, i)),
            "one_low": sum(1 for i in common if low(ra, i) != low(rb, i)),
            "mean": {a: (sa[a]["mean"] + sb[a]["mean"]) / 2 for a in AXES},
            "lowcnt": {a: sa[a]["low"] + sb[a]["low"] for a in AXES},
            "comp": {k: compliance_counts(ra, common)[k] + compliance_counts(rb, common)[k]
                     for k in COMPLIANCE},
            "cost": u["in"] / 1e6 * spec["price_in"] + u["out"] / 1e6 * spec["price_out"],
            "sec": u["sec"], "out": u["out"],
        })

    L = ["# C. 로컬라이징 번역 — 3단계 결승 종합", "",
         "> 자동 생성. `python judge.py --finals ...` 재실행 시 덮어씀.", "",
         f"- 구조: `{variant}` / 평가셋 v3.1 (128세그)",
         f"- 채점: **블라인드** — judge는 어느 모델의 번역인지 모른다. `{ja}` × `{jb}` 2종 교차",
         f"- 척도: 분야 {len(AXES)}개 × 1~10점. **종합 점수를 만들지 않는다** — 가중은 팀이 정한다",
         "", "> ⚠️ 규제 표가 **테스트용 더미**다. 모든 결론은 실제 표 확보 전까지 잠정.", ""]

    L += ["## 1. 분야별 평균 (채점자 2종 평균)", "",
          "| 대상 | " + " | ".join(f"`{a}`" for a in AXES) + " | 일치율 |",
          "|---|" + "---|" * (len(AXES) + 1)]
    for r in rows:
        L.append(f"| `{r['id']}` | " + " | ".join(f"{r['mean'][a]:.2f}" for a in AXES)
                 + f" | {r['rate'] * 100:.0f}% |")
    L.append("")

    L += ["## 2. 저점 분포 — **평균과 반드시 함께 볼 것**", "",
          f"{config.JUDGE_LOW}점 이하 건수. 두 채점자 합계다.", "",
          "| 대상 | " + " | ".join(f"`{a}`" for a in AXES) + " | 양측 저점 | 한쪽만 |",
          "|---|" + "---|" * (len(AXES) + 2)]
    for r in sorted(rows, key=lambda x: x["both_low"]):
        L.append(f"| `{r['id']}` | " + " | ".join(str(r["lowcnt"][a] or "") for a in AXES)
                 + f" | **{r['both_low']}** | {r['one_low']} |")
    L += ["", "> `양측 저점` = 두 채점자가 모두 문제로 본 건. **판정 반영분.**",
          "> `한쪽만` = 채점자가 갈린 건. 육안 재채점 대상이 아니며 **적은 쪽을 우선**한다.", ""]

    L += ["## 3. 규제 미준수 정당성", "",
          "| 대상 | 정당 | **부당** | 해당없음 |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['id']}` | {r['comp']['정당']} | **{r['comp']['부당']}** | "
                 f"{r['comp']['해당없음']} |")
    L += ["", "> **`부당`만 실제 위반이다.** `정당`에는 바꾸면 안 되는 자리와 "
          "**규제 표 자체가 모순인 경우**가 함께 들어간다 — 후자는 표 개선 근거다.",
          "> **`양립` 유형(H UI 라벨) 8쌍은 집계에서 제외했다** — 치환·유지 둘 다 "
          "정답으로 인정한 자리라, 세면 미결 항목에 대한 우리 선택이 순위에 반영된다.", ""]

    L += ["## 4. 실측 (판정 축 아님 — 기록)", "",
          "토큰량·시간은 **judge가 채점하지 않는다.** 실측값을 로컬에서 집계한다.", "",
          "| 대상 | 비용 | 소요 | 출력tok |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['id']}` | {r['cost']:.4f}$ | {r['sec']}s | {r['out']:,} |")
    L += ["", "> **judge에게 이 값을 넘기지 않는다.** 출력 토큰 수가 모델을 식별하는 "
          "지문이 되어 블라인드를 깬다.", "",
          "## 5. 대상별 상세", "", "| 대상 | 문서 |", "|---|---|"]
    for r in rows:
        L.append(f"| `{r['id']}` | `scores/detail/{tag(variant, r['t'])}__cross.md` |")
    L.append("")

    out = HERE / "scores" / "FINALS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"결승 종합 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", help="채점할 번역 결과의 모델 키")
    ap.add_argument("--variant", default="v6_principle")
    ap.add_argument("--judges", nargs="*", default=None,
                    help=f"채점자. 기본 {config.JUDGE_MODELS}")
    ap.add_argument("--evalset", default="evalset.json")
    ap.add_argument("--execute", action="store_true", help="실제 API 호출 (비용 발생)")
    ap.add_argument("--report", action="store_true", help="집계만 다시 수행")
    ap.add_argument("--finals", nargs="*", default=None, help="결승 종합 문서 생성")
    ap.add_argument("--docs", nargs="*", default=None, help="문서 일부만 (선실측용)")
    args = ap.parse_args()

    judges = args.judges or config.JUDGE_MODELS
    evalset = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))

    if args.finals is not None:
        finals(args.variant, args.finals, judges, evalset)
        return
    if not args.target:
        raise SystemExit("--target 또는 --finals 가 필요하다")
    if args.report:
        cross_report(args.variant, args.target, judges, evalset)
        return

    pairs = load_pairs(evalset, args.variant, args.target)
    if args.docs:
        pairs = {k: v for k, v in pairs.items() if k in args.docs}
    if not pairs:
        raise SystemExit(f"번역 결과 없음: results/{args.variant}/{args.target}/")

    print(f"채점 대상: {args.variant} / {args.target}  (블라인드)")
    print(f"  세그먼트 {sum(len(v) for v in pairs.values())}개 · 채점자 {judges}")
    for note in config.pending_notes():
        print(f"  [!] {note}")

    if not args.execute:
        for j in judges:
            score(j, args.variant, args.target, pairs, execute=False)
        print("\n--dry-run (기본). 실제 호출하지 않았음. 호출하려면 --execute")
        return

    load_env()   # ⚠️ 호출 전에 와야 한다. 뒤에 두면 인증이 안 된 채로 호출한다
    for j in judges:
        score(j, args.variant, args.target, pairs, execute=True)
    cross_report(args.variant, args.target, judges, evalset)


if __name__ == "__main__":
    main()
