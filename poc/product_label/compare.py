"""제품 라벨 판정 — variant 비교표 생성기.

results/ 아래 실행된 모든 variant를 읽어 summary.md를 만든다.
사람이 채우는 건 판정표의 **미탐·오탐** 두 칸이다.

  미탐 = 제품 라벨인데 `배경`으로 본 블록 수 — **복구 불가**
  오탐 = 배경 텍스트인데 `라벨`로 본 블록 수 — 번역 누락, 검수 복구 가능

**등급 산식을 두지 않는다.** 미탐 1건으로 탈락시킬지가 아직 미정이라
(`PoC_추가검증_계획.md` 미결 8) 임의로 정하지 않는다. 건수만 모은다.

**이미 채워진 값은 재실행해도 보존한다.**

--sample golden
    results/golden/vlm_relation/ 을 읽어 summary_golden.md 를 만든다. 섹션 단위 판정표.
    채울 칸 = 미탐 번호 · 오탐 번호(블록 번호, 쉼표 구분, 없으면 `-`) · 컷 유형 · 비고.
    채워진 행으로 라벨 정답지 results/golden/vlm_relation/truth.json 을 만든다
    (정답 라벨 = 판정 라벨 − 오탐 + 미탐). 단계 2 역할 라벨 칸 · 단계 5·6 판정 제외 기준으로 씀.
    판정 대지 results/golden/vlm_relation/board/{섹션}.jpg.
    출력은 과업 폴더에 나오고 poc/golden/move.py 3 으로 옮긴다. 재실행은 --restore 후.

사용법
    python compare.py
    python compare.py --sample golden
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE / "summary.md"

COUNT_COLS = ["미탐", "오탐", "비고"]

# summary.md에서 통째로 빼는 variant.
# 실행 기록은 results/{variant}/meta.json 과 결과 문서에 남는다.
EXCLUDED: dict[str, str] = {
    "vlm_opus": "vlm_relation과 110블록 전부 동일 판정 — 비교 가치 없음 (2026-09-09)",
}


def variants() -> list[str]:
    if not RESULTS.exists():
        return []
    return sorted(d.name for d in RESULTS.iterdir() if (d / "meta.json").exists())


def load_blocks(variant: str, image: str) -> list[dict]:
    return json.loads(
        (RESULTS / variant / "blocks" / f"{Path(image).stem}.json").read_text(encoding="utf-8")
    )["blocks"]


def read_table() -> dict[tuple[str, str], list[str]]:
    """기존 summary.md 판정표에서 채워진 행을 회수한다.

    행 형식: | 이미지 | `variant` | 블록 | 라벨 | 미탐 | 오탐 | 비고 | 시각화 |
    """
    if not OUT.exists():
        return {}
    got: dict[tuple[str, str], list[str]] = {}
    width = 2 + 2 + len(COUNT_COLS) + 1
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != width:
            continue
        img, variant = cells[0], cells[1]
        if not img.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if not (variant.startswith("`") and variant.endswith("`")):
            continue
        vals = cells[4 : 4 + len(COUNT_COLS)]
        if any(vals):
            got[(img, variant.strip("`"))] = vals
    return got


def main_default() -> None:
    names = [n for n in variants() if n not in EXCLUDED]
    if not names:
        raise SystemExit(f"{RESULTS} 아래 실행 결과 없음 — run.py 를 먼저 돌릴 것")

    metas = {n: json.loads((RESULTS / n / "meta.json").read_text(encoding="utf-8")) for n in names}
    images = [p["image"] for p in metas[names[0]]["per_image"]]
    filled = read_table()

    blocks = {(n, img): load_blocks(n, img) for n in names for img in images}

    L: list[str] = []
    L.append("# 제품 라벨 판정 — 실행 결과")
    L.append("")
    L.append("> 이 파일은 `compare.py`가 생성함. **미탐·오탐 두 칸이 사람이 채우는 전부임.**")
    L.append("> 입력은 `block_role`의 `llm_assist` 블록. 계획은 `PoC_추가검증_계획.md`.")
    L.append("> **등급 산식 없음** — 미탐 1건 탈락 여부가 미결(계획 문서 미결 8)이라 두지 않음.")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| variant | 조건 | 블록 | 라벨 판정 | 비율 | 소요 | 비용 |")
    L.append("|---|---|---|---|---|---|---|")
    for n in names:
        m = metas[n]
        cfg = " ".join(f"`{k}={v}`" for k, v in m["cfg"].items())
        rate = m["total_labels"] / max(1, m["total_blocks"])
        cost = f"${m['cost_usd']}" if m.get("cost_usd") else "0"
        L.append(
            f"| `{n}` | {cfg} | {m['total_blocks']} | {m['total_labels']} | "
            f"{rate:.0%} | {m['total_sec']}s | {cost} |"
        )
    L.append("")

    # 2. 이미지별 라벨 판정 수
    L.append("## 2. 이미지별 라벨 판정 수 (기계 집계 — 정오 아님)")
    L.append("")
    L.append("| 이미지 | 블록 | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|---|" + "---|" * len(names))
    for img in images:
        nb = len(blocks[(names[0], img)])
        cells = []
        for n in names:
            cells.append(str(sum(1 for b in blocks[(n, img)] if b["is_product_label"])))
        L.append(f"| {img} | {nb} | " + " | ".join(cells) + " |")
    L.append("")

    # 3. 합의도 — 어느 블록을 먼저 볼지 고르는 용도
    if len(names) >= 2:
        L.append("## 3. 합의도")
        L.append("")
        L.append("블록마다 몇 개 variant가 `라벨`로 봤는지 센다. **갈리는 블록이 판정 대상임.**")
        L.append("")
        L.append("| 이미지 | 전원 라벨 | 전원 배경 | **갈림** |")
        L.append("|---|---|---|---|")
        tot = [0, 0, 0]
        for img in images:
            n_all = n_none = n_split = 0
            for i in range(len(blocks[(names[0], img)])):
                votes = sum(1 for n in names if blocks[(n, img)][i]["is_product_label"])
                if votes == len(names):
                    n_all += 1
                elif votes == 0:
                    n_none += 1
                else:
                    n_split += 1
            tot = [tot[0] + n_all, tot[1] + n_none, tot[2] + n_split]
            L.append(f"| {img} | {n_all} | {n_none} | **{n_split}** |")
        L.append(f"| **합계** | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** |")
        L.append("")

    # 4. 판정표
    L.append("## 4. 판정표")
    L.append("")
    L.append("**채울 칸은 `미탐`·`오탐` 2개.** 블록·라벨 수는 코드가 채움.")
    L.append("")
    L.append("- **미탐** = 제품 라벨인데 `배경`으로 본 블록 수. **복구 불가**")
    L.append("- **오탐** = 배경 텍스트인데 `라벨`로 본 블록 수. 번역 누락이나 검수 복구 가능")
    L.append("")
    L.append("`vis/`에서 **빨강 = 라벨 판정 · 파랑 = 배경 판정**. 라벨 옆 숫자는 판정에 쓴 값임.")
    L.append("")
    L.append("| 이미지 | variant | 블록 | 라벨 | " + " | ".join(COUNT_COLS) + " | 시각화 |")
    L.append("|---|---|---|---|" + "---|" * len(COUNT_COLS) + "---|")
    for img in images:
        stem = Path(img).stem
        for n in names:
            nb = len(blocks[(n, img)])
            nl = sum(1 for b in blocks[(n, img)] if b["is_product_label"])
            vals = filled.get((img, n), [""] * len(COUNT_COLS))
            L.append(
                f"| {img} | `{n}` | {nb} | {nl} | " + " | ".join(vals)
                + f" | `results/{n}/vis/{stem}.jpg` |"
            )
    L.append("")

    # 5. 집계 — 채워진 칸에서만
    L.append("## 5. 집계")
    L.append("")
    if not filled:
        L.append("_판정 전_ — 채워진 칸 없음.")
    else:
        L.append(f"채워진 행 {len(filled)} / {len(images) * len(names)}. 빈 행은 계산에서 뺌.")
        L.append("")
        L.append("| variant | 판정 이미지 | 미탐 | 오탐 | 라벨 판정 | 오탐률 |")
        L.append("|---|---|---|---|---|---|")
        for n in names:
            rows = [(img, v) for (img, var), v in filled.items() if var == n]
            miss = fp = lab = 0
            ok = 0
            for img, v in rows:
                try:
                    miss += int(v[0])
                    fp += int(v[1])
                except ValueError:
                    continue
                lab += sum(1 for b in blocks[(n, img)] if b["is_product_label"])
                ok += 1
            if not ok:
                continue
            L.append(
                f"| `{n}` | {ok} | **{miss}** | {fp} | {lab} | "
                f"{fp / max(1, lab):.0%} |"
            )
        L.append("")
        L.append("**미탐이 0인 variant만 채택 후보임.** 오탐률은 검수 부담의 크기임.")
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    skipped = [n for n in EXCLUDED if (RESULTS / n / "meta.json").exists()]
    tail = f" · 제외 {', '.join(skipped)}" if skipped else ""
    print(f"작성: {OUT}  (variant {len(names)}종, 이미지 {len(images)}장{tail})")


# ---------------------------------------------------------------- 골든 샘플 — 섹션 단위

GOLDEN = RESULTS / "golden" / "vlm_relation"
GOLDEN_OUT = HERE / "summary_golden.md"
OCR_SUMMARY = HERE.parents[1] / "poc" / "golden" / "1_B_ocr" / "summary.md"  # 단계 1 판정 — 글자 없는 섹션
GOLDEN_COLS = ["미탐 번호", "오탐 번호", "컷 유형", "비고"]
BOARD_PANEL_W = 600
SID = re.compile(r"^A\d+_\d{3}_\d{3}$")
PIPE = re.compile(r"(?<!\\)\|")


def g_cells(line: str) -> list[str]:
    return [c.strip() for c in PIPE.split(line.strip().strip("|"))]


def g_esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " / ").strip()


def parse_ids(cell: str, n_blocks: int) -> list[int] | None:
    """`-` = 없음, `3, 7` = 블록 번호. 빈 칸·형식 오류는 None(미판정)."""
    cell = cell.strip()
    if cell == "-":
        return []
    if not cell:
        return None
    try:
        ids = sorted({int(x) for x in re.split(r"[,\s]+", cell) if x})
    except ValueError:
        return None
    return ids if all(1 <= i <= n_blocks for i in ids) else None


def read_golden_table() -> dict[str, list[str]]:
    got: dict[str, list[str]] = {}
    if not GOLDEN_OUT.exists():
        return got
    for line in GOLDEN_OUT.read_text(encoding="utf-8").splitlines():
        if line.startswith("|"):
            c = g_cells(line)
            if len(c) == 5 + len(GOLDEN_COLS) and SID.match(c[0]):
                vals = c[4 : 4 + len(GOLDEN_COLS)]
                if any(vals):
                    got[c[0]] = vals
    return got


def no_text_sections() -> set[str]:
    out = set()
    if OCR_SUMMARY.exists():
        for line in OCR_SUMMARY.read_text(encoding="utf-8").splitlines():
            if line.startswith("|"):
                c = g_cells(line)
                if len(c) == 9 and SID.match(c[0]) and c[3] == "-" and c[4] == "-":
                    out.add(c[0])
    return out


def make_board(sid: str, blocks: list[dict], out: Path) -> None:
    """판정 대지 — 왼쪽 라벨(빨강)·배경(파랑) 판정 vis, 오른쪽 블록 번호·판정·텍스트."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size):
        for name in ("malgun.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    vis = Image.open(GOLDEN / "vis" / f"{sid}.jpg").convert("RGB")
    f = font(15)
    probe = ImageDraw.Draw(vis)
    lines = [(f"{sid}  vlm_relation  블록 {len(blocks)} · 라벨 {sum(b['is_product_label'] for b in blocks)}", (0, 0, 0)),
             ("빨강 = 라벨 판정 · 파랑 = 배경 판정", (110, 110, 110)), ("", (0, 0, 0))]
    for i, b in enumerate(blocks, 1):
        col = (220, 30, 30) if b["is_product_label"] else (30, 90, 220)
        text = f"{i} [{'라벨' if b['is_product_label'] else '배경'}] " + b["text"].replace("\n", " / ")
        cur = ""
        for ch in text:
            if cur and probe.textlength(cur + ch, font=f) > BOARD_PANEL_W - 24:
                lines.append((cur, col))
                cur = "    " + ch
            else:
                cur += ch
        lines.append((cur, col))
    h = max(vis.height, 12 + 21 * len(lines) + 12)
    board = Image.new("RGB", (vis.width + BOARD_PANEL_W, h), (255, 255, 255))
    board.paste(vis, (0, 0))
    d = ImageDraw.Draw(board)
    d.line([(vis.width, 0), (vis.width, h)], fill=(180, 180, 180), width=2)
    y = 12
    for seg, col in lines:
        d.text((vis.width + 12, y), seg, fill=col, font=f)
        y += 21
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out, quality=90)


