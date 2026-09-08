"""C. 로컬라이징 번역 — 금지표현의 **직역형** 사전 (평가 전용).

왜 필요한가
    함정 정답률을 "대체표현이 번역문에 있는가"로만 재면 한쪽만 보는 것이 된다.
    대체표현이 없다고 해서 원문을 유지한 것은 아니다 — 모델이 표에 없는 제3의
    표현으로 바꿨을 수도 있다. 치환/유지를 가르려면 **직역형도 함께** 봐야 한다.

    치환됨 = 대체표현 있음 & 직역형 없음
    유지됨 = 직역형 있음 & 대체표현 없음
    불명   = 둘 다 없음 / 둘 다 있음  → 기계가 정하지 않고 육안 판정으로 올린다

왜 규제 표에 넣지 않는가
    직역형은 **채점하는 쪽의 사전**이지 규제 스펙이 아니다. 데이터 담당이 넘겨줄
    실제 규제 표에는 들어가지 않을 항목이므로 분리해 둔다.

⚠️ 규제 표를 갱신하면 이 사전도 같이 갱신할 것.
   누락된 금지표현은 `missing_forms()`가 잡아내며, compare.py가 경고를 찍는다.
"""

from __future__ import annotations

# 금지표현 → 영어 직역형 후보. 하나라도 걸리면 "원문 뜻이 그대로 남았다"로 본다.
#
# 작성 원칙
#   - 대체표현과 어간이 겹치지 않게 고른다. 겹치면 치환/유지를 못 가른다.
#     예) 재생 → 대체 `renewing` 이므로 직역형에 renew 계열을 넣지 않고
#         regenerat 계열만 둔다.
#   - 굴절형을 나열한다. 단어 경계로 매칭하므로 접사가 붙은 형태는 따로 적어야 한다.
LITERAL_FORMS: dict[str, list[str]] = {
    "미백":        ["whitening", "whiten", "whitens", "skin whitening"],
    "주름 개선":    ["wrinkle improvement", "improves wrinkles", "wrinkle reduction",
                    "reduces wrinkles", "anti wrinkle", "wrinkle improving",
                    "improving wrinkles"],
    "재생":        ["regeneration", "regenerating", "regenerate", "regenerates",
                    "regenerative"],
    "치료":        ["treatment", "treating", "treat", "treats", "cure", "cures",
                    "curing", "therapy"],
    "여드름 완화":  ["acne relief", "relieves acne", "acne treatment", "treats acne",
                    "anti acne", "soothes acne", "acne alleviation", "alleviates acne"],
    "안티에이징":   ["anti aging", "antiaging", "anti ageing"],
    "즉각":        ["immediate", "immediately", "instant", "instantly"],
    "부작용 없음":  ["no side effects", "without side effects", "free of side effects",
                    "side effect free", "absence of side effects"],
    "기미":        ["melasma", "dark spots", "dark spot", "pigmentation spots"],
    "모공 축소":    ["pore reduction", "reduces pores", "shrinks pores",
                    "minimizes pores", "pore shrinking", "pore minimizing"],
    "노화 방지":    ["prevents aging", "aging prevention", "anti aging", "antiaging",
                    "prevents ageing"],
    "트러블":      ["trouble", "troubles", "breakouts", "breakout", "acne"],
    "100%":       ["100%", "100 percent"],
    "의학적":      ["medically", "medical", "medicinally"],
    "탄력 강화":    ["elasticity", "firmness", "firming", "improves elasticity",
                    "strengthens elasticity"],
}


def missing_forms(table: list[dict] | None) -> list[str]:
    """규제 표에는 있는데 직역형 사전에 없는 금지표현. 있으면 채점이 반쪽이 된다."""
    if not table:
        return []
    return [r["금지표현"] for r in table
            if r.get("금지표현") and r["금지표현"] not in LITERAL_FORMS]
