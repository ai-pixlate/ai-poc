"""섹션 단위 규제·현지 부적합 판정 — VLM variant (sec_only · sec_adj · sec_outline).

`gemini-3.8-flash`에 섹션 이미지와 블록을 주고, 8항목마다 **해당 / 애매**인 것만 받는다.
사이트 정책이 미정이라 항목 판정만 받고, 정책별 결정(유지·확인 필요·제외)은 로컬에서 낸다.
    해당 → 제외 · 애매 → 확인 필요 · 목록에 없음 → 유지 (rule_kw와 같은 정책 계산)

variant — 맥락을 한 단계씩 더한다. 판정 대상·출력 형식은 같다.
    sec_only     섹션 이미지 + 섹션 블록(role · 위치 · 글자 높이)
    sec_adj      sec_only + 앞뒤 섹션 블록 텍스트 (참고용 — 판정 대상 아님)
    sec_outline  sec_adj + 페이지 개요 (섹션별 이름 · 한 줄 요약 · 현재 위치 표시)

페이지 개요 — 페이지당 1호출(텍스트만). 섹션별 블록 텍스트를 주고 이름·요약을 받는다.
    color_snap_vlm2는 배경색 절단 섹션에 이름이 없어 새로 만든다.

이미지 — 긴 변 1024px(vlm_relation과 같음). **4,000px 초과 섹션은 200px 겹쳐 2조각**으로
    같은 호출에 넣는다(골든 1개 · 4,491px). 블록 좌표는 섹션 원본 좌표 그대로 준다.

편향 — "애매하면 애매" — 미탐은 정책 위반 게시, 오탐은 검수에서 되살림.
항목 경계(브랜드 자체 시험 vs 사용자 설문 vs 리뷰)는 **팀 정의 미정** — 프롬프트의 정의는 초안.

출력
    results/{variant}/prompts/{섹션}.txt       보낸 텍스트
    results/{variant}/decisions/{섹션}.json    정책별 결정 · 항목 판정 · 근거 블록 · 관련 섹션
    results/{variant}/vis/sections · vis/pages/{policy}
    results/{variant}/meta.json                호출 · 토큰 · 비용 · 소요 · 오류
    results/outline/{stem}.json                페이지 개요
    cache/{model}/{variant}_{지문}/{섹션}.json · cache/{model}/outline_{지문}/{stem}.json

사용법
    python run_vlm.py --variant all --dry-run                 # 호출 없이 프롬프트·추정 비용
    python run_vlm.py --variant sec_only --sections A000000250199_009_003
    python run_vlm.py --variant all --concurrency 4
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

import run as base

Image.MAX_IMAGE_PIXELS = None

HERE = base.HERE
ROOT = base.ROOT
RESULTS = base.RESULTS
CACHE = HERE / "cache"

VARIANTS = {
    "sec_only": dict(adj=False, outline=False),
    "sec_adj": dict(adj=True, outline=False),
    "sec_outline": dict(adj=True, outline=True),
}

MODEL = {
    "model_id": "gemini-3.8-flash",
    "env_key": "GOOGLE_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "price_in": 0.75,
    "price_out": 3.75,
}

VLM_MAX_SIDE = 1024
SPLIT_OVER = 4000      # 이보다 긴 섹션은 2조각
SPLIT_OVERLAP = 200
BLOCK_CHARS = 300      # 판정 대상 블록 텍스트 최대 글자 (성분표 등 긴 블록 절단)
ADJ_CHARS = 600        # 앞뒤 섹션 텍스트 최대 글자
OUTLINE_IN_CHARS = 400 # 개요 생성 시 섹션당 텍스트 최대 글자

# 추정용 — vlm_relation 실측(in 216,415 / 102호출) 역산. 확정값 아님
EST_IMG_TOKENS = 1100
EST_CHARS_PER_TOKEN = 1.4
EST_OUT_TOKENS = {"judge": 250, "outline": 60}   # 호출당 · 개요는 섹션당

ITEM_DEFS = """- review (사용자 리뷰·후기): 소비자가 쓴 사용 후기·리뷰 인용, 별점, 리뷰 캡처, 가린 이름(홍길*님)과 함께 실린 소감
- survey (설문·만족도): 사용자 대상 설문·만족도 조사 결과(N% 만족, N명이 인정 등). 인체적용시험의 측정 수치(주름 -N%)는 해당 아님 — 단, 시험 참여자 만족도 조사는 해당
- influencer (체험단·인플루언서): 체험단·서포터즈·인플루언서·크리에이터의 사용·추천, 협찬 표기
- before_after (비포·애프터): 사용 전후를 나란히 비교한 사진·수치
- comparison (타사 비교): 다른 회사·다른 제품과의 우열 비교(자사 다른 제품과의 비교 포함)
- price_event (가격·이벤트): 가격, 할인, 쿠폰, 증정, 1+1, 기획 구성, 구매 인증 이벤트, 기간 한정 행사
- external_rank (외부 채널·랭킹): 특정 쇼핑몰·플랫폼의 판매 랭킹·수상·어워즈, 다른 판매처·SNS·메신저·QR·URL 안내
- efficacy_drug (효능·의약품 오인): 질병 치료·예방, 의약품·시술과 같은 효과를 내세우는 표현"""

SYSTEM = f"""너는 한국 이커머스 상품 상세페이지를 해외 판매 사이트에 올리기 전에 검토한다.
사이트마다 게시를 금지하는 내용이 다르다. 너는 **한 섹션**에 아래 항목의 내용이 들어 있는지 판정한다.
게시 여부 결정은 네가 하지 않는다 — 항목별 판정만 한다.

