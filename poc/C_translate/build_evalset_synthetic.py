"""C. 로컬라이징 번역 — 합성 평가셋 생성기.

synthetic_source.py의 가상 상세페이지 텍스트를 evalset.json 형식으로 만든다.
스키마는 build_evalset.py(OCR 기반)와 동일해 이후 도구를 그대로 쓴다.

사용법
    python build_evalset_synthetic.py
    python build_evalset_synthetic.py --out evalset.json

OCR 기반 평가셋과의 차이
    - `manual_fix` 칸이 없다. 원문이 정답이므로 고칠 것이 없다.
    - `source_kind`가 `synthetic`으로 찍힌다. 결과 해석 시 이 값을 확인할 것.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import config
from synthetic_source import DOCUMENTS, TRAPS

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evalset.json")
    args = ap.parse_args()

    documents, n_seg = [], 0
    for name, lines in DOCUMENTS:
        # 세그먼트는 평문 문자열 또는 S(...) 딕셔너리다 (v3에서 role·expect_term 추가)
        entries = [e if isinstance(e, dict) else {"text": e} for e in lines]
        segments = [
            {"id": f"{name}-{i:02d}", "region": i, "bbox": None,
             "source": e["text"], "manual_fix": "",
             "role": e.get("role"), "expect_term": e.get("expect_term") or []}
            for i, e in enumerate(entries, 1)
        ]
        documents.append({
            "image": f"{name}.synthetic",
            "page_text": [e["text"] for e in entries],   # 합성이므로 문맥 = 문서 전체
            "segments": segments,
        })
        n_seg += len(segments)

    out = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_kind": "synthetic",
        "source": "poc/C_translate/synthetic_source.py (가상 데이터 — 실존 제품 아님)",
        "note": "원문 OCR이 완벽하다는 가정. OCR 오류와 번역 품질을 분리하기 위함 (2026-08-20 결정)",
        "target_lang": config.TARGET_LANG,
        "documents": documents,
        "counts": {"documents": len(documents), "segments": n_seg},
    }
    path = HERE / args.out
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    chars = sum(len(s["source"]) for d in documents for s in d["segments"])
    print(f"평가셋 작성: {path}")
    print(f"  문서 {len(documents)}개 / 세그먼트 {n_seg}개 / 문자 {chars}")

    # ── 함정 구성 점검 ───────────────────────────────────────
    # v3의 목적은 `유지`를 늘리는 것이다. 의도한 배분이 실제로 나왔는지 확인한다.
    banned = [r["금지표현"] for r in (config.REGULATION_TABLE or [])]
    hits = [(s["id"], b) for d in documents for s in d["segments"]
            for b in banned if b in s["source"]]

    by_kind: dict[tuple[str, str], int] = {}
    for sid, _ in hits:
        by_kind[TRAPS.get(sid, ("대조군", "치환"))] = \
            by_kind.get(TRAPS.get(sid, ("대조군", "치환")), 0) + 1

    keep = sum(n for (_, e), n in by_kind.items() if e == "유지")
    swap = sum(n for (_, e), n in by_kind.items() if e == "치환")
    print(f"\n금지표현 등장 {len(hits)}쌍 — 유지 {keep}쌍 / 치환 {swap}쌍")
    for (kind, exp), n in sorted(by_kind.items(), key=lambda x: (x[0][1], x[0][0])):
        print(f"   {n:>3}쌍  {exp}  {kind}")

    terms = [t for d in documents for s in d["segments"] for t in s["expect_term"]]
    roles = {s["role"] for d in documents for s in d["segments"]} - {None}
    print(f"\nexpect_term {len(terms)}건 / role {sorted(roles)}")

    unused = [b for b in banned if not any(b == x for _, x in hits)]
    if unused:
        print(f"  [!] 규제 표에 있으나 원문 미등장: {', '.join(unused)}")
    orphan = [sid for sid in TRAPS if sid not in {s["id"] for d in documents
                                                  for s in d["segments"]}]
    if orphan:
        print(f"  [!] TRAPS에만 있고 평가셋에 없는 id: {', '.join(orphan)}")
    silent = [sid for sid in TRAPS if sid not in {s for s, _ in hits}]
    if silent:
        print(f"  [!] 함정으로 지정됐으나 금지표현이 검출되지 않는 id: {', '.join(silent)}")


if __name__ == "__main__":
    main()
