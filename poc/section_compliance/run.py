"""섹션 단위 규제·현지 부적합 판정 — rule_kw 기준선.

게시 대상 사이트 정책(예: 사이트 A는 사용자 리뷰 게시 금지)에 걸리는 섹션을 찾아
**유지 / 제외 / 확인 필요**를 가른다. 이 파일은 비용 0 기준선이다.
VLM variant(sec_only · sec_adj · sec_outline)는 같은 입력 조립(`load_sections`)을 쓴다.

판정 규칙 (rule_kw)
    섹션 블록 텍스트를 항목별 키워드·정규식과 대조한다.
    항목마다 **서로 다른 키워드 2개 이상** 적중 → 제외 / 1개 → 확인 필요 / 0개 → 유지.
    정책에서 켠 항목 중 가장 무거운 결정이 섹션 결정이 된다.
    전후 비교는 단어 하나로는 못 가르므로 '사용 전'과 '사용 후'가 **함께** 있을 때만 적중.
    글자 없는 섹션은 유지로 두되 `no_text`로 표시 — 이미지 판단은 VLM variant 몫.

키워드 작성 — 항목별 일반 어휘에 **골든 102섹션 텍스트를 읽고 본 표현**을 더했다.
    평가 표본과 작성 표본이 같아 이 표본 성적은 낙관적이다. 키워드는 현 상태로 고정하고
    판정표 작성 후에는 고치지 않는다. 결정 기준(키워드 2개)은 임의값. 한계 전문은 summary.md.

사이트 정책 — **실제 정책 미정.** 아래는 가정.
    all         8항목 전부 금지 — 키워드 적중 전체를 보기 위한 상한
    review_ban  사용자 리뷰·후기만 금지 — 예시(사이트 A)

입력
    poc/golden/2_block_role/results/llm_assist/blocks/{섹션}.json      블록 + role
    poc/section_split/results/color_snap_vlm2/crops/{stem}/{i}.jpg     섹션 이미지
    poc/section_split/results/color_snap_vlm2/sections/{stem}.json     페이지 안 섹션 순서

출력
    results/rule_kw/decisions/{섹션}.json     정책별 결정 · 항목별 적중 키워드 · 근거 블록
    results/rule_kw/vis/sections/{섹션}.jpg   섹션 이미지에 근거 블록 박스(항목별 색)
    results/rule_kw/vis/pages/{policy}/{stem}.jpg  페이지 썸네일에 섹션별 결정 색
    results/rule_kw/meta.json
    summary.md                                요약 · 섹션별 적중 · 판정표(등급 칸 비움)

사용법
    python run.py --variant rule_kw
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
BLOCKS = ROOT / "poc" / "golden" / "2_block_role" / "results" / "llm_assist" / "blocks"
SPLIT = ROOT / "poc" / "section_split" / "results" / "color_snap_vlm2"
RESULTS = HERE / "results"

VARIANTS = ("rule_kw",)

# 판정 항목 — 계획서 초안 8항목. (키, 이름, 표시색)
ITEMS = [
    ("review", "사용자 리뷰·후기", (220, 30, 30)),
    ("survey", "설문·만족도", (235, 120, 0)),
    ("influencer", "체험단·인플루언서", (190, 60, 170)),
    ("before_after", "비포·애프터", (40, 110, 230)),
    ("comparison", "타사 비교", (20, 150, 150)),
    ("price_event", "가격·이벤트", (30, 150, 60)),
    ("external_rank", "외부 채널·랭킹", (120, 90, 40)),
    ("efficacy_drug", "효능·의약품 오인", (100, 100, 100)),
]
ITEM_NAME = {k: n for k, n, _ in ITEMS}
ITEM_COLOR = {k: c for k, _, c in ITEMS}

# 키워드 — 공백 제거·소문자 텍스트에 대조. (라벨, 정규식)
# 기준선이므로 넓게 잡는다. 오탐은 VLM variant와의 비교 대상.
KEYWORDS: dict[str, list[tuple[str, str]]] = {
    "review": [
        ("후기", r"후기"),
        ("리뷰", r"리뷰|review"),
        ("별점", r"별점|★{2,}"),
        ("가린 이름+님", r"[가-힣]{1,3}\*(고객)?님"),
        ("실사용", r"실사용|찐사용"),
    ],
    "survey": [
        ("설문", r"설문|survey|서베이"),
        ("만족도", r"만족도"),
        ("긍정 답변율", r"긍정답변|금정답변"),
        ("N명이 인정·평가", r"\d+명이(인정|평가)"),
    ],
    "influencer": [
        ("체험단", r"체험단"),
        ("인플루언서", r"인플루언서|크리에이터|유튜버"),
        ("협찬", r"협찬|광고포함"),
    ],
    "comparison": [
        ("대비", r"대비"),
        ("vs", r"(?<![a-z])vs(?![a-z])"),
        ("타사", r"타사|경쟁사"),
        ("자사 제품 비교", r"자사[가-힣]*(크림|세럼|제품|로션)"),
        ("N배 더", r"\d+(\.\d+)?배더"),
    ],
    "price_event": [
        ("가격", r"\d[\d,]*원(?![가-힣])"),
        ("할인·세일", r"할인|세일|특가|sale"),
        ("쿠폰", r"쿠폰"),
        ("이벤트", r"이벤트|경품|페이백|기프트카드"),
        ("증정·1+1", r"증정|1\+1"),
        ("기획", r"기획"),
    ],
    "external_rank": [
        ("랭킹·1위", r"랭킹|\d위(?![가-힣])|top\d"),
        ("베스트셀러", r"베스트셀러|bestseller"),
        ("어워즈·수상", r"어워즈|award|수상|md'?s?pick"),
        ("QR", r"qr"),
        ("외부 채널", r"인스타그램|카카오|네이버|유튜브|https?:|www\."),
        ("타 쇼핑몰명", r"올리브영|oliveyoung|아마존|amazon"),
    ],
    "efficacy_drug": [
        ("치료", r"치료|완치|처방"),
        ("재생", r"재생"),
        ("의약품", r"의약품|의약외품"),
        ("시술·피부과", r"시술|피부과(?!학)|특수관리"),
    ],
}
BEFORE = re.compile(r"사용전|before|비포")
AFTER = re.compile(r"사용\d*[일주]?후|\d+[일주]사용후|after|애프터")

POLICIES = {
    "all": [k for k, _, _ in ITEMS],
    "review_ban": ["review"],
}
RANK = {"유지": 0, "확인 필요": 1, "제외": 2}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


# ---------------------------------------------------------------- 입력 조립 (VLM variant 공용)

def load_sections() -> list[dict]:
    """섹션 102개 — 페이지 순서대로, 앞뒤 섹션 id 포함."""
    out = []
    for sec_path in sorted((SPLIT / "sections").glob("*.json"),
                           key=lambda p: p.stem):
        page = json.loads(sec_path.read_text(encoding="utf-8"))
        ids = [f"{sec_path.stem}_{s['index']:03d}" for s in page["sections"]]
        for i, s in enumerate(page["sections"]):
            sid = ids[i]
            blk = json.loads((BLOCKS / f"{sid}.json").read_text(encoding="utf-8"))
            out.append({
                "section": sid, "stem": sec_path.stem, "index": s["index"],
                "range": s["range"], "height": s["height"],
                "crop": SPLIT / s["crop"], "blocks": blk["blocks"],
                "prev": ids[i - 1] if i > 0 else None,
                "next": ids[i + 1] if i + 1 < len(ids) else None,
            })
    return out


# ---------------------------------------------------------------- rule_kw

def match_items(blocks: list[dict]) -> dict[str, dict]:
    """항목별 적중 키워드 라벨과 근거 블록 번호."""
    texts = [norm(b["text"]) for b in blocks]
    hits: dict[str, dict] = {}
    for item, pats in KEYWORDS.items():
        labels, where = [], set()
        for label, pat in pats:
            rx = re.compile(pat)
            found = [i for i, t in enumerate(texts) if rx.search(t)]
            if found:
                labels.append(label)
                where.update(found)
        if labels:
            hits[item] = {"keywords": labels, "blocks": sorted(where)}
    b_idx = [i for i, t in enumerate(texts) if BEFORE.search(t)]
    a_idx = [i for i, t in enumerate(texts) if AFTER.search(t)]
    if b_idx and a_idx:
        hits["before_after"] = {"keywords": ["사용 전", "사용 후"],
                                "blocks": sorted(set(b_idx) | set(a_idx))}
    return hits


def item_decision(hit: dict) -> str:
    return "제외" if len(hit["keywords"]) >= 2 else "확인 필요"


def decide(hits: dict[str, dict], items: list[str]) -> str:
    best = "유지"
    for k in items:
        if k in hits and RANK[item_decision(hits[k])] > RANK[best]:
            best = item_decision(hits[k])
    return best


# ---------------------------------------------------------------- vis

def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


DEC_COLOR = {"유지": (60, 170, 80), "확인 필요": (240, 160, 0), "제외": (220, 30, 30)}


def vis_section(sec: dict, hits: dict, out: Path) -> None:
    """섹션 이미지(폭 600)에 근거 블록 박스. 상단 범례에 적중 항목·키워드."""
    im = Image.open(sec["crop"]).convert("RGB")
    scale = 600 / im.width
    im = im.resize((600, max(1, round(im.height * scale))), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    for item, h in hits.items():
        for bi in h["blocks"]:
            x0, y0, x1, y1 = (round(v * scale) for v in sec["blocks"][bi]["bbox"])
            d.rectangle([x0, y0, x1, y1], outline=ITEM_COLOR[item], width=3)
    f = _font(14)
    lines = [f"{sec['section']} · {sec['height']}px"]
    lines += [f"■ {ITEM_NAME[k]} [{item_decision(h)}] — {', '.join(h['keywords'])}"
              for k, h in hits.items()] or ["적중 없음"]
    head = 10 + 20 * len(lines)
    canvas = Image.new("RGB", (600, im.height + head), (255, 255, 255))
    canvas.paste(im, (0, head))
    cd = ImageDraw.Draw(canvas)
    for i, ln in enumerate(lines):
        k = list(hits)[i - 1] if 0 < i <= len(hits) else None
        cd.text((6, 5 + 20 * i), ln, fill=ITEM_COLOR[k] if k else (0, 0, 0), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=88)


def vis_page(stem: str, secs: list[dict], decs: dict[str, str], hits: dict[str, dict],
             items: list[str], out: Path) -> None:
    """페이지 썸네일(폭 240) + 오른쪽 결정 막대(섹션별 색 · 적중 항목 약칭)."""
    src = next(SRC.rglob(f"{stem}.jpg"))
    im = Image.open(src).convert("RGB")
    scale = 240 / im.width
    thumb = im.resize((240, max(1, round(im.height * scale))), Image.BILINEAR)
    bar_w = 150
    head = 50
    canvas = Image.new("RGB", (240 + bar_w, thumb.height + head), (255, 255, 255))
    canvas.paste(thumb, (0, head))
    d = ImageDraw.Draw(canvas)
    f, fs = _font(13), _font(11)
    d.text((4, 4), f"{stem} · rule_kw · 정책 {out.parent.name}", fill=(0, 0, 0), font=f)
    x = 4
    for name, c in DEC_COLOR.items():
        d.rectangle([x, 30, x + 12, 42], fill=c)
        d.text((x + 16, 29), name, fill=(0, 0, 0), font=fs)
        x += 80
    for s in secs:
        y0 = head + round(s["range"][0] * scale)
        y1 = head + round(s["range"][1] * scale)
        c = DEC_COLOR[decs[s["section"]]]
        d.rectangle([240, y0, 240 + bar_w - 1, y1 - 1], fill=c, outline=(255, 255, 255))
        d.line([(0, y0), (239, y0)], fill=(0, 0, 0), width=1)
        tags = [ITEM_NAME[k].split("·")[0] for k in items if k in hits[s["section"]]]
        label = f"#{s['index']} " + " ".join(tags)
        if y1 - y0 >= 14:
            d.text((244, y0 + 1), label[:18], fill=(255, 255, 255), font=fs)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=88)


# ---------------------------------------------------------------- summary

def write_summary(secs: list[dict], hits: dict, decs: dict, meta: dict) -> None:
    L = ["# 섹션 단위 규제·현지 부적합 판정", "",
         "> **2026-09-17 마무리** — `rule_kw` 기준선까지 실행. VLM variant(`sec_only` · `sec_adj` · `sec_outline`) 미실행. 판정표 미작성.",
         "> 계획 `PoC_추가검증_계획.md` 2장. 입력 골든 섹션 102개(`color_snap_vlm2`) · 블록 `llm_assist`.",
         "> **사이트 정책은 미정** — `all`(8항목 전부 금지)·`review_ban`(사용자 리뷰만 금지, 사이트 A 예시)은 가정.",
         "> 판정 칸은 비워둠. 정답 항목은 사람이 채움.", "",
         "## rule_kw — 키워드 기준선", "",
         "| 항목 | 내용 |", "|---|---|",
         "| 규칙 | 항목별 **서로 다른 키워드 2개 이상 → 제외 · 1개 → 확인 필요 · 0개 → 유지**. 전후 비교는 `사용 전`·`사용 후` 동시 적중 |",
         f"| 소요 · 비용 | {meta['sec']}s · 0 |",
         f"| 글자 없는 섹션 | {meta['no_text']}개 — 유지로 둠. 이미지 판단은 VLM variant |", "",
         "### 정책별 결정 수", "",
         "| 정책 | 유지 | 확인 필요 | 제외 |", "|---|---|---|---|"]
    for p in POLICIES:
        c = meta["policies"][p]
        L.append(f"| `{p}` | {c['유지']} | {c['확인 필요']} | {c['제외']} |")
    L += ["", "### 항목별 적중 섹션 수", "",
          "| 항목 | 제외 (키워드 2+) | 확인 필요 (1) | 합 |", "|---|---|---|---|"]
    for k, n, _ in ITEMS:
        c = meta["items"][k]
        L.append(f"| {n} | {c['제외']} | {c['확인 필요']} | {c['제외'] + c['확인 필요']} |")

    L += ["", "### 규칙 작성 방법", "",
          "| 단계 | 내용 |", "|---|---|",
          "| 항목 | 계획서 초안 8항목 그대로 |",
          "| 키워드 | 항목별 일반 어휘 + **골든 102섹션 텍스트를 읽고 본 표현** 추가 — 가린 이름+님(`한기*님`) · `실사용`·`찐사용` · `N명이 인정` · OCR 오타 `금정 답변` · `페이백`·`기프트카드` · `올리브영`·`아마존` · `특수관리` 등 |",
          "| 오탐 예외 | `피부과(?!학)`(한국피부과학연구원) · `\\d원(?![가-힣])`(원료·원하는) · `\\d위(?![가-힣])` · 영문자 사이 `vs` 제외 |",
          "| 결정 기준 | 키워드 2개 이상 제외 · 1개 확인 필요 — **임의값, 데이터로 조정 안 함** |", "",
          "### 한계", "",
          "| # | 한계 |", "|---|---|",
          "| 1 | **평가 표본과 규칙 작성 표본이 같음** — 골든 102섹션을 보고 키워드를 골라 이 표본 성적은 낙관적. 처음 보는 페이지에서 더 낮을 것 |",
          "| 2 | 골든 표기 방식에 맞춘 패턴 포함 — 가린 이름 `*님` 등. 다른 브랜드·쇼핑몰 표기에는 안 맞을 수 있음 |",
          "| 3 | 결정 기준(키워드 2개)이 임의값 |",
          "| 4 | 키워드 유무로는 **맥락을 못 가름** — 리뷰 3건 섹션(`250199_009_003`)이 키워드 1개로 확인 필요에 그침. `리뷰 작성은 필요 없어요`(이벤트) · `실사용자 만족도`(설문)가 리뷰로 걸림 |",
          "| 5 | OCR 깨진 글자(`1위)` · `top14위`) · 논문 초록 속 `vs`가 그대로 걸림 |",
          "| 6 | 글자 없는 섹션은 판단 못 함 — 유지로 둠 |",
          "| 7 | 사이트 정책(`all` · `review_ban`)은 가정 — 실제 정책 확정 시 항목·키워드 변경 가능 |", "",
          "**보완 방향** — 키워드를 현 상태로 고정하고 판정표 작성 후 수정 안 함 · 골든 밖 상세페이지를 따로 두어 재측정.", "",
          "## 섹션별 적중 · 판정표", "",
          "`결정`은 `all` 기준. 항목 약칭 뒤 괄호는 적중 키워드 수. vis: `results/rule_kw/vis/sections/{섹션}.jpg`.", "",
          "**채울 칸** — `정답 항목`(해당 항목 키를 쉼표로, 없으면 `-`) · `전체/일부`(해당 내용이 섹션 전체인가) · `비고`.", "",
          "| 섹션 | 높이 | 결정(all) | 결정(review_ban) | 적중 항목 · 키워드 | 정답 항목 | 전체/일부 | 비고 |",
          "|---|---|---|---|---|---|---|---|"]
    for s in secs:
        sid = s["section"]
        h = hits[sid]
        cell = "<br>".join(f"`{k}`({len(v['keywords'])}) {', '.join(v['keywords'])}"
                           for k, v in h.items()) or ("_글자 없음_" if not any(
                               b["text"].strip() for b in s["blocks"]) else "—")
        L.append(f"| `{sid}` | {s['height']} | {decs['all'][sid]} | {decs['review_ban'][sid]} | {cell} |  |  |  |")
    L += ["", "항목 키 — " + " · ".join(f"`{k}` {n}" for k, n, _ in ITEMS), ""]
    (HERE / "summary.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- main

def run_rule_kw() -> None:
    t0 = time.perf_counter()
    secs = load_sections()
    out = RESULTS / "rule_kw"
    hits = {s["section"]: match_items(s["blocks"]) for s in secs}
    decs = {p: {s["section"]: decide(hits[s["section"]], items) for s in secs}
            for p, items in POLICIES.items()}
    sec_time = round(time.perf_counter() - t0, 3)

    for s in secs:
        sid = s["section"]
        no_text = not any(b["text"].strip() for b in s["blocks"])
        doc = {"section": sid, "variant": "rule_kw", "range": s["range"], "height": s["height"],
               "prev": s["prev"], "next": s["next"], "no_text": no_text,
               "decisions": {p: decs[p][sid] for p in POLICIES},
               "hits": [{"item": k, "name": ITEM_NAME[k], "decision": item_decision(v),
                         "keywords": v["keywords"], "blocks": v["blocks"],
                         "texts": [s["blocks"][i]["text"][:80] for i in v["blocks"]]}
                        for k, v in hits[sid].items()],
               "coverage": None}
        (out / "decisions").mkdir(parents=True, exist_ok=True)
        (out / "decisions" / f"{sid}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        vis_section(s, hits[sid], out / "vis" / "sections" / f"{sid}.jpg")

    by_page: dict[str, list[dict]] = {}
    for s in secs:
        by_page.setdefault(s["stem"], []).append(s)
    for p, items in POLICIES.items():
        for stem, ss in by_page.items():
            vis_page(stem, ss, decs[p], hits, items, out / "vis" / "pages" / p / f"{stem}.jpg")

    meta = {"variant": "rule_kw", "sections": len(secs), "sec": sec_time,
            "no_text": sum(1 for s in secs if not any(b["text"].strip() for b in s["blocks"])),
            "policies": {p: {k: sum(1 for v in decs[p].values() if v == k) for k in RANK}
                         for p in POLICIES},
            "items": {k: {d: sum(1 for h in hits.values() if k in h and item_decision(h[k]) == d)
                          for d in ("제외", "확인 필요")} for k, _, _ in ITEMS},
            "keywords": KEYWORDS, "policy_items": POLICIES,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    write_summary(secs, hits, decs, meta)

    print(f"[rule_kw] 섹션 {len(secs)} · 판정 {sec_time}s")
    for p in POLICIES:
        print(f"  정책 {p:<11} {meta['policies'][p]}")
    for k, n, _ in ITEMS:
        print(f"  {n:<12} {meta['items'][k]}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=VARIANTS)
    args = ap.parse_args()
    {"rule_kw": run_rule_kw}[args.variant]()


if __name__ == "__main__":
    main()