항목
{ITEM_DEFS}

입력
- 섹션 이미지(길면 위아래 2조각). 이미지 속 사진·그래픽도 판정 근거다 — 글자가 없어도 전후 비교 사진·리뷰 캡처면 해당
- 섹션 블록 목록 `b번호 [역할] y위치 (글자 높이) 텍스트`. OCR이라 오타가 있을 수 있다
- 주어지면: 앞뒤 섹션 텍스트, 페이지 개요. **참고용이다. 판정 대상은 현재 섹션뿐이다.**
  앞뒤 맥락 때문에 현재 섹션의 성격이 달라지면(예: 앞 섹션 제목이 '실제 고객 후기'이고 현재 섹션은 인용문만 있음) 반영하고, 그 섹션 id를 related_sections에 적는다.

판정
- status: `해당`(분명히 들어 있음) / `애매`(들어 있을 수 있음). 해당 없는 항목은 적지 않는다.
- **애매하면 `애매`로 적는다.** 놓치는 것이 잘못 잡는 것보다 나쁘다.
- 부인·안내 문구("리뷰 작성은 필요 없어요")처럼 항목 내용 자체가 아닌 언급은 해당이 아니다.
- coverage: 항목 내용이 섹션의 거의 전부면 `전체`, 다른 내용과 섞여 일부면 `일부`.
- blocks: 근거 블록 번호. 이미지에서만 보이는 근거면 빈 배열로 두고 reason에 적는다.

출력은 JSON 하나. 설명을 붙이지 않는다.
{{"items": [{{"item": "review", "status": "해당", "coverage": "일부", "blocks": [3, 4], "related_sections": [], "reason": "고객 이름과 함께 사용 소감 인용"}}]}}
해당 항목이 없으면 {{"items": []}}"""

OUTLINE_SYSTEM = """너는 한국 이커머스 상품 상세페이지의 섹션 목록을 받아 개요를 만든다.
섹션마다 OCR 텍스트(오타 있음)가 있다. 섹션마다 짧은 이름(15자 이내)과 한 줄 요약(40자 이내)을 쓴다.
요약에는 섹션의 성격(브랜드 설명 / 자체 시험 결과 / 사용자 후기 / 설문 / 이벤트 / 사용법 / 고시 정보 등)이 드러나게 쓴다.
글자가 없는 섹션은 앞뒤 흐름으로 추정하고 요약 끝에 "(추정)"을 붙인다.

