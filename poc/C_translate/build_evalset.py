"""C. 로컬라이징 번역 — 평가셋 구성기.

B(OCR) 출력에서 번역 대상 텍스트를 뽑아 평가셋을 만든다.
문서 2.3의 "평가 데이터는 실제 뷰티 상세페이지 텍스트 표본"을 그대로 만족한다.

사용법
    python build_evalset.py
    python build_evalset.py --min-len 2 --out evalset.json

출력
    evalset.json   이미지 단위 문서 + 세그먼트

왜 이미지 단위로 묶는가
    낱개 세그먼트만 던지면 "1등"·"세럼" 같은 조각이 문맥 없이 번역된다.
    실제 파이프라인도 한 페이지를 통째로 다루므로, 같은 이미지의 전체 텍스트를
    문맥으로 함께 넘길 수 있게 문서 단위로 묶는다.

⚠️ 원문에 B의 인식 오류가 그대로 들어 있다(예: `Biodance`→`Buodance`).
   번역 품질과 OCR 오류가 섞이지 않도록, 벤치마크 전에 원문을 눈으로 훑어
   명백한 오탈자를 고치는 편이 낫다. `manual_fix` 필드를 비워 두었다.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
B_REGIONS = ROOT / "poc" / "B_ocr" / "results" / "baseline" / "regions"

HANGUL = re.compile(r"[가-힣]")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-len", type=int, default=2, help="이 길이 미만 세그먼트는 제외")
    ap.add_argument("--out", default="evalset.json")
    ap.add_argument("--all-text", action="store_true",
                    help="한글이 없는 세그먼트도 번역 대상에 포함(기본은 한글 포함분만)")
    args = ap.parse_args()

    if not B_REGIONS.exists():
        raise SystemExit(f"B 출력 없음: {B_REGIONS}")

    files = sorted(B_REGIONS.glob("*.json"), key=lambda p: (len(p.stem), p.stem))
    documents, n_seg = [], 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        regions = payload["regions"]
        page_text = [r["text"] for r in regions]

        segments = []
        for i, r in enumerate(regions, 1):
            t = r["text"].strip()
            if len(t) < args.min_len:
                continue
            if not args.all_text and not HANGUL.search(t):
                continue
            segments.append({
                "id": f"{f.stem}-{i:02d}",
                "region": i,
                "bbox": r["bbox"],
                "source": t,
                "manual_fix": "",   # OCR 오탈자를 손으로 고칠 자리. 비어 있으면 source를 쓴다
            })
        if not segments:
            continue
        documents.append({
            "image": payload["image"],
            "page_text": page_text,   # 문맥용 — 번역 대상이 아닌 것도 포함
            "segments": segments,
        })
        n_seg += len(segments)

    out = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "poc/B_ocr/results/baseline (B 채택 설정)",
        "target_lang": None,          # _미정_ — 팀 확정 필요
        "filter": {"min_len": args.min_len, "hangul_only": not args.all_text},
        "documents": documents,
        "counts": {"documents": len(documents), "segments": n_seg},
    }
    path = HERE / args.out
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"평가셋 작성: {path}")
    print(f"  문서 {len(documents)}개 / 세그먼트 {n_seg}개")
    print(f"  문자 수 합계 {sum(len(s['source']) for d in documents for s in d['segments'])}")
    print("  ⚠️ target_lang 미정 — 팀 확정 후 채울 것")


if __name__ == "__main__":
    main()
