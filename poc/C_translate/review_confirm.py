"""C. 로컬라이징 번역 — 육안 확정 기록.

기계 detector가 `?`(불명)으로 보류한 건을 **사람이 확인해 확정한 결과**다.
`compare.py`가 이 파일을 읽어 판정을 덮어쓴다.

규칙
    - **기계가 `?`로 보류한 건만** 넣는다. `O`/`X` 판정을 뒤집지 않는다.
      뒤집으면 확인이 아니라 측정을 덮어쓰는 것이 된다.
    - **근거를 반드시 적는다.** 근거 없는 확정은 "확인했다"는 기록만 남기고
      실제 검증은 없는 상태를 만든다(CLAUDE.md — 등급을 임의로 채우지 않는다).
    - detector가 개선돼 더 이상 `?`가 아닌 항목은 `compare.py`가 경고를 찍는다. 그때 지운다.

확정 [2026-08-25 / 예람님] — 불명 13건 전부 `O`.

    11건은 **직역형 사전 누락**이었다. `therapeutic` · `renewal` · `pore shrinkage` ·
    `pore minimization` 등 정상 번역인데 `literal_forms.py`에 없어 보류된 건들이다.

    2건(`16_award-03`)은 판단이 필요했다 — `소비자 선정 트러블 케어 브랜드 1위`를
    `No.1 Blemish Care Brand`로 옮긴 건이다. 규제 대체표현(`blemish-prone concerns`)도
    직역(`trouble`)도 아니다. **「트러블」이 한국어권 조어**라 영어 자연 표기가 `Blemish`이므로
    규제 치환이 아니라 **번역 선택**으로 판단했다.
"""

from __future__ import annotations

# (대상, 세그먼트 id, 금지표현) -> (판정, 근거)
CONFIRMED: dict[tuple[str, str, str], tuple[str, str]] = {
    ("v6_principle/gemini_flash38", "13_quote-02", "치료"):
        ("O", "therapeutic - 원 뜻 유지. 직역형 사전에 없던 표현"),
    ("v6_principle/gpt_sol", "09_regulation_edge-04", "재생"):
        ("O", "renewal - 대체표현 renewing의 명사형. 치환으로 봄"),
    ("v6_principle/gpt_sol", "09_regulation_edge-06", "재생"):
        ("O", "renewal - 대체표현 renewing의 명사형. 치환으로 봄"),
    ("v6_principle/gpt_sol", "11_denial-02", "주름 개선"):
        ("O", "Wrinkle-reducing - 원 뜻 유지, 대체표현 미사용"),
    ("v6_principle/gpt_sol", "15_ui_label-03", "재생"):
        ("O", "양립 유형 - 치환/유지 어느 쪽이든 정답"),
    ("v6_principle/gpt_sol", "15_ui_label-03", "트러블"):
        ("O", "양립 유형 - 치환/유지 어느 쪽이든 정답"),
    ("v6_principle/gpt_sol", "16_award-03", "트러블"):
        ("O", "「트러블」은 한국어권 조어. 영어 자연 표기가 Blemish이므로 규제 치환이 아니라 번역 선택으로 봄"),
    ("v6_principle/gpt_terra", "13_quote-06", "모공 축소"):
        ("O", "pore shrinkage / minimization - 원 뜻 유지. 직역형 사전에 없던 표현"),
    ("v6_principle/gpt_terra", "15_ui_label-03", "트러블"):
        ("O", "양립 유형 - 치환/유지 어느 쪽이든 정답"),
    ("v6_principle/gpt_terra", "16_award-03", "트러블"):
        ("O", "「트러블」은 한국어권 조어. 영어 자연 표기가 Blemish이므로 규제 치환이 아니라 번역 선택으로 봄"),
    ("v6_principle/gpt_terra", "16_award-04", "재생"):
        ("O", "Renewal - 부문명 원 뜻 유지"),
    ("v6_principle/qwen_plus", "13_quote-02", "치료"):
        ("O", "therapeutic - 원 뜻 유지. 직역형 사전에 없던 표현"),
    ("v6_principle/qwen_plus", "13_quote-06", "모공 축소"):
        ("O", "pore shrinkage / minimization - 원 뜻 유지. 직역형 사전에 없던 표현"),
}
