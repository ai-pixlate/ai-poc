"""번역 길이 팽창률 — 번역 프롬프트.

`poc/C_translate/prompts.py`의 채택 문안(`v6_principle`)과 규제 표를
**복사한 것**이다. 과업 간 코드는 공유하지 않는다(CLAUDE.md).

⚠️ **규칙 4에 길이 제약 지시가 들어 있다.** 초과율은 이 지시의 유무에
크게 흔들리므로, 이 파일 전문이 곧 측정 조건이다. 결과 문서에 그대로 남긴다.

⚠️ 규제 표는 **테스트용 더미**다. 실제 규제 자료가 아니다.
    대체표현이 원표현보다 길거나 짧으면 초과율이 함께 움직인다.
"""

from __future__ import annotations

import json

TARGET_LANG = "영어"

# poc/C_translate/regulation_table_TEST.py 사본 (v2, 15항목).
REGULATION_TABLE: list[dict] = [
    {"금지표현": "미백", "대체표현": "brightening"},
    {"금지표현": "주름 개선", "대체표현": "helps reduce the look of fine lines"},
    {"금지표현": "재생", "대체표현": "renewing"},
    {"금지표현": "치료", "대체표현": "care"},
    {"금지표현": "여드름 완화", "대체표현": "for blemish-prone skin"},
    {"금지표현": "안티에이징", "대체표현": "age-defying"},
    {"금지표현": "즉각", "대체표현": "fast-acting"},
    {"금지표현": "부작용 없음", "대체표현": "gentle formula"},
    {"금지표현": "기미", "대체표현": "uneven-looking areas"},
    {"금지표현": "모공 축소", "대체표현": "pore-refining appearance"},
    {"금지표현": "노화 방지", "대체표현": "age-defying"},
    {"금지표현": "트러블", "대체표현": "blemish-prone concerns"},
    {"금지표현": "100%", "대체표현": "pure"},
    {"금지표현": "의학적", "대체표현": "dermatologist-informed"},
    {"금지표현": "탄력 강화", "대체표현": "for a firmer look"},
]

# 채택 규칙 2 — 열거가 아니라 원리. C 과업에서 33% → 89%로 올린 문안.
RULE_2 = (
    "2. 아래 규제 매핑 표는 **브랜드가 그 효능을 스스로 주장하는 자리**에만 적용한다.\n"
    "   바꾸기 전에 스스로 물어라 — **이 표현을 바꾸면 원문이 가리키던 대상이\n"
    "   달라지거나 사실관계가 틀어지는가?** 그렇다면 바꾸지 말고 원문의 뜻을\n"
    "   그대로 옮긴다.\n"
    "   예) \"미백 효과를 보장하지 않습니다\" — 효능을 부인하는 문장이므로\n"
    "       바꾸면 고지 기능이 깨진다.\n"
    "   예) 후기 인용 \"기미가 옅어졌어요\" — 제3자의 발화이므로 바꾸면\n"
    "       그 사람이 하지 않은 말이 된다."
)

TRANSLATE_SYSTEM = """당신은 한국 화장품 상세페이지를 {target_lang}(으)로 현지화하는 번역가다.

원문은 상세페이지 이미지에서 OCR로 추출한 텍스트다. 다음을 지켜라.

1. 뷰티 도메인 용어를 정확히 옮긴다. 성분명·인증명은 해당 시장에서 통용되는 표기를 쓴다.
{rule_2}
3. 브랜드명·제품명은 번역하지 않고 원표기를 유지한다.
4. 상세페이지 문구이므로 길이를 원문과 비슷하게 유지한다. 이미지 위에 얹을 문구라 길어지면 배치가 깨진다.
5. OCR 오탈자로 보이는 부분은 문맥으로 추정해 옮기되, 추정한 항목은 `note`에 남긴다.

{regulation_block}

같은 페이지의 다른 문구를 문맥으로 함께 준다. 번역 대상은 `segments`뿐이다."""

TRANSLATE_USER = """[같은 페이지 전체 문구 — 문맥용, 번역 대상 아님]
{page_context}

[번역 대상]
{segments}

각 세그먼트를 번역해 아래 JSON 형식으로만 답하라. 다른 말은 붙이지 마라.

{{"translations": [{{"id": "<입력 id 그대로>", "translation": "<번역문>", "note": "<추정·대체한 내용이 있으면. 없으면 빈 문자열>"}}]}}"""


def regulation_block() -> str:
    lines = ["[규제 매핑 표] 아래 표현은 반드시 대체하라."]
    for row in REGULATION_TABLE:
        lines.append(f"  - {row['금지표현']} → {row['대체표현']}")
    return "\n".join(lines)


def build(segments: list[dict], page_context: list[str]) -> tuple[str, str]:
    """세그먼트 목록 → (system, user). segments는 {id, text} 형식."""
    return (
        TRANSLATE_SYSTEM.format(
            target_lang=TARGET_LANG, rule_2=RULE_2, regulation_block=regulation_block()
        ),
        TRANSLATE_USER.format(
            page_context=" / ".join(page_context),
            segments=json.dumps(segments, ensure_ascii=False, indent=1),
        ),
    )
