"""브랜드 로고 제외 — variant 실행기.

등록 로고 이미지로 상세페이지에서 로고 위치를 찾는다. 찾은 자리는 하류에서
번역·인페인팅 대상에서 빠진다. 전부 로컬, 비용 0.

⚠️ **등록 로고 파일이 없다.** 페이지에서 가장 깨끗한 워드마크를 잘라 임시 템플릿으로
쓴다. 실제 등록 로고는 배경 없는 원본 파일이라 조건이 다르다 — 결과 해석에 유의.

템플릿을 잘라낸 **원래 자리는 무조건 맞는다.** 그 자리는 평가에서 뺀다(`is_source`).

variant
    template_gray     다중 스케일 밝기 정규화 상관(NCC). 색이 같으면 가장 정확하다
    template_edge     윤곽선(Canny)끼리 매칭. 흰 로고/검은 로고처럼 색이 뒤집혀도 잡는다
    feature_orb       ORB 특징점 + 호모그래피. 기울어지거나 크기가 크게 다를 때 강하다
    template_gray_lo  template_gray와 같고 임계만 0.80 → 0.60
    template_edge_lo  template_edge와 같고 임계만 0.45 → 0.30

판정
    **오탐이 놓침보다 나쁘다.** 놓침은 "확인 필요"로 드러나지만, 오탐은 멀쩡한
    글자가 조용히 번역·인페인팅에서 빠진다. 사람이 vis/를 보고 판정한다.

범위
    제품 패키지에 인쇄된 로고는 **제품 라벨 판정** 소관이다. 찾아도 오탐이 아니고
    못 찾아도 놓침이 아니다.

출력
    results/{variant}/matches/{stem}.json   로고별 매칭 좌표·점수·배율
    results/{variant}/vis/{stem}.jpg        매칭 박스. 초록=임계 통과, 주황=미달, 회색=원래 자리
    results/{variant}/meta.json

사용법
    python run.py --variant all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data" / "golden_sample"
RESULTS = HERE / "results"

# 임시 등록 로고 — (이름, 원본 파일, 잘라낼 상자)
LOGOS = [
    ("b.clinicx", "images_A000000213548/A000000213548_002.jpg", (385, 170, 615, 230)),
    ("goodal", "images_A000000219554/A000000219554_002.jpg", (530, 33868, 760, 33965)),
    # goodal의 두 번째 로고 형태(세리프체). 1차 실행에서 219554_001 하단 페이지 로고를
    # 타원 템플릿으로 못 잡았다. **튜브 인쇄분에서 잘라** 그 페이지 로고를 처음 보는
    # 대상으로 남긴다 — 페이지 로고에서 자르면 원래 자리라 평가에서 빠진다.
    ("goodal_serif", "images_A000000219554/A000000219554_002.jpg", (615, 5280, 727, 5325)),
]

SCALES = tuple(round(0.4 + 0.1 * i, 2) for i in range(17))   # 0.4 ~ 2.0

VARIANTS: dict[str, dict] = {
    "template_gray": {"method": "gray", "thresh": 0.80},
    "template_edge": {"method": "edge", "thresh": 0.45},
    "feature_orb": {"method": "orb", "min_inliers": 12},
    # 임계를 낮춘 쌍 — 1차에서 0.60~0.63 미달 후보가 전부 실제 로고였다.
    # 낮추면 오탐이 실제로 늘어나는지 본다.
    "template_gray_lo": {"method": "gray", "thresh": 0.60},
    "template_edge_lo": {"method": "edge", "thresh": 0.30},
}

NMS_IOU = 0.3      # 겹치는 후보는 점수 높은 것 하나만
REPORT_FLOOR = 0.5 # 이 비율 × 임계 이상인 후보는 '미달'로라도 남긴다 — 경계선을 보려고


def load_gray(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def edges(g: np.ndarray) -> np.ndarray:
    return cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 60, 160)


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0.0


def nms(cands: list[dict]) -> list[dict]:
    keep = []
    for c in sorted(cands, key=lambda x: -x["score"]):
        if all(iou(c["bbox"], k["bbox"]) < NMS_IOU for k in keep):
            keep.append(c)
    return keep


def match_template(page: np.ndarray, tmpl: np.ndarray, cfg: dict) -> list[dict]:
    """다중 스케일 템플릿 매칭. 페이지 전체를 한 번에 본다."""
    use_edge = cfg["method"] == "edge"
    src = edges(page) if use_edge else page
    floor = cfg["thresh"] * REPORT_FLOOR
    out = []
    for s in SCALES:
        t = cv2.resize(tmpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        if t.shape[0] < 12 or t.shape[1] < 24 or t.shape[0] >= src.shape[0] or t.shape[1] >= src.shape[1]:
            continue
        tt = edges(t) if use_edge else t
        if use_edge and tt.sum() == 0:
            continue
        res = cv2.matchTemplate(src, tt, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= floor)
        if len(ys) > 4000:           # 너무 많으면 상위만
            idx = np.argsort(res[ys, xs])[-4000:]
            ys, xs = ys[idx], xs[idx]
        h, w = tt.shape
        for y, x in zip(ys, xs):
            out.append({"bbox": [int(x), int(y), int(x + w), int(y + h)],
                        "score": round(float(res[y, x]), 3), "scale": s})
    return nms(out)


_orb = cv2.ORB_create(nfeatures=4000)
_bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)


def match_orb(page: np.ndarray, tmpl: np.ndarray, cfg: dict) -> list[dict]:
    """특징점 매칭. 긴 페이지는 2,000px 띠로 나눠 본다 — 특징점 수 상한 때문."""
    kt, dt = _orb.detectAndCompute(tmpl, None)
    if dt is None or len(kt) < 8:
        return []
    out = []
    band, step = 2000, 1600
    for top in range(0, max(1, page.shape[0] - 400), step):
        strip = page[top:top + band]
        kp, dp = _orb.detectAndCompute(strip, None)
        if dp is None or len(kp) < 8:
            continue
        pairs = _bf.knnMatch(dt, dp, k=2)
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < 8:
            continue
        a = np.float32([kt[m.queryIdx].pt for m in good])
        b = np.float32([kp[m.trainIdx].pt for m in good])
        H, mask = cv2.findHomography(a, b, cv2.RANSAC, 5.0)
        if H is None:
            continue
        inl = int(mask.sum())
        h, w = tmpl.shape
        corners = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2), H)
        xs, ys = corners[:, 0, 0], corners[:, 0, 1] + top
        box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        bw, bh = box[2] - box[0], box[3] - box[1]
        # 찌그러진 호모그래피는 버린다 — 가로세로비가 템플릿과 크게 다르면 엉터리다
        if bw <= 8 or bh <= 4 or not (0.4 < (bw / bh) / (w / h) < 2.5):
            continue
        if inl >= cfg["min_inliers"] * REPORT_FLOOR:
            out.append({"bbox": box, "score": inl, "scale": round(bw / w, 2)})
    return nms(out)


def _font(size: int):
    for name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def visualize(path: Path, found: list[dict], out: Path) -> None:
    """초장축이라 폭 600으로 줄여 그린다."""
    img = Image.open(path).convert("RGB")
    s = 600 / img.width
    img = img.resize((600, max(1, int(img.height * s))), Image.BILINEAR)
    d = ImageDraw.Draw(img)
    font = _font(14)
    for m in found:
        x1, y1, x2, y2 = (int(v * s) for v in m["bbox"])
        color = (150, 150, 150) if m["is_source"] else ((20, 170, 60) if m["pass"] else (240, 140, 0))
        d.rectangle([x1, y1, x2, y2], outline=color, width=3)
        d.rectangle([x1, max(0, y1 - 18), x1 + 150, max(0, y1 - 18) + 18], fill=color)
        d.text((x1 + 3, max(0, y1 - 17)), f"{m['logo']} {m['score']}", fill=(255, 255, 255), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=88)


def run_variant(name: str, paths: list[Path], templates: dict[str, np.ndarray]) -> None:
    cfg = VARIANTS[name]
    out_dir = RESULTS / name
    (out_dir / "matches").mkdir(parents=True, exist_ok=True)
    print(f"[{name}] {cfg}")
    t0 = time.perf_counter()
    per = []

    for path in paths:
        page = load_gray(path)
        found = []
        for logo, src_file, box in LOGOS:
            tmpl = templates[logo]
            cands = (match_orb(page, tmpl, cfg) if cfg["method"] == "orb"
                     else match_template(page, tmpl, cfg))
            thr = cfg.get("thresh", cfg.get("min_inliers"))
            for c in cands:
                is_src = (path.relative_to(SRC).as_posix() == src_file and iou(c["bbox"], box) > 0.5)
                found.append({**c, "logo": logo, "pass": c["score"] >= thr, "is_source": is_src})

        (out_dir / "matches" / f"{path.stem}.json").write_text(
            json.dumps({"image": path.name, "variant": name, "matches": found},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        visualize(path, found, out_dir / "vis" / f"{path.stem}.jpg")
        n_pass = sum(1 for m in found if m["pass"] and not m["is_source"])
        n_low = sum(1 for m in found if not m["pass"] and not m["is_source"])
        per.append({"image": path.name, "brand_folder": path.parent.name,
                    "pass": n_pass, "below": n_low,
                    "by_logo": {lg: sum(1 for m in found if m["logo"] == lg and m["pass"] and not m["is_source"])
                                for lg, _, _ in LOGOS}})
        print(f"  {path.parent.name[-6:]}/{path.name:<24} 통과 {n_pass:>2}  미달 {n_low:>3}  "
              f"{per[-1]['by_logo']}")

    meta = {"variant": name, "cfg": cfg, "logos": [l[0] for l in LOGOS], "scales": SCALES,
            "images": len(paths), "total_pass": sum(p["pass"] for p in per),
            "total_sec": round(time.perf_counter() - t0, 2), "per_image": per,
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] 완료 — 통과 {meta['total_pass']}, {meta['total_sec']}s\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help=f"{', '.join(VARIANTS)}, all")
    ap.add_argument("--images", nargs="*", default=None)
    args = ap.parse_args()

    templates = {}
    tdir = RESULTS / "_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    for logo, src_file, box in LOGOS:
        g = load_gray(SRC / src_file)
        x1, y1, x2, y2 = box
        templates[logo] = g[y1:y2, x1:x2].copy()
        cv2.imencode(".png", templates[logo])[1].tofile(str(tdir / f"{logo}.png"))

    paths = sorted(SRC.rglob("*.jpg"), key=lambda p: (p.parent.name, p.name))
    if args.images:
        paths = [p for p in paths if p.name in args.images]
    for n in (list(VARIANTS) if args.variant == "all" else [args.variant]):
        if n not in VARIANTS:
            raise SystemExit(f"모르는 variant: {n}. 가능: {', '.join(VARIANTS)}, all")
        run_variant(n, paths, templates)


if __name__ == "__main__":
    main()
