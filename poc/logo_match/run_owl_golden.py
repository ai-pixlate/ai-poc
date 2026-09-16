"""브랜드 로고 제외 — 골든 샘플 **OCR 전 제외** 검증 (후보 A: OWLv2 원샷 검출).

로고 파일을 **예시 이미지(query image)** 로 넣으면 섹션에서 같은 물체를 찾는다
(`Owlv2ForObjectDetection.image_guided_detection`). 템플릿 매칭(후보 B)과 달리
배율을 훑지 않고, 색·배경·글꼴 변형에 강할 것으로 기대한다. 심볼형 로고도 같은 방식.

평가·하류는 후보 B(`run_tmpl_golden.py`)와 **완전히 같은 기준**을 쓴다 — 같은 템플릿(크롭),
같은 정답 4개, 같은 분류(원래 자리 · 로고 · 라벨 소관 · 오탐), 같은 글자 확인.

실행 환경
    **`.venv-e1`** (torch CUDA · transformers). 하류 OCR은 paddle이 있는 `.venv`에서
    `run_tmpl_golden.py --from-passed` 로 이어 돌린다.

모델
    google/owlv2-base-patch16-ensemble (가중치 약 620MB). 기본은 **로컬 캐시만** 쓴다.
    처음 받을 때만 `--allow-download`.

입력 크기
    OWLv2는 이미지를 정사각형으로 패딩해 960×960으로 줄인다. 섹션은 최대 1000×4,491이라
    통째로 넣으면 로고가 수 px로 줄어듦 → **정사각 타일(한 변 = 섹션 폭)** · 겹침 TILE_OVERLAP로 나눠 넣는다.

점수
    ⚠️ processor 후처리 점수는 조각 안 최고점을 1.0으로 맞춘 표시용 값이고, sigmoid(로짓)도 이미지 질의에선
    수백 상자가 0.999로 포화됨 → **보정 전 코사인 유사도**를 점수로 씀.
    ⚠️ 기본 질의 선택은 정사각 패딩 탓에 회색 패딩을 질의로 고름 → 로고 자리 상자를 직접 고름(`query_embed`).

임계
    유사도 점수의 절대 눈금을 모르므로 **낮은 바닥(FLOOR)으로 후보를 모두 남기고
    임계를 여러 값으로 훑어** 찾음·놓침·오탐을 함께 본다(`sweep`). 하류는 SWEEP 중 대표 임계 하나로.

variant
    owl_bg     크롭 템플릿 그대로
    owl_white  배경 제거 — 획 밖 화소를 흰색으로 채운 템플릿(투명 PNG 로고를 흰 바탕에 얹은 것에 해당)

출력
    results/golden/owl_{variant}/meta.json     후보·임계별 평가
    results/golden/owl_{variant}/passed.json   대표 임계 통과 후보 — 하류 입력
    results/golden/owl_{variant}/sheet.jpg     `run_tmpl_golden.py --from-passed` 가 그림

사용법 (.venv-e1)
    python run_owl_golden.py --allow-download     # 최초 1회
    python run_owl_golden.py
그다음 (.venv)
    python run_tmpl_golden.py --from-passed owl_bg
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

import run as R
import run_text as T
import run_tmpl_golden as G

Image.MAX_IMAGE_PIXELS = None

MODEL_ID = "google/owlv2-base-patch16-ensemble"
TILE_OVERLAP = 300          # 로고 최대 높이(135px)의 2배 이상
FLOOR = 0.4                 # 코사인 유사도 바닥
TOPK = 50                   # 조각마다 유사도 상위 몇 개만 남김(상자 3,600개 중)
NMS_IOU = 0.3
SWEEP = (0.6, 0.65, 0.7, 0.75, 0.8)
REP_THRESH = 0.75           # 하류·대지에 쓰는 대표 임계
VARIANTS = ("owl_bg", "owl_white")


def query_image(tp: dict, variant: str) -> Image.Image:
    g = tp["img"]
    if variant == "owl_white":
        g = np.where(tp["mask"] > 0, g, 255).astype(np.uint8)
    return Image.fromarray(g).convert("RGB")


def tiles(h: int, w: int) -> list[tuple[int, int]]:
    """세로 타일 (top, bottom). 한 변 = 섹션 폭."""
    side = w
    if h <= side:
        return [(0, h)]
    step = side - TILE_OVERLAP
    tops = list(range(0, h - side, step)) + [h - side]
    return [(t, t + side) for t in sorted(set(tops))]


def embed(model, processor, torch, img: Image.Image):
    """이미지 → (특징 맵 평탄화, 상자 cx·cy·w·h 0~1). 프로세서가 오른쪽·아래를 회색으로 채워 정사각형을 만듦."""
    px = processor(images=img, return_tensors="pt")["pixel_values"].to("cuda")
    with torch.no_grad():
        fmap = model.image_embedder(pixel_values=px)[0]
        b, h, w, d = fmap.shape
        feats = fmap.reshape(b, h * w, d)
        boxes = model.box_predictor(feats, fmap)
    return feats, boxes


def query_embed(model, processor, torch, query: Image.Image):
    """질의 임베딩 — **로고가 실제로 있는 자리**와 가장 겹치는 상자를 고른다.

    ⚠️ 기본 `image_guided_detection`은 '질의 이미지 전체[0,0,1,1]와 가장 겹치는 상자'를 고른다.
       로고 크롭은 가로로 길어(예 230×60) 정사각형 패딩이 대부분이라 **회색 패딩이 질의로 뽑혀**
       빈 곳마다 유사도 0.999가 나왔음. 패딩 전 로고 자리 = [0, 0, w/side, h/side].
    """
    from transformers.models.owlv2.modeling_owlv2 import box_iou, center_to_corners_format
    feats, boxes = embed(model, processor, torch, query)
    qw, qh = query.size
    side = max(qw, qh)
    region = torch.tensor([[0.0, 0.0, qw / side, qh / side]], device="cuda")
    with torch.no_grad():
        _, class_embeds = model.class_predictor(feats)
        ious = box_iou(region, center_to_corners_format(boxes[0]))[0][0]
    best = int(torch.argmax(ious))
    return class_embeds[0, best], float(ious[best])


def detect(model, processor, torch, sec_img: Image.Image, qemb, cache: dict | None = None) -> list[dict]:
    """섹션을 정사각 조각으로 나눠 질의와의 유사도(sigmoid)를 상자마다 낸다. 조각 특징은 cache로 재사용."""
    w, h = sec_img.size
    out = []
    for top, bot in tiles(h, w):
        key = (top, bot)
        if cache is not None and key in cache:
            feats, boxes = cache[key]
        else:
            feats, boxes = embed(model, processor, torch, sec_img.crop((0, top, w, bot)))
            if cache is not None:
                cache[key] = (feats, boxes)
        side = max(w, bot - top)
        with torch.no_grad():
            # 점수 = 보정 전 코사인 유사도. sigmoid(로짓)은 상자별 shift·scale 보정 탓에 수백 개가 0.999로 포화됨
            _, ce = model.class_predictor(feats)
            ce = ce[0] / (ce[0].norm(dim=-1, keepdim=True) + 1e-6)
            raw = ce @ (qemb / (qemb.norm() + 1e-6))
        order = torch.argsort(raw, descending=True)[:TOPK]
        for i in order.tolist():
            if float(raw[i]) < FLOOR:
                break
            cx, cy, bw, bh = (float(v) * side for v in boxes[0, i].tolist())
            x1, y1 = max(0, int(cx - bw / 2)), max(0, int(cy - bh / 2))
            x2, y2 = min(w, int(cx + bw / 2)), min(bot - top, int(cy + bh / 2))
            if x2 - x1 < 8 or y2 - y1 < 6:
                continue
            out.append({"bbox": [x1, y1 + top, x2, y2 + top], "score": round(float(raw[i]), 4), "scale": None})
    return R.nms(out)


def evaluate(dets: list[dict], thresh: float) -> dict:
    passed = [d for d in dets if d["score"] >= thresh]
    found = {}
    for k in sorted(G.TARGET):
        hit = [d for d in passed if d["kind"] == f"로고{k + 1}"]
        best_any = max((d for d in dets if d["kind"] == f"로고{k + 1}"), key=lambda d: d["score"], default=None)
        found[k] = {"logo": T.PAGE_LOGOS[k], "status": "찾음" if hit else "놓침",
                    "best": max(hit, key=lambda d: d["score"]) if hit else best_any}
    false = [d for d in passed if d["kind"] == "오탐"]
    return {"thresh": thresh,
            "counts": {"found": sum(v["status"] == "찾음" for v in found.values()),
                       "missed": sum(v["status"] == "놓침" for v in found.values()), "false": len(false)},
            "targets": [found[k] for k in sorted(found)], "false_hits": false,
            "false_by_height": {"<20px": sum(1 for d in false if d["bbox"][3] - d["bbox"][1] < 20),
                                "20~40px": sum(1 for d in false if 20 <= d["bbox"][3] - d["bbox"][1] < 40),
                                ">=40px": sum(1 for d in false if d["bbox"][3] - d["bbox"][1] >= 40)},
            "false_by_logo": {k: sum(1 for d in false if d["logo"] == k) for k in sorted({d["logo"] for d in false})},
            "pass_by_kind": {k: sum(1 for d in passed if d["kind"] == k) for k in sorted({d["kind"] for d in passed})},
            "_passed": passed}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all")
    ap.add_argument("--allow-download", action="store_true", help="모델 가중치(약 620MB)를 처음 받을 때만")
    ap.add_argument("--sections", nargs="*", default=None, help="시험용 — 일부 섹션만")
    args = ap.parse_args()

    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor

    local = not args.allow_download
    try:
        processor = Owlv2Processor.from_pretrained(MODEL_ID, local_files_only=local)
        model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID, local_files_only=local).to("cuda").eval()
    except OSError:
        raise SystemExit(f"{MODEL_ID} 가 로컬 캐시에 없음 — 허락받은 뒤 --allow-download 로 한 번 받을 것")

    pages = {p.name: p for p in R.SRC.rglob("*.jpg")}
    tps = G.templates()
    secs = G.load_sections()
    if args.sections:
        secs = [s for s in secs if s["section"] in args.sections]
    names = list(VARIANTS) if args.variant == "all" else [args.variant]

    for name in names:
        queries = {}
        for logo, tp in tps.items():
            qemb, qiou = query_embed(model, processor, torch, query_image(tp, name))
            queries[logo] = qemb
            print(f"    질의 {logo}: 로고 자리와 IoU {qiou:.2f}")
        t0 = time.perf_counter()
        dets, sec_sec = [], []
        page_name, page_img = None, None
        for sec in secs:
            if sec["image"] != page_name:
                page_name, page_img = sec["image"], Image.open(pages[sec["image"]]).convert("RGB")
            top, bot = sec["range"]
            sec_img = page_img.crop((0, top, page_img.width, bot))
            ts = time.perf_counter()
            cache = {}
            for logo, tp in tps.items():
                if G.LOGO_BRAND[logo] != sec["brand"]:
                    continue
                for c in detect(model, processor, torch, sec_img, queries[logo], cache):
                    d = {**c, "logo": logo, "section": sec["section"], "page": sec["image"],
                         "page_bbox": G.page_box(c["bbox"], sec["off"])}
                    d["kind"] = G.classify(d, sec, tp)
                    dets.append(d)
            sec_sec.append(time.perf_counter() - ts)

        sweep = [evaluate(dets, th) for th in SWEEP]
        rep = next(s for s in sweep if s["thresh"] == REP_THRESH)
        out_dir = G.OUT / name
        out_dir.mkdir(parents=True, exist_ok=True)
        passed = rep.pop("_passed")
        for s in sweep:
            s.pop("_passed", None)
        info = {"variant": name, "model": MODEL_ID, "tile_overlap": TILE_OVERLAP, "floor": FLOOR,
                "rep_thresh": REP_THRESH, "sweep": sweep, "counts": rep["counts"], "targets": rep["targets"],
                "false_hits": rep["false_hits"], "false_by_height": rep["false_by_height"],
                "false_by_logo": rep["false_by_logo"], "pass_by_kind": rep["pass_by_kind"],
                "near_false": [], "candidates": len(dets),
                "sec_per_section": {"mean": round(sum(sec_sec) / len(sec_sec), 3), "max": round(max(sec_sec), 3)},
                "scales": [None, None, 0], "total_sec": round(time.perf_counter() - t0, 1),
                "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        (out_dir / "meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        (out_dir / "passed.json").write_text(json.dumps(passed, ensure_ascii=False, indent=1), encoding="utf-8")
        # 대지는 .venv에서 그림 — .venv-e1의 PIL 9.5가 한글 글꼴 렌더링에서 죽음(access violation)

        print(f"[{name}] 후보 {len(dets)} · 섹션당 {info['sec_per_section']['mean']}s · {info['total_sec']}s")
        for s in sweep:
            c = s["counts"]
            print(f"    임계 {s['thresh']:.2f}  찾음 {c['found']} · 놓침 {c['missed']} · 오탐 {c['false']}  {s['pass_by_kind']}")
        for t in rep["targets"]:
            b = t["best"]
            print(f"    {t['logo']['image']:<22} y{t['logo']['bbox'][1]:>6} {t['status']}  "
                  + (f"{b['logo']} {b['score']}" if b else "후보 없음"))


if __name__ == "__main__":
    main()