def main_golden() -> None:
    if not (GOLDEN / "meta.json").exists():
        raise SystemExit(f"{GOLDEN / 'meta.json'} 없음 — run_llm.py --variant vlm_relation --sample golden 먼저")
    meta = json.loads((GOLDEN / "meta.json").read_text(encoding="utf-8"))
    per = {p["section"]: p for p in meta["per_section"]}
    sids = [p["section"] for p in meta["per_section"]]
    blocks = {s: json.loads((GOLDEN / "blocks" / f"{s}.json").read_text(encoding="utf-8"))["blocks"] for s in sids}
    filled = read_golden_table()
    empty = no_text_sections()
    rel = "results/golden/vlm_relation"

    for s in sids:
        make_board(s, blocks[s], GOLDEN / "board" / f"{s}.jpg")

    L: list[str] = []
    L.append("# 제품 라벨 판정 — 골든 샘플 섹션 판정")
    L.append("")
    L.append("> `compare.py --sample golden`이 생성함. 재실행해도 **채운 칸은 보존함.**")
    L.append("> 계획 `PoC_골든샘플_재실행_계획.md` 단계 3. 입력은 단계 2 `llm_assist` 블록 + 섹션 이미지(긴 변 1024px). 12장 결과(`summary.md`)는 건드리지 않음.")
    L.append("")

    # 1. 실행 조건
    L.append("## 1. 실행 조건")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|---|---|")
    L.append(f"| 조건 | " + " ".join(f"`{k}={v}`" for k, v in meta["cfg"].items()) + " |")
    L.append(f"| 섹션 · 호출 | {meta['sections']} · {meta['calls']} (캐시 {meta['cache_hits']}) |")
    L.append(f"| 블록 · 라벨 판정 | {meta['total_blocks']} · **{meta['total_labels']}** ({meta['total_labels'] / max(1, meta['total_blocks']):.0%}) |")
    L.append(f"| 토큰 · 비용 | in {meta['tokens']['in']:,} · out {meta['tokens']['out']:,} · ${meta['cost_usd']:.4f} |")
    L.append(f"| 소요 · 응답 적용 실패 | {meta['total_sec']}s · {len(meta['errors'])} |")
    L.append("")
    for e in meta["errors"]:
        L.append(f"- 적용 실패 `{e['section']}` — {g_esc(e['error'])}")
    if meta["errors"]:
        L.append("")

    # 2. 판정표
    L.append("## 2. 판정표 (섹션 단위 — 블록 번호로 채움)")
    L.append("")
    L.append(f"대지 `{rel}/board/{{섹션}}.jpg` — 왼쪽 빨강 = 라벨 판정 · 파랑 = 배경 판정, 오른쪽 블록 번호별 판정·텍스트.")
    L.append("")
    L.append("- **미탐 번호** = 제품 라벨인데 `배경`으로 본 블록 번호 · **복구 불가**")
    L.append("- **오탐 번호** = 배경 텍스트인데 `라벨`로 본 블록 번호 · 검수 복구 가능")
    L.append("- 쉼표로 구분(`3, 7`). **없으면 `-`** — 빈 칸은 미판정으로 봄")
    L.append("- **컷 유형** = 겹친 패키지 · 라벨 없음 · 단일 제품 등(확인 항목 — 조건부 종결 사유). 해당 없으면 `-`")
    L.append("- 비텍스트 오검출 블록(얼굴·아이콘 등)은 배경으로 보는 게 맞음 — 라벨로 봤으면 오탐")
    L.append("- 판정 주체: Claude 1차 전수 확인(비고에 \"Claude 육안 판정\") → 예람님 검토. **이 판정이 라벨 정답지가 됨**")
    if empty:
        L.append("- 글자 없는 섹션(단계 1 `-`): " + ", ".join(f"`{s}`" for s in sorted(empty)) + " — 비텍스트 블록만 있음")
    L.append("")
    L.append("| 섹션 | 블록 | 라벨 판정 | 보낸 크기 | " + " | ".join(GOLDEN_COLS) + " | 대지 |")
    L.append("|---|---|---|---|" + "---|" * len(GOLDEN_COLS) + "---|")
    for s in sids:
        p = per[s]
        vals = filled.get(s, [" "] * len(GOLDEN_COLS))
        L.append(f"| {s} | {p['blocks']} | {p['labels']} | {p['sent_size'][0]}×{p['sent_size'][1]} | "
                 + " | ".join(vals) + f" | [보기]({rel}/board/{s}.jpg) |")
    L.append("")

    # 3. 집계 · 정답지
    L.append("## 3. 집계")
    L.append("")
    truth: dict[str, list[int]] = {}
    miss_t = fp_t = lab_t = 0
    miss_rows, bad = [], []
    width_miss: dict[str, list[int]] = {}
    for s in sids:
        v = filled.get(s)
        if not v:
            continue
        nb = len(blocks[s])
        m, f = parse_ids(v[0], nb), parse_ids(v[1], nb)
        if m is None or f is None:
            bad.append(s)
            continue
        pred = {i for i, b in enumerate(blocks[s], 1) if b["is_product_label"]}
        if set(m) & pred or not set(f) <= pred:
            bad.append(s)  # 미탐은 배경 판정 블록, 오탐은 라벨 판정 블록이어야 함
            continue
        truth[s] = sorted((pred - set(f)) | set(m))
        miss_t += len(m)
        fp_t += len(f)
        lab_t += len(pred)
        if m:
            miss_rows.append((s, m))
        w = min(per[s]["sent_size"])
        bucket = "300px 미만" if w < 300 else ("300~599px" if w < 600 else "600px 이상")
        width_miss.setdefault(bucket, [0, 0])
        width_miss[bucket][0] += 1
        width_miss[bucket][1] += len(m)
    done = len(truth)
    if not done:
        L.append("_판정 전_ — 채워진 행 없음.")
    else:
        L.append(f"판정 섹션 {done}/{len(sids)}" + (f" · **형식 오류로 뺀 섹션 {len(bad)}: " + ", ".join(f"`{s}`" for s in bad) + "**" if bad else ""))
        L.append("")
        L.append("| 미탐 | 오탐 | 라벨 판정(판정 섹션) | 오탐률 | 정답 라벨 | 게이트 (미탐 0) |")
        L.append("|---|---|---|---|---|---|")
        gate = ("통과" if miss_t == 0 else "미달") if done == len(sids) else "판정 미완"
        L.append(f"| **{miss_t}** | {fp_t} | {lab_t} | {fp_t / max(1, lab_t):.0%} | {sum(len(t) for t in truth.values())} | **{gate}** |")
        L.append("")
        L.append("**보낸 이미지 짧은 변별 미탐** — 긴 섹션일수록 폭이 좁아짐(계획 위험 항목)")
        L.append("")
        L.append("| 짧은 변 | 섹션 | 미탐 |")
        L.append("|---|---|---|")
        for k in ("300px 미만", "300~599px", "600px 이상"):
            if k in width_miss:
                L.append(f"| {k} | {width_miss[k][0]} | {width_miss[k][1]} |")
        L.append("")
        if miss_rows:
            L.append("**미탐 블록**")
            L.append("")
            L.append("| 섹션 | 블록 | 텍스트 |")
            L.append("|---|---|---|")
            for s, m in miss_rows:
                for i in m:
                    t = g_esc(blocks[s][i - 1]["text"])
                    L.append(f"| `{s}` | {i} | {t[:100] + ('…' if len(t) > 100 else '')} |")
            L.append("")
        types: dict[str, int] = {}
        for s in truth:
            for t in re.split(r"\s*·\s*|,\s*", filled[s][2]):
                if t and t != "-":
                    types[t] = types.get(t, 0) + 1
        if types:
            L.append("**컷 유형** — " + " · ".join(f"{k} {v}" for k, v in sorted(types.items(), key=lambda x: -x[1])))
            L.append("")
    L.append("")

    GOLDEN_OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    (GOLDEN / "truth.json").write_text(json.dumps(
        {"note": "정답 라벨 블록 번호(1부터) — 판정 라벨 − 오탐 + 미탐. 판정 완료 섹션만.",
         "sections_done": done, "sections_total": len(sids), "labels": truth},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"작성: {GOLDEN_OUT}  (섹션 {len(sids)} · 판정 {done} · 대지 {rel}/board/ · 정답지 truth.json)")


def main() -> None:
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", choices=("default", "golden"), default="default")
    args = ap.parse_args()
    if args.sample == "golden":
        main_golden()
    else:
        main_default()


if __name__ == "__main__":
    main()