출력은 JSON 하나.
{"sections": [{"section": "섹션 id", "name": "이름", "summary": "요약"}]}"""


def fingerprint(*parts) -> str:
    raw = json.dumps([MODEL["model_id"], VLM_MAX_SIDE, SPLIT_OVER, SPLIT_OVERLAP,
                      BLOCK_CHARS, ADJ_CHARS, OUTLINE_IN_CHARS, *parts], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


# ---------------------------------------------------------------- 입력

def cut(t: str, n: int) -> str:
    t = " / ".join(x for x in t.split("\n") if x.strip())
    return t if len(t) <= n else t[:n] + "…"


def block_lines(sec: dict) -> list[str]:
    out = []
    for i, b in enumerate(sec["blocks"], 1):
        if not b["text"].strip():
            continue
        out.append(f"b{i} [{b['role']}] y{b['bbox'][1]}~{b['bbox'][3]} ({b['font_h']}px) "
                   f"{cut(b['text'], BLOCK_CHARS)}")
    return out


def section_text(sec: dict, n: int) -> str:
    return cut(" | ".join(b["text"] for b in sec["blocks"] if b["text"].strip()), n) or "[글자 없음]"


def images_of(sec: dict) -> list[str]:
    im = Image.open(sec["crop"]).convert("RGB")
    h = im.height
    if h > SPLIT_OVER:
        mid = h // 2
        parts = [im.crop((0, 0, im.width, mid + SPLIT_OVERLAP // 2)),
                 im.crop((0, mid - SPLIT_OVERLAP // 2, im.width, h))]
    else:
        parts = [im]
    out = []
    for p in parts:
        r = min(1.0, VLM_MAX_SIDE / max(p.size))
        if r < 1:
            p = p.resize((round(p.width * r), round(p.height * r)), Image.LANCZOS)
        buf = io.BytesIO()
        p.save(buf, format="JPEG", quality=85)
        out.append(base64.b64encode(buf.getvalue()).decode())
    return out


def build_prompt(sec: dict, by_id: dict, cfg: dict, outline: dict | None) -> str:
    L = [f"현재 섹션 {sec['section']} · 폭 1000 · 높이 {sec['height']}px"
         + (" · 이미지 2조각(위·아래, 200px 겹침)" if sec["height"] > SPLIT_OVER else ""), ""]
    if cfg["outline"] and outline:
        L.append("[페이지 개요 — 참고]")
        for o in outline["sections"]:
            mark = "  ◀ 현재" if o["section"] == sec["section"] else ""
            L.append(f"- {o['section']} {o['name']} — {o['summary']}{mark}")
        L.append("")
    if cfg["adj"]:
        for tag, sid in (("앞 섹션", sec["prev"]), ("뒤 섹션", sec["next"])):
            L.append(f"[{tag} — 참고] " + (f"{sid}: {section_text(by_id[sid], ADJ_CHARS)}"
                                            if sid else "없음"))
        L.append("")
    L.append("[현재 섹션 블록 — 판정 대상]")
    L += block_lines(sec) or ["(글자 없음 — 이미지로만 판정)"]
    return "\n".join(L)


def outline_prompt(stem: str, secs: list[dict]) -> str:
    L = [f"페이지 {stem} · 섹션 {len(secs)}개 (위에서 아래 순)", ""]
    for s in secs:
        L.append(f"{s['section']} (높이 {s['height']}px): {section_text(s, OUTLINE_IN_CHARS)}")
    return "\n".join(L)


# ---------------------------------------------------------------- 호출

def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def make_client():
    load_env()
    key = os.environ.get(MODEL["env_key"])
    if not key:
        raise SystemExit(f"{MODEL['env_key']} 없음 — .env 확인")
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=MODEL["base_url"])


def ask(client, system: str, text: str, images: list[str]) -> tuple[dict, dict, float]:
    content: list | str = text
    if images:
        content = [{"type": "text", "text": text}]
        for i, b in enumerate(images, 1):
            if len(images) > 1:
                content.append({"type": "text", "text": f"[이미지 {i}/{len(images)}]"})
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}})
    t0 = time.perf_counter()
    for attempt in range(5):
        try:
            res = client.chat.completions.create(
                model=MODEL["model_id"], temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": content}],
            )
            break
        except Exception as e:  # noqa: BLE001
            if "503" not in str(e) or attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
    usage = {"in": res.usage.prompt_tokens, "out": res.usage.completion_tokens}
    return json.loads(res.choices[0].message.content), usage, time.perf_counter() - t0


def cached(path: Path, no_cache: bool, fn):
    """캐시 우선. 반환 (응답, 토큰, 소요초 또는 None=캐시)."""
    if path.exists() and not no_cache:
        c = json.loads(path.read_text(encoding="utf-8"))
        return c["answer"], c["usage"], None
    ans, usage, sec = fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"answer": ans, "usage": usage, "sec": round(sec, 2)},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return ans, usage, sec


def usd(t_in: float, t_out: float) -> float:
    return t_in / 1e6 * MODEL["price_in"] + t_out / 1e6 * MODEL["price_out"]


def validate(sec: dict, ans: dict, page_ids: set[str]) -> tuple[dict, list[str]]:
    """응답을 hits로 바꾼다. 계약 위반은 오류 목록에 남기고 해당 값만 버린다."""
    errs, hits = [], {}
    items = ans.get("items") if isinstance(ans, dict) else None
    if not isinstance(items, list):
        return {}, [f"items 배열 없음: {str(ans)[:120]}"]
    n = len(sec["blocks"])
    for it in items:
        k = it.get("item")
        if k not in base.ITEM_NAME:
            errs.append(f"모르는 항목 {k}")
            continue
        st = it.get("status")
        if st not in ("해당", "애매"):
            errs.append(f"{k} status={st}")
            st = "애매"
        blocks = []
        for b in it.get("blocks") or []:
            try:
                b = int(b)
            except (TypeError, ValueError):
                errs.append(f"{k} 블록 {b}")
                continue
            if 1 <= b <= n:
                blocks.append(b - 1)
            else:
                errs.append(f"{k} 범위 밖 블록 b{b}")
        related = [r for r in it.get("related_sections") or [] if r in page_ids and r != sec["section"]]
        hits[k] = {"decision": "제외" if st == "해당" else "확인 필요", "status": st,
                   "coverage": it.get("coverage"), "blocks": sorted(set(blocks)),
                   "keywords": [f"{st}·{it.get('coverage') or '?'}"],
                   "related_sections": related, "reason": it.get("reason", "")}
    return hits, errs


# ---------------------------------------------------------------- 실행

def build_outlines(client, secs: list[dict], dry: bool, no_cache: bool) -> tuple[dict, dict]:
    by_page: dict[str, list[dict]] = {}
    for s in secs:
        by_page.setdefault(s["stem"], []).append(s)
    fp = fingerprint("outline", OUTLINE_SYSTEM)
    stat = {"calls": 0, "cache": 0, "in": 0, "out": 0, "sec": 0.0, "chars": 0, "errors": []}
    outlines = {}
    for stem, ss in by_page.items():
        prompt = outline_prompt(stem, ss)
        stat["chars"] += len(prompt) + len(OUTLINE_SYSTEM)
        if dry:
            continue
        ans, usage, sec = cached(CACHE / MODEL["model_id"] / f"outline_{fp}" / f"{stem}.json", no_cache,
                                 lambda: ask(client, OUTLINE_SYSTEM, prompt, []))
        stat["in"] += usage["in"]
        stat["out"] += usage["out"]
        if sec is None:
            stat["cache"] += 1
        else:
            stat["calls"] += 1
            stat["sec"] += sec
        got = {o.get("section"): o for o in ans.get("sections", []) if isinstance(o, dict)}
        rows = []
        for s in ss:
            o = got.get(s["section"])
            if not o:
                stat["errors"].append(f"{stem}: {s['section']} 개요 없음")
                o = {"name": "?", "summary": "?"}
            rows.append({"section": s["section"], "name": o.get("name", "?"), "summary": o.get("summary", "?")})
        outlines[stem] = {"stem": stem, "sections": rows}
        (RESULTS / "outline").mkdir(parents=True, exist_ok=True)
        (RESULTS / "outline" / f"{stem}.json").write_text(
            json.dumps(outlines[stem], ensure_ascii=False, indent=1), encoding="utf-8")
    stat["pages"] = len(by_page)
    return outlines, stat


def run_variant(name: str, client, secs: list[dict], only: list[str] | None,
                outlines: dict, dry: bool, no_cache: bool, conc: int) -> dict:
    cfg = VARIANTS[name]
    by_id = {s["section"]: s for s in secs}
    page_ids = {}
    for s in secs:
        page_ids.setdefault(s["stem"], set()).add(s["section"])
    todo = [s for s in secs if not only or s["section"] in only]
    fp = fingerprint(name, SYSTEM, cfg)
    out = RESULTS / name
    (out / "prompts").mkdir(parents=True, exist_ok=True)

    prompts, imgs = {}, {}
    for s in todo:
        prompts[s["section"]] = build_prompt(s, by_id, cfg, outlines.get(s["stem"]))
        (out / "prompts" / f"{s['section']}.txt").write_text(prompts[s["section"]], encoding="utf-8")
        imgs[s["section"]] = 2 if s["height"] > SPLIT_OVER else 1

    chars = sum(len(p) + len(SYSTEM) for p in prompts.values())
    n_img = sum(imgs.values())
    est_in = chars / EST_CHARS_PER_TOKEN + n_img * EST_IMG_TOKENS
    est_out = len(todo) * EST_OUT_TOKENS["judge"]
    report = {"variant": name, "fingerprint": fp, "sections": len(todo), "images": n_img,
              "chars": chars, "est_in": round(est_in), "est_out": est_out,
              "est_usd": round(usd(est_in, est_out), 4)}
    if dry:
        return report

    def one(s):
        sid = s["section"]
        try:
            ans, usage, sec = cached(CACHE / MODEL["model_id"] / f"{name}_{fp}" / f"{sid}.json", no_cache,
                                     lambda: ask(client, SYSTEM, prompts[sid], images_of(s)))
            return s, ans, usage, sec, None
        except Exception as e:  # noqa: BLE001
            return s, None, {"in": 0, "out": 0}, None, f"{type(e).__name__}: {str(e)[:160]}"

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        results = list(ex.map(one, todo))
    wall = time.perf_counter() - t0

    tin = tout = calls = cache_hits = 0
    live_in = live_out = 0      # 비용은 이번에 실제 호출한 것만
    call_sec, errors, per = [], [], []
    hits_all, decs = {}, {p: {} for p in base.POLICIES}
    for s, ans, usage, sec, err in results:
        sid = s["section"]
        tin += usage["in"]
        tout += usage["out"]
        if err:
            errors.append({"section": sid, "error": err})
            continue
        if sec is None:
            cache_hits += 1
        else:
            calls += 1
            call_sec.append(sec)
            live_in += usage["in"]
            live_out += usage["out"]
        hits, verr = validate(s, ans, page_ids[s["stem"]])
        errors += [{"section": sid, "error": e} for e in verr]
        hits_all[sid] = hits
        for p, items in base.POLICIES.items():
            decs[p][sid] = base.decide(hits, items)
        doc = {"section": sid, "variant": name, "range": s["range"], "height": s["height"],
               "prev": s["prev"], "next": s["next"],
               "no_text": not any(b["text"].strip() for b in s["blocks"]),
               "decisions": {p: decs[p][sid] for p in base.POLICIES},
               "hits": [{"item": k, "name": base.ITEM_NAME[k], "decision": v["decision"],
                         "status": v["status"], "coverage": v["coverage"], "blocks": v["blocks"],
                         "texts": [s["blocks"][i]["text"][:80] for i in v["blocks"]],
                         "related_sections": v["related_sections"], "reason": v["reason"]}
                        for k, v in hits.items()],
               "images": imgs[sid], "tokens": usage, "sec": None if sec is None else round(sec, 2)}
        (out / "decisions").mkdir(parents=True, exist_ok=True)
        (out / "decisions" / f"{sid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
        base.vis_section(s, hits, out / "vis" / "sections" / f"{sid}.jpg")
        per.append({"section": sid, "in": usage["in"], "out": usage["out"],
                    "sec": doc["sec"], "items": list(hits)})
        print(f"  [{name}] {sid}  {decs['all'][sid]:<5}  {','.join(hits) or '-':<30} "
              f"in {usage['in']} out {usage['out']}  {'캐시' if sec is None else f'{sec:.1f}s'}")

    if not only:
        by_page: dict[str, list[dict]] = {}
        for s in secs:
            if s["section"] in hits_all:
                by_page.setdefault(s["stem"], []).append(s)
        for p, items in base.POLICIES.items():
            for stem, ss in by_page.items():
                base.vis_page(stem, ss, decs[p], hits_all, items,
                              out / "vis" / "pages" / p / f"{stem}.jpg", variant=name)

    report.update({"calls": calls, "cache_hits": cache_hits, "errors": errors,
                   "tokens": {"in": tin, "out": tout}, "cost_usd": round(usd(live_in, live_out), 4),
                   "wall_sec": round(wall, 2), "sum_call_sec": round(sum(call_sec), 2),
                   "concurrency": conc, "partial": bool(only),
                   "policies": {p: {k: sum(1 for v in decs[p].values() if v == k) for k in base.RANK}
                                for p in base.POLICIES},
                   "items": {k: {d: sum(1 for h in hits_all.values() if k in h and h[k]["decision"] == d)
                                 for d in ("제외", "확인 필요")} for k, _, _ in base.ITEMS},
                   "cfg": {"model": MODEL["model_id"], "temperature": 0, **cfg,
                           "image_max_side": VLM_MAX_SIDE, "split_over": SPLIT_OVER},
                   "per_section": per, "run_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    if not only:
        (out / "meta.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--sections", nargs="*", default=None, help="일부 섹션만 (meta·페이지 vis 안 씀)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--concurrency", type=int, default=1)
    args = ap.parse_args()
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for n in names:
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}")

    secs = base.load_sections()
    client = None if args.dry_run else make_client()

    outlines, ostat = {}, None
    if "sec_outline" in names:
        need = None if not args.sections else {s["stem"] for s in secs if s["section"] in args.sections}
        osecs = [s for s in secs if need is None or s["stem"] in need]
        outlines, ostat = build_outlines(client, osecs, args.dry_run, args.no_cache)
        if args.dry_run:
            # 개요가 아직 없으므로 이름 10자 · 요약 30자 자리표시로 프롬프트 길이만 맞춘다
            for s in osecs:
                outlines.setdefault(s["stem"], {"sections": []})["sections"].append(
                    {"section": s["section"], "name": "〇" * 10, "summary": "〇" * 30})
        est_in = ostat["chars"] / EST_CHARS_PER_TOKEN
        est_out = len(osecs) * EST_OUT_TOKENS["outline"]
        if args.dry_run:
            print(f"[outline] 페이지 {ostat['pages']} · {ostat['chars']:,}자 · 추정 in {est_in:,.0f} out {est_out:,} "
                  f"· ${usd(est_in, est_out):.4f}")
        else:
            print(f"[outline] 호출 {ostat['calls']} · 캐시 {ostat['cache']} · in {ostat['in']} out {ostat['out']} "
                  f"· ${usd(ostat['in'], ostat['out']) if ostat['calls'] else 0:.4f} · {ostat['sec']:.1f}s"
                  f"{' · 오류 ' + str(len(ostat['errors'])) if ostat['errors'] else ''}")

    total = usd(ostat["chars"] / EST_CHARS_PER_TOKEN, len(secs) * EST_OUT_TOKENS["outline"]) \
        if (ostat and args.dry_run) else 0
    for n in names:
        r = run_variant(n, client, secs, args.sections, outlines, args.dry_run, args.no_cache, args.concurrency)
        if args.dry_run:
            total += r["est_usd"]
            print(f"[{n}] 지문 {r['fingerprint']} · 섹션 {r['sections']} · 이미지 {r['images']} · "
                  f"{r['chars']:,}자 · 추정 in {r['est_in']:,} out {r['est_out']:,} · ${r['est_usd']:.4f}")
        else:
            print(f"[{n}] 호출 {r['calls']} · 캐시 {r['cache_hits']} · 오류 {len(r['errors'])} · "
                  f"in {r['tokens']['in']} out {r['tokens']['out']} · ${r['cost_usd']:.4f} · "
                  f"벽시계 {r['wall_sec']}s (호출 합 {r['sum_call_sec']}s)")
            print(f"    정책 all {r['policies']['all']} · review_ban {r['policies']['review_ban']}")
    if args.dry_run:
        print(f"→ 추정 합계 ${total:.4f} (이미지 {EST_IMG_TOKENS}토큰/장 · {EST_CHARS_PER_TOKEN}자/토큰 가정). 호출 없음")
    else:
        import compare
        compare.build()


if __name__ == "__main__":
    main()
