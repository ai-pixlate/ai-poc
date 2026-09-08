"""세션 예비 번역을 run.py와 같은 출력 형식으로 저장한다.

results/claude_session/{stem}.json — API 결과와 같은 도구로 비교하기 위함.
변형 이름을 `claude_session`으로 둬 벤치마크 결과(`claude`)와 섞이지 않게 한다.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import config

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default="session_translations_synth",
                    help="번역이 담긴 모듈. OCR 평가셋용은 session_translations")
    ap.add_argument("--evalset", default="evalset.json")
    ap.add_argument("--out", default="claude_session")
    args = ap.parse_args()

    TRANSLATIONS = importlib.import_module(args.module).TRANSLATIONS
    OUT = HERE / "results" / args.out
    data = json.loads((HERE / args.evalset).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    missing, filled, empty = [], 0, 0
    for doc in data["documents"]:
        rows = []
        for s in doc["segments"]:
            if s["id"] not in TRANSLATIONS:
                missing.append(s["id"])
                continue
            text, note = TRANSLATIONS[s["id"]]
            rows.append({"id": s["id"], "translation": text, "note": note})
            filled += 1
            if not text:
                empty += 1
        stem = Path(doc["image"]).stem
        (OUT / f"{stem}.json").write_text(json.dumps({
            "image": doc["image"],
            "model": "claude_session",
            "kind": "예비 실행 — 벤치마크 아님",
            "target_lang": config.TARGET_LANG,
            "regulation_table_is_test": config.REGULATION_TABLE_IS_TEST,
            "translations": rows,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    total = data["counts"]["segments"]
    print(f"저장 → {OUT}")
    print(f"  세그먼트 {filled}/{total} 번역")
    print(f"  번역 불가(빈 문자열) {empty}건")
    if missing:
        print(f"  ⚠️ 누락 {len(missing)}건: {missing}")

    # 규제 치환이 실제로 이뤄졌는지 — 금지표현이 있는 원문의 번역에 대체표현이 들어갔나
    rows = {r["금지표현"]: r["대체표현"] for r in (config.REGULATION_TABLE or [])}
    print(f"\n규제 치환 점검 (금지표현 {len(rows)}종)")
    print(f"  {'세그먼트':<20}{'금지표현':<12}{'치환':<6}비고")
    ok = skipped = intentional = 0
    for doc in data["documents"]:
        for s in doc["segments"]:
            src = s["manual_fix"] or s["source"]
            for banned, repl in rows.items():
                if banned not in src:
                    continue
                tr, note = TRANSLATIONS.get(s["id"], ("", ""))
                # 대체표현의 첫 단어를 어간까지만 비교한다. 문장에 녹이면 어형이 바뀌므로
                # (renewing → renew) 완전일치로 보면 적용된 것을 미적용으로 오판한다.
                stem = repl.split()[0].lower()[:5]
                applied = stem in tr.lower()
                deliberate = note.startswith("⚠️")   # 의도적 미적용은 note에 근거를 남긴다
                if applied:
                    ok += 1
                    mark, tag = "O", ""
                elif deliberate:
                    intentional += 1
                    mark, tag = "-", "의도적 미적용 — note 참조"
                else:
                    skipped += 1
                    mark, tag = "X", "← 미적용. 확인 필요"
                print(f"  {s['id']:<20}{banned:<12}{mark:<6}{tag}")
    print(f"  적용 {ok}건 / 의도적 미적용 {intentional}건 / 미확인 {skipped}건")


if __name__ == "__main__":
    main()
