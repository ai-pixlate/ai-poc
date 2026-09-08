"""C. 로컬라이징 번역 — 1차 정량 집계 + 육안 확인표 생성기.

사용법
    python compare.py                          # results/ 아래 전부
    python compare.py --targets gpt claude     # 일부만

출력
    summary.md   실행 요약 + 1차 정량 + 함정 정답률 + 세그먼트 대조
    REVIEW.md    **육안 확정 작업지** — 함정 불명 / 오답 재확인 / 품질 등급
                 확정 칸은 비워서 낸다. 사람이 채운다(CLAUDE.md).

판정 구조 (PLAN.md 7장)
    1차 정량(이 파일) → 2차 judge → **육안 확정**
    기계는 후보를 좁히는 데까지만 한다. 등급·확정 칸을 채우지 않는다(CLAUDE.md).

결과 폴더 구조는 두 가지를 모두 읽는다.
    results/{모델}/            현행
    results/{variant}/{모델}/  1단계 variant 실행용
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import config
from literal_forms import LITERAL_FORMS, missing_forms
from review_confirm import CONFIRMED
from synthetic_source import TRAPS

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CACHE = HERE / "cache"
SCORES = HERE / "scores"

# 벤치마크가 아닌 결과는 표에서 구분한다.
# 조건이 다른 결과를 같은 표에 넣으면 오독한다 — 실제로 참고 측정 대상의
# 정답률을 52%로 잘못 읽은 적이 있다(PoC 문서 2.3 6차 실행 기록).
NOT_BENCHMARK = {
    "claude_session": "⚠️ 세션 예비 실행 — 조건이 다름. 벤치마크 점수로 쓰지 말 것",
    "qwen_mt_ref": "⚠️ 참고 측정 — 번역 전용 모델. 시스템 프롬프트·JSON 불가로 후보 제외",
    "qwen_plus_nothink": "⚠️ 참고 측정 — **사고 모드 off.** 타 벤더와 조건이 다름",
    "qwen_flash38": "⚠️ 프로브만 — 전체 환산 86분으로 서비스 부적합, 예선 제외",
}

HANGUL = re.compile(r"[가-힣]")

# 브랜드명은 원표기 유지가 정답이므로(프롬프트 규칙 3) 한글이 남아도 미번역이 아니다.
# ⚠️ 임시 목록. 평가셋 v3에서 `role` 필드로 대체한다.
KEEP_AS_IS = ["루미에르"]


# ─────────────────────────────────────────────────────────────
# 정규화·매칭 — detector의 토대
# ─────────────────────────────────────────────────────────────
# 옛 판정식은 `대체표현 첫 단어 앞 5글자`를 부분 문자열로 찾았다. 15항목 중
# 5항목이 오탐이었다 — `여드름 완화`·`탄력 강화`가 둘 다 "for"로 줄어 거의 모든
# 영어 문장에 걸렸고, `치료`의 "care"가 skincare에, `의학적`의 "derma"가
# dermatologist에 걸렸다. 전체 구문을 단어 경계로 맞춰 그 오탐을 없앤다.

def norm(s: str) -> str:
    """소문자·하이픈·구두점·공백 정규화. `%`는 `100%` 때문에 남긴다."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[-–—_/]", " ", s)
    s = re.sub(r"[^0-9a-z가-힣%\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def stem(tok: str) -> str:
    """영어 굴절 어미를 떨어낸다. 한글·숫자는 그대로 둔다.

    모델은 표의 문안을 그대로 쓰지 않는다 — 표가 `helps reduce ...`인데
    `help reduce` / `helping reduce`로 쓴다. 어간을 맞추지 않으면 이런 건이
    전부 '대체표현 미검출'로 빠져 불명 처리된다.
    """
    if not tok.isascii() or not tok.isalpha():
        return tok
    for suf in ("ing", "ed", "es", "s"):
        if len(tok) > 3 and tok.endswith(suf) and len(tok) - len(suf) >= 3:
            tok = tok[:-len(suf)]
            break
    return tok[:-1] if len(tok) > 3 and tok.endswith("e") else tok


def toks(s: str) -> list[str]:
    return [stem(t) for t in norm(s).split()]


def _contains(haystack: list[str], p: list[str]) -> bool:
    if not p or len(p) > len(haystack):
        return False
    return any(haystack[i:i + len(p)] == p for i in range(len(haystack) - len(p) + 1))


def has_phrase(haystack: list[str], phrase: str) -> bool:
    """어간 토큰 열에서 구문을 **연속 부분열**로 찾는다.

    부분 문자열이 아니라 토큰 단위이므로 `care`가 `skincare`에,
    `derma`가 `dermatologist`에 걸리는 옛 오탐이 원천적으로 생기지 않는다.

    선두 토큰 완화 — 모델은 표의 문안을 통째로 옮기지 않고 앞머리를 바꾼다.
        표 `helps reduce the look of fine lines` → 모델 `reducing the look of fine lines`
        표 `for a firmer look`                  → 모델 `contributes to a firmer look`
    선두를 최대 2토큰까지 떼어 보되 **남는 구문이 3토큰 이상일 때만** 허용한다.
    짧은 구문(`care`, `pure`, `gentle formula`)은 완화하지 않는다 — 느슨해지면 오탐이 돌아온다.
    """
    p = toks(phrase)
    if _contains(haystack, p):
        return True
    for i in (1, 2):
        if len(p) - i >= 3 and _contains(haystack, p[i:]):
            return True
    return False


def form_collisions(table: list[dict] | None) -> list[str]:
    """직역형과 대체표현이 겹치면 치환/유지를 못 가른다. 사전 자체를 점검한다."""
    out = []
    for row in table or []:
        b, rep = row.get("금지표현"), row.get("대체표현", "")
        for lf in LITERAL_FORMS.get(b, []):
            if has_phrase(toks(rep), lf) or has_phrase(toks(lf), rep):
                out.append(f"`{b}` — 직역형 `{lf}` 이 대체표현 `{rep}` 과 겹침")
    return out


# ─────────────────────────────────────────────────────────────
# 결과 로딩
# ─────────────────────────────────────────────────────────────

def find_targets() -> dict[str, Path]:
    """results/ 아래에서 대상을 찾는다. 한 단계 또는 두 단계 구조를 모두 지원."""
    found: dict[str, Path] = {}
    if not RESULTS.exists():
        return found
    for d in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        if any(d.glob("*.json")):
            found[d.name] = d
            continue
        for sub in sorted(p for p in d.iterdir() if p.is_dir()):
            if any(sub.glob("*.json")):
                found[f"{d.name}/{sub.name}"] = sub
    return found


def load(path: Path) -> tuple[dict[str, tuple[str, str]], dict]:
    """(id → (번역문, note), 메타). 메타에 파싱 실패 건수를 담는다."""
    out: dict[str, tuple[str, str]] = {}
    docs = fails = 0
    for f in sorted(path.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        docs += 1
        if d.get("parse_error"):
            fails += 1
        for t in d.get("translations", []):
            out[t["id"]] = (t.get("translation", ""), t.get("note", ""))
    return out, {"docs": docs, "parse_fail": fails}


def cache_path(label: str) -> Path:
    """run.py의 캐시 경로 규칙을 그대로 따른다.

    `v0_baseline`은 프롬프트가 현행 그대로라 variant 폴더를 두지 않고
    `cache/{model}/`을 재사용한다. 이 규칙을 여기서 못 맞추면 실행 요약의
    토큰·비용 칸이 통째로 비어 버린다.
    """
    parts = label.split("/")
    if len(parts) == 2 and parts[0] == "v0_baseline":
        return CACHE / parts[1]
    return CACHE / Path(label)


def usage_of(label: str) -> dict:
    """캐시에서 실측 토큰·소요를 모은다. 세션 실행처럼 캐시가 없으면 빈 값."""
    path = cache_path(label)
    ti = to = n = 0
    sec = 0.0
    for f in path.glob("*.json") if path.exists() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        u = d.get("usage") or {}
        ti += u.get("input", 0)
        to += u.get("output", 0)
        sec += d.get("sec", 0) or 0
        n += 1
    return {"calls": n, "in": ti, "out": to, "sec": round(sec)}


def model_key(label: str) -> str:
    return label.split("/")[-1]


# ─────────────────────────────────────────────────────────────
# 1차 정량 — 6항목
# ─────────────────────────────────────────────────────────────

def trap_verdict(translation: str, banned: str, replacement: str,
                 expect: str) -> tuple[str, str]:
    """(판정, 근거). 판정은 O 정답 · X 오답 · ? 불명 · — 미실행.

    치환됨 = 대체표현 있음 & 직역형 없음
    유지됨 = 직역형 있음 & 대체표현 없음
    둘 다 없거나 둘 다 있으면 **기계가 정하지 않는다.** 육안 판정으로 올린다.
    """
    if translation is None:
        return "—", "미실행"
    tn = toks(translation)
    # `양립` — 치환·유지 어느 쪽이든 정답인 자리. 사람·모델·judge가 모두 갈렸으므로
    # 한쪽을 정답으로 강제하지 않는다(synthetic_source.TRAPS의 H 주석 참조).
    if expect == "양립":
        replaced_ = has_phrase(tn, replacement)
        literal_ = has_phrase(tn, banned) or any(
            has_phrase(tn, lf) for lf in LITERAL_FORMS.get(banned, []))
        if not replaced_ and not literal_:
            return "?", "대체·직역 둘 다 미검출"
        return "O", ("치환함 (양립)" if replaced_ else "유지함 (양립)")
    replaced = has_phrase(tn, replacement)
    # 원 표기(한글)가 그대로 남은 것도 '유지'다. 제품명을 원표기로 둔 경우가 여기 해당한다.
    literal = has_phrase(tn, banned) or any(
        has_phrase(tn, lf) for lf in LITERAL_FORMS.get(banned, []))
    if replaced and not literal:
        did = "치환"
    elif literal and not replaced:
        did = "유지"
    else:
        return "?", ("대체·직역 둘 다 검출" if replaced else "대체·직역 둘 다 미검출")
    return ("O" if did == expect else "**X**"), f"{did}함"


def term_accuracy(segs: list[dict], tr: dict) -> tuple[int, int]:
    """expect_term 사전 대비 (맞은 용어, 전체 용어). v3 이전 평가셋이면 (0, 0)."""
    ok = total = 0
    for s in segs:
        terms = s.get("expect_term") or []
        if not terms or s["id"] not in tr:
            continue
        tn = toks(tr[s["id"]][0])
        for t in terms:
            # `|`로 대체 표기를 허용한다 — 인증명은 정답이 하나로 정해지지 않는다
            # (예: 식약처 → `MFDS` / `Ministry of Food and Drug Safety`).
            total += 1
            ok += any(has_phrase(tn, alt) for alt in t.split("|"))
    return ok, total


# ─────────────────────────────────────────────────────────────
# 환각 — 숫자·단위 보존 (PLAN.md 7-1)
# ─────────────────────────────────────────────────────────────
# 환각은 세 갈래인데 기계로 잴 수 있는 것은 앞의 둘뿐이다.
#   ① 숫자·단위 변조    ← 여기서 잰다. 정답이 원문에 그대로 있다
#   ② 성분·인증명 훼손  ← `expect_term`이 담당
#   ③ 원문에 없는 정보 추가 ← **기계로 못 잡는다.** 3단계 결승에서 judge가 맡는다
#
# ①이 중요한 이유 — 성분 함량(`0.04%`)이나 임상 인원(`32명`)이 틀리면
# 안전·법적 문제가 된다. PoC 문서 4장 체크리스트의 성분 표기 항목과 직결된다.

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def banned_with_digits(table: list[dict] | None) -> list[str]:
    """규제 표의 금지표현 중 숫자를 품은 것. 예: `100%`."""
    return [r["금지표현"] for r in (table or [])
            if r.get("금지표현") and any(c.isdigit() for c in r["금지표현"])]


def numbers_of(text: str, strip: list[str] | None = None) -> list[str]:
    """숫자 토큰을 뽑는다. 콤마는 지우고 값만 남긴다.

    두 가지를 제외한다 — 둘 다 숫자가 **정당하게** 사라지는 자리라
    세면 멀쩡한 번역이 오답으로 잡힌다.

    ① `8월`처럼 뒤에 `월`이 붙은 숫자 — 영어로 `August`가 되며 숫자가 없어진다.
    ② `strip`에 넘긴 금지표현 안의 숫자 — `100% → pure`처럼 치환하면 사라진다.
       **이 자리의 정오는 함정 정답률이 이미 판정한다.** 환각으로 또 세면
       같은 오류를 두 축에서 이중 계상하게 된다.
    """
    t = text or ""
    for b in strip or []:
        t = t.replace(b, " ")
    out = []
    for m in NUM_RE.finditer(t):
        if t[m.end():m.end() + 1] == "월":
            continue
        out.append(m.group().replace(",", ""))
    return out


def numeric_fidelity(segs: list[dict], tr: dict,
                     strip: list[str] | None = None) -> tuple[int, int, list[tuple[str, str, str]]]:
    """(보존, 전체, 누락 목록). 값 단위로 비교하므로 `4`가 `0.04`에 걸리지 않는다."""
    ok = total = 0
    lost: list[tuple[str, str, str]] = []
    for s in segs:
        if s["id"] not in tr:
            continue
        src = numbers_of(src_text(s), strip)
        if not src:
            continue
        pool = numbers_of(tr[s["id"]][0])
        missing = []
        for n in src:
            total += 1
            if n in pool:
                pool.remove(n)          # 같은 값이 여러 번 나오는 경우 대응
                ok += 1
            else:
                missing.append(n)
        if missing:
            lost.append((s["id"], ", ".join(missing), tr[s["id"]][0]))
    return ok, total, lost


def korean_left(segs: list[dict], tr: dict, exempt: set[str]) -> int:
    """번역문에 한글이 남은 세그먼트 수.

    제품명·브랜드명은 원표기 유지가 정답이라 한글이 남는 것이 정상이다. 세지 않는다 —
    세면 프롬프트 규칙 3(브랜드명 원표기 유지)을 지킨 모델이 필수 통과 조건에서 탈락한다.
    """
    n = 0
    for s in segs:
        if s["id"] not in tr or s["id"] in exempt:
            continue
        text = tr[s["id"]][0] or ""
        for kw in KEEP_AS_IS:
            text = text.replace(kw, "")
        n += bool(HANGUL.search(text))
    return n


def char_ratio(segs: list[dict], tr: dict) -> float | None:
    src = sum(len(src_text(s)) for s in segs if s["id"] in tr)
    out = sum(len(tr[s["id"]][0] or "") for s in segs if s["id"] in tr)
    return round(out / src, 2) if src else None


def src_text(s: dict) -> str:
    return s.get("manual_fix") or s["source"]


# ─────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="*", default=None)
    ap.add_argument("--evalset", default="evalset.json")
    args = ap.parse_args()

    ev = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))
    segs = [s for d in ev["documents"] for s in d["segments"]]
    seg_ids = [s["id"] for s in segs]

    available = find_targets()
    labels = args.targets or list(available)
    labels = [t for t in labels if t in available]
    if not labels:
        raise SystemExit("번역 결과 없음")

    data, meta = {}, {}
    for t in labels:
        data[t], meta[t] = load(available[t])
    labels = [t for t in labels if data[t]]

    table = config.REGULATION_TABLE or []
    rows = {r["금지표현"]: r["대체표현"] for r in table}

    # 사전 자체 점검 — 채점 신뢰도가 곧 판정 신뢰도다
    warn = [f"직역형 사전에 없는 금지표현: {', '.join(m)}" for m in [missing_forms(table)] if m]
    warn += form_collisions(table)

    # 제품명 유지가 정답인 세그먼트 — 미번역 잔존 집계에서 뺀다
    exempt = {sid for sid, (kind, exp) in TRAPS.items()
              if kind.startswith("C 제품명") and exp == "유지"}
    exempt |= {s["id"] for s in segs if s.get("role") in ("product_name", "brand")}

    # 금지표현에 든 숫자(`100%`)는 환각 집계에서 뺀다 — 함정 축이 이미 판정한다
    num_strip = banned_with_digits(table)

    # 함정 대상 (세그먼트, 금지표현) 쌍
    flagged = [(s["id"], b) for s in segs for b in rows if b in src_text(s)]
    has_terms = any(s.get("expect_term") for s in segs)

    # 대상별 함정 판정 계산
    # 기계가 `?`로 보류한 건은 `review_confirm.CONFIRMED`의 육안 확정으로 덮어쓴다.
    # **`O`/`X` 판정은 덮어쓰지 않는다** — 덮어쓰면 확인이 아니라 측정을 바꾸는 것이 된다.
    verdicts: dict[str, dict[tuple[str, str], tuple[str, str]]] = {}
    stale: list[str] = []
    for t in labels:
        verdicts[t] = {}
        for sid, b in flagged:
            _, expect = TRAPS.get(sid, ("대조군", "치환"))
            tr = data[t][sid][0] if sid in data[t] else None
            v = trap_verdict(tr, b, rows[b], expect)
            conf = CONFIRMED.get((t, sid, b))
            if conf:
                if v[0] == "?":
                    v = (conf[0], f"육안 확정 — {conf[1]}")
                else:
                    stale.append(f"{t} / {sid} / {b} — 기계 판정이 `{v[0]}`인데 확정 기록이 있다")
            verdicts[t][(sid, b)] = v
    warn += stale

    # ── summary.md ────────────────────────────────────────────
    L = ["# C. 로컬라이징 번역 — 1차 정량 집계", "",
         "> 자동 생성. `compare.py` 재실행 시 덮어씀.", "",
         f"- 평가셋: `{ev.get('source_kind', 'ocr')}` — 문서 {ev['counts']['documents']}개 / "
         f"세그먼트 {ev['counts']['segments']}개",
         f"- 목표 언어: {ev.get('target_lang') or config.TARGET_LANG}",
         "- 판정 구조: **1차 정량(이 표) → 2차 judge → 육안 확정** (PLAN.md 7장)", ""]

    if config.REGULATION_TABLE_IS_TEST:
        L += ["> ⚠️ 규제 표가 **테스트용 더미**다. 결과는 실제 규제 준수 판단 근거가 "
              "아니며, 실제 표 확보 전까지 **잠정**이다.", ""]
    if warn:
        L += ["> ⚠️ **채점 사전 점검 경고** — 아래를 고치기 전 정답률을 신뢰하지 말 것.", ""]
        L += [f"> - {w}" for w in warn] + [""]

    # 1. 실행 요약
    L += ["## 1. 실행 요약", "",
          "| 대상 | 모델 | 호출 | 입력tok | 출력tok | 소요 | 실측 비용 | 비고 |",
          "|---|---|---|---|---|---|---|---|"]
    for t in labels:
        u = usage_of(t)
        spec = config.MODELS.get(model_key(t), {})
        cost = "—"
        if spec.get("price_in") and u["calls"]:
            cost = f"{u['in']/1e6*spec['price_in'] + u['out']/1e6*spec['price_out']:.4f}$"
        L.append(f"| `{t}` | {spec.get('model_id') or '—'} | {u['calls'] or '—'} | "
                 f"{u['in'] or '—'} | {u['out'] or '—'} | {str(u['sec']) + 's' if u['sec'] else '—'} | "
                 f"{cost} | {NOT_BENCHMARK.get(model_key(t), '')} |")
    L.append("")

    # 2. 1차 정량 6항목
    L += ["## 2. 1차 정량 지표", "",
          "| 대상 | 함정 정답률 | 불명 | 용어 정확도 | **숫자 보존** | 미번역 잔존 | "
          "세그먼트 누락 | JSON 성공률 | 문자수 비율 |",
          "|---|---|---|---|---|---|---|---|---|"]
    quant = {}
    for t in labels:
        v = verdicts[t]
        o = sum(1 for x in v.values() if x[0] == "O")
        x_ = sum(1 for x in v.values() if x[0] == "**X**")
        q = sum(1 for x in v.values() if x[0] == "?")
        miss = sum(1 for x in v.values() if x[0] == "—")
        rate = f"{o / (o + x_) * 100:.0f}%" if (o + x_) else "—"
        tok, ttot = term_accuracy(segs, data[t])
        term = f"{tok}/{ttot} ({tok / ttot * 100:.0f}%)" if ttot else "— _v3 미적용_"
        nok, ntot, nlost = numeric_fidelity(segs, data[t], num_strip)
        num = f"{nok}/{ntot} ({nok / ntot * 100:.0f}%)" if ntot else "—"
        kr = korean_left(segs, data[t], exempt)
        lost = len([i for i in seg_ids if i not in data[t]])
        m = meta[t]
        js = f"{(m['docs'] - m['parse_fail']) / m['docs'] * 100:.0f}%" if m["docs"] else "—"
        ratio = char_ratio(segs, data[t])
        quant[t] = {"rate": rate, "unknown": q, "miss": miss, "kr": kr,
                    "lost": lost, "parse_fail": m["parse_fail"],
                    "num": num, "nlost": nlost}
        L.append(f"| `{t}` | {rate} | {q or '0'} | {term} | {num} | {kr} | {lost} | {js} | "
                 f"{ratio if ratio is not None else '—'} |")
    L += ["",
          "> `함정 정답률` 분모에서 **미실행(`—`)과 불명(`?`)을 제외**한다. "
          "미실행을 오답으로 세어 정답률을 52%로 오독한 사고가 있었다(PoC 문서 2.3).",
          "> `불명`은 기계가 판정하지 않고 육안으로 올린 건수다 → `review_traps.md`",
          "> `미번역 잔존`에서 제품명 유지 세그먼트는 제외한다 — 한글이 남는 것이 정답이다.",
          "> `숫자 보존`은 **환각 축의 일부**다. 원문에 없는 정보를 지어내는 유형은 "
          "기계로 못 잡으며 3단계 결승에서 judge가 맡는다(7-4 `added_info`).", ""]

    # 2-1. 숫자 누락 상세 — 환각 육안 확인용
    if any(quant[t]["nlost"] for t in labels):
        L += ["### 2-1. 숫자·단위 누락 상세", "",
              "성분 함량·임상 인원이 틀리면 안전·법적 문제가 된다. 전수 확인할 것.", "",
              "| 대상 | 세그먼트 | 원문 | 누락된 값 | 번역문 |", "|---|---|---|---|---|"]
        src_by_id = {s["id"]: src_text(s) for s in segs}
        for t in labels:
            for sid, miss, tr_text in quant[t]["nlost"]:
                L.append(f"| `{t}` | {sid} | {esc(src_by_id.get(sid, ''))} | **{miss}** | "
                         f"{esc(tr_text)} |")
        L.append("")

    # 3. 예선 필수 통과 조건
    L += ["## 3. 예선 필수 통과 조건", "",
          "정량 상위라도 하나라도 못 지키면 탈락 (PLAN.md 4-2).", "",
          "| 대상 | JSON 파싱 실패 | 세그먼트 누락 | 미번역 잔존 | 판정 |",
          "|---|---|---|---|---|"]
    for t in labels:
        c = quant[t]
        ok = c["parse_fail"] == 0 and c["lost"] == 0 and c["kr"] == 0
        L.append(f"| `{t}` | {c['parse_fail']} | {c['lost']} | {c['kr']} | "
                 f"{'통과' if ok else '**탈락**'} |")
    L.append("")

    # 4. 함정 정답률 상세
    if flagged:
        L += ["## 4. 함정 정답률 — 기대 동작 대비 정오", "",
              "**치환 여부가 아니다.** 부인·고지 문맥 / 인용문 / 제품명은 "
              "**치환하지 않는 것**이 정답이다.", "",
              "| 세그먼트 | 금지표현 | 유형 | 기대 | " + " | ".join(f"`{t}`" for t in labels) + " |",
              "|---|---|---|---|" + "---|" * len(labels)]
        for sid, b in flagged:
            kind, expect = TRAPS.get(sid, ("대조군", "치환"))
            cells = " | ".join(verdicts[t][(sid, b)][0] for t in labels)
            L.append(f"| {sid} | {b} | {kind} | {expect} | {cells} |")
        L += ["", "> `O` 정답 · `X` 오답 · `?` **불명(육안 판정 필요)** · `—` **미실행**", ""]

        L += ["### 유형별 정답률", "",
              "| 유형 | " + " | ".join(f"`{t}`" for t in labels) + " |",
              "|---|" + "---|" * len(labels)]
        kinds = sorted({TRAPS.get(sid, ("대조군", "치환"))[0] for sid, _ in flagged})
        for k in kinds:
            pairs = [p for p in flagged if TRAPS.get(p[0], ("대조군", "치환"))[0] == k]
            cells = []
            for t in labels:
                o = sum(1 for p in pairs if verdicts[t][p][0] == "O")
                x_ = sum(1 for p in pairs if verdicts[t][p][0] == "**X**")
                cells.append(f"{o}/{o + x_}" if (o + x_) else "—")
            L.append(f"| {k} | " + " | ".join(cells) + " |")
        L += ["", "> `유지` 기대 유형(A 부인 / C 제품명 / D 인용)이 변별의 핵심이다.", ""]

    # 4-1. 양립 유형 처리 방침 — 점수가 아니라 모델 특성이다
    amb = [(sid, b) for sid, b in flagged
           if TRAPS.get(sid, ("", ""))[1] == "양립"]
    if amb:
        L += ["### 양립 유형 처리 방침 — 우열이 아니라 **모델 특성**", "",
              "`양립`은 치환·유지 둘 다 정답으로 인정한 자리다. 어느 쪽을 골랐는지는 "
              "점수에 반영하지 않되, **벤더별 방침 차이가 실재하므로 기록한다.**", "",
              "| 대상 | 치환 | 유지 | 방침 |", "|---|---|---|---|"]
        for t in labels:
            rep = sum(1 for k in amb if verdicts[t][k][1].startswith("치환"))
            kep = sum(1 for k in amb if verdicts[t][k][1].startswith("유지"))
            kind = ("**치환형**" if rep > kep else "**유지형**" if kep > rep else "혼재")
            L.append(f"| `{t}` | {rep} | {kep} | {kind} |")
        L += ["", "> `치환형` — UI 라벨·카테고리도 규제 적용 대상으로 본다",
              "> `유지형` — 분류 체계이므로 바꾸지 않는다",
              "> **팀이 규제 표의 적용 범위를 정하면 어느 쪽이 맞는지 결정된다**(PLAN.md 3-4).", ""]

    # 5. 세그먼트별 대조
    L += ["## 5. 세그먼트별 대조", ""]
    for doc in ev["documents"]:
        L += [f"### {Path(doc['image']).stem}", "",
              "| # | 원문 | " + " | ".join(f"`{t}`" for t in labels) + " |",
              "|---|---|" + "---|" * len(labels)]
        for s in doc["segments"]:
            cells = []
            for t in labels:
                tr, note = data[t].get(s["id"], ("", ""))
                cells.append(esc(tr) + (f" _({esc(note)})_" if note else ""))
            L.append(f"| {s['id'].split('-')[-1]} | {esc(src_text(s))} | " + " | ".join(cells) + " |")
        L.append("")

    (HERE / "summary.md").write_text("\n".join(L), encoding="utf-8")

    # ── REVIEW.md — 육안 확정 작업지 (단일) ──────────────────
    # 사람이 채워야 할 것을 한 장에 모은다. 기계 판정은 후보를 좁히는 데까지이고
    # 확정은 사람이 한다(CLAUDE.md). 확정 칸은 **비워서** 낸다.
    src_map = {s["id"]: src_text(s) for s in segs}
    unknown = [(t, sid, b) for t in labels for (sid, b), v in verdicts[t].items() if v[0] == "?"]
    wrong = [(t, sid, b) for t in labels for (sid, b), v in verdicts[t].items() if v[0] == "**X**"]

    R = ["# C. 로컬라이징 번역 — 육안 확정 작업지", "",
         "> 자동 생성. `compare.py` 재실행 시 덮어씀.",
         "> **확정 칸은 비어 있다. 사람이 채운다**(CLAUDE.md — 등급을 코드가 채우지 않는다).", "",
         "## 대기 현황", "",
         "| 절 | 무엇을 정하는가 | 건수 | 우선순위 |", "|---|---|---|---|",
         f"| 1 | 함정 **불명(`?`)** — 기계가 판정을 보류한 건 | {len(unknown)} | **필수** |",
         f"| 2 | 함정 **오답(`X`)** 재확인 | {len(wrong)} | 권장 |",
         f"| 3 | 번역 품질 **A/B/C 등급** | 대상 {len(labels)}종 | **필수** |", "",
         "> **judge 불일치는 육안 대상이 아니다** [확정 2026-08-25 / 예람님].",
         "> 채점자 2종이 갈린 건을 사람이 다시 채점하지 않는다. 대신 **불일치가 적은 모델**,",
         "> 즉 두 채점자가 더 잘 합의한 모델을 우선한다. 건수는 `scores/FINALS.md` 1절 참조.", ""]

    R += ["---", "", "## 1. 함정 불명 — 기계가 판정하지 않은 건", "",
          "대체표현·직역형이 둘 다 검출되거나 둘 다 없어 **기계가 정하지 않고 올린 것**이다.", ""]
    if unknown:
        R += ["| 대상 | 유형 | 기대 | **규제 매핑** | 원문 | 번역 | **확정(O/X)** |",
              "|---|---|---|---|---|---|---|"]
        for t, sid, b in unknown:
            kind, expect = TRAPS.get(sid, ("대조군", "치환"))
            R.append(f"| `{t}` | {kind} | {expect} | `{b}` → `{rows[b]}` | "
                     f"{esc(src_map.get(sid))} | {esc(data[t].get(sid, ('', ''))[0])} |  |")
    else:
        R.append("_없음_")
    R.append("")

    R += ["---", "", "## 2. 함정 오답 재확인", "",
          "기계가 오답으로 판정한 건이다. **정말 오답인지** 확인한다.", ""]
    if wrong:
        R += ["| 대상 | 유형 | 기대 | **규제 매핑** | 원문 | 번역 | **확정(유지/정정)** |",
              "|---|---|---|---|---|---|---|"]
        for t, sid, b in wrong:
            kind, expect = TRAPS.get(sid, ("대조군", "치환"))
            R.append(f"| `{t}` | {kind} | {expect} | `{b}` → `{rows[b]}` | "
                     f"{esc(src_map.get(sid))} | {esc(data[t].get(sid, ('', ''))[0])} |  |")
    else:
        R.append("_없음_")
    R.append("")

    R += ["---", "", "## 3. 번역 품질 등급", "",
          "함정 정답률은 **규제 처리만** 잰다. 번역의 자연스러움·현지화는 이 표가 맡는다.", "",
          "| 대상 | **등급 (A/B/C)** | 근거 |", "|---|---|---|"]
    R += [f"| `{t}` |  |  |" for t in labels]
    R.append("")
    (HERE / "REVIEW.md").write_text("\n".join(R), encoding="utf-8")

    # ── 콘솔 ─────────────────────────────────────────────────
    print("작성 완료: summary.md / REVIEW.md")
    print(f"  대상 {len(labels)}종: {', '.join(labels)}")
    print(f"  함정 {len(flagged)}쌍 (기대=유지 "
          f"{sum(1 for sid, _ in flagged if TRAPS.get(sid, ('', '치환'))[1] == '유지')}쌍)")
    if not has_terms:
        print("  [!] expect_term 없음 - 용어 정확도 미집계 (평가셋 v3에서 추가)")
    for w in warn:
        print(f"  [!] {w}")
    for t in labels:
        c = quant[t]
        print(f"  {t:<24} 정답률 {c['rate']:>4}  불명 {c['unknown']:>2}  "
              f"미실행 {c['miss']:>2}  누락 {c['lost']:>2}  한글잔존 {c['kr']:>2}")


if __name__ == "__main__":
    main()
