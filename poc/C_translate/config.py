"""C. 로컬라이징 번역 — 벤치마크 설정.

미확정 항목은 None으로 두고 채우지 않는다. 임의값을 넣으면 근거 없이 굳는다.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# 팀 확정 필요 — 채우기 전에는 실행이 막힌다
# ─────────────────────────────────────────────────────────────

# 번역 목표 언어 [확정 2026-08-20 / 예람님]: 한국어 → 영어
TARGET_LANG: str | None = "영어"

# ⚠️ **폐기 [2026-08-25]** — 5점 척도와 통과선을 쓰지 않는다.
#    v1에서 2·3·4종 모두 전체 평균 격차가 0.05점이었고 점수가 4.4~4.95에 몰렸다.
#    척도를 **결함 플래그**로 교체했다(PLAN.md 7-4). 아래 둘은 옛 점수(scores/*__by_claude,
#    v1 기준)를 읽을 때만 의미가 있으므로 값만 남기고 실행 경로에서는 쓰지 않는다.
JUDGE_SCALE: int | None = 5      # 폐기 — v1 점수 해석용으로만 남김
JUDGE_PASS: float | None = None  # 폐기 — 통과선 개념 자체가 바뀜

# 규제 매핑 테이블.
# ⚠️ 지금 들어 있는 것은 **테스트용 더미**다. 실제 규제 자료가 아니며 법령 확인을
#    거치지 않았다. 배선 검증 전용 — 데이터 담당과 최소 스펙을 합의한 뒤(문서 2.3
#    선행 조건) 실제 표로 교체하고 regulation_table_TEST.py를 지운다.
from regulation_table_TEST import TEST_TABLE  # noqa: E402

REGULATION_TABLE: list[dict] | None = TEST_TABLE
REGULATION_TABLE_IS_TEST = True   # 결과 기록에 이 사실을 남기기 위한 표식


# ─────────────────────────────────────────────────────────────
# 후보 모델 — 문서 2.3 기준 4종
# ─────────────────────────────────────────────────────────────
# price는 100만 토큰당 USD. Claude는 확정값(2026-06 기준),
# 나머지는 키 확보 시점에 각 벤더 가격표를 확인해 채운다.

MODELS: dict[str, dict] = {
    # ── 상위 티어 (v2 후보 4종. v3.1 예선의 상위 자리) ──────────
    "claude": {
        "vendor": "anthropic",
        "model_id": "claude-opus-5",
        "env_key": "ANTHROPIC_API_KEY",
        "price_in": 5.00,
        "price_out": 25.00,
    },
    "gpt": {
        "vendor": "openai",
        # [2026-08-20 확정 → 2026-08-25 교체] v2 당시의 최신 플래그십이었다.
        # 예선 상위 자리는 `gpt_sol`(gpt-5.6-sol)로 넘어갔다. **지우지 않는다** —
        # results_v2/gpt·cache/gpt가 이 model_id로 만든 결과이며, 라벨이 틀어진다.
        "model_id": "gpt-5.5",
        "env_key": "OPENAI_API_KEY",
        # developers.openai.com/api/docs/pricing 확인 (2026-08-20)
        "price_in": 5.00,
        "price_out": 30.00,
    },
    "gemini": {
        "vendor": "google",
        # [확정 2026-08-20 / 예람님] 최신 Pro 플래그십. 타 후보와 급을 맞춤.
        # preview라 버전이 바뀔 수 있음 — 결과 재현 시 유의
        "model_id": "gemini-3.1-pro-preview",
        "env_key": "GOOGLE_API_KEY",
        # Gemini도 OpenAI 호환 엔드포인트를 제공한다
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        # ai.google.dev/gemini-api/docs/pricing 확인 (2026-08-20)
        # 프롬프트 200k 토큰 이하 요율. 본 평가셋은 문서당 1.5k 수준이라 해당
        "price_in": 2.00,
        "price_out": 12.00,
    },
    "qwen": {
        "vendor": "alibaba",
        # [확정 2026-08-20 / 예람님] 최신 플래그십. claude-opus-5·gpt-5.5와 급을 맞춤
        "model_id": "qwen3.8-max",
        "env_key": "DASHSCOPE_API_KEY",
        # DashScope는 OpenAI 호환 엔드포인트를 제공한다. 국제(싱가포르) 리전 사용.
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        # alibabacloud.com/help/en/model-studio/qwen3-8-max 확인 (2026-08-20)
        # 싱가포르 리전 요율 — 타 리전은 $1.65/$4.951로 더 저렴하다
        "price_in": 2.00,
        "price_out": 6.00,
    },

    # ── 중위·하위 티어 [2026-08-25 각 벤더 공식 가격표 확인] ─────
    # 2단계 예선용. 플래그십 4종의 품질 폭이 1%였으므로 하위 티어로도
    # 충분한지 실측한다(PLAN.md 1-④). 벤더 내 단가차가 5~30배다.

    "claude_sonnet": {
        "vendor": "anthropic",
        "model_id": "claude-sonnet-5",
        "env_key": "ANTHROPIC_API_KEY",
        # platform.claude.com/docs/en/about-claude/pricing 확인 (2026-08-25)
        # 도입가 $2/$10가 정가로 확정됨 — 2026-09-01 인상 예정은 철회
        "price_in": 2.00,
        "price_out": 10.00,
    },
    "claude_haiku": {
        "vendor": "anthropic",
        "model_id": "claude-haiku-4-5-20251001",
        "env_key": "ANTHROPIC_API_KEY",
        "price_in": 1.00,
        "price_out": 5.00,
    },

    "gpt_terra": {
        "vendor": "openai",
        "model_id": "gpt-5.6-terra",
        "env_key": "OPENAI_API_KEY",
        # developers.openai.com/api/docs/pricing 확인 (2026-08-25)
        "price_in": 2.00,
        "price_out": 12.00,
    },
    "gpt_luna": {
        "vendor": "openai",
        "model_id": "gpt-5.6-luna",
        "env_key": "OPENAI_API_KEY",
        "price_in": 0.20,
        "price_out": 1.20,
    },

    # [추가 2026-08-25] `gemini-3.1-pro-preview`가 **preview라 채택 불가**로 판정되어
    # 정식(GA) 대안을 찾는 중이다. 3.x 세대 Pro는 전부 preview뿐이라 GA Pro는 2.5가 마지막.
    # ⚠️ 2단계 예선 모델을 고를 때 이 모델이 조사 목록에서 누락됐다 — 3.7-flash와 단가가 같다.
    "gemini_flash38": {
        "vendor": "google",
        "model_id": "gemini-3.8-flash",
        "env_key": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        # ai.google.dev/gemini-api/docs/pricing 재확인 (2026-08-25)
        # ⚠️ 프로모션가. 2026-12-31 이후 $1.50/$7.50 (3.7-flash와 동일 조건)
        "price_in": 0.75,
        "price_out": 3.75,
    },
    "gemini_flash": {
        "vendor": "google",
        "model_id": "gemini-3.7-flash",
        "env_key": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        # ai.google.dev/gemini-api/docs/pricing 확인 (2026-08-25)
        # ⚠️ 프로모션가. 2026-12-31 이후 $1.50/$7.50으로 오른다
        "price_in": 0.75,
        "price_out": 3.75,
    },
    "gemini_flash_lite": {
        "vendor": "google",
        "model_id": "gemini-3.1-flash-lite",
        "env_key": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "price_in": 0.25,
        "price_out": 1.50,
    },

    "qwen_plus": {
        "vendor": "alibaba",
        "model_id": "qwen3.7-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        # alibabacloud.com/help/en/model-studio/qwen3-7-plus 확인 (2026-08-25)
        # 싱가포르 리전, 입력 256k 이하 요율
        "price_in": 0.40,
        "price_out": 1.60,
    },
    # ⚠️ 선실측에서 **1문서 305초 / 출력 16,174토큰**이 나왔다. 전체 환산 86분으로
    #    품질과 무관하게 서비스에 쓸 수 없다 [제외 확정 2026-08-25 / 예람님].
    #    등록은 남긴다 — 프로브 결과가 캐시에 있고, 제외 근거를 재현할 수 있어야 한다.
    "qwen_flash38": {
        "vendor": "alibaba",
        "model_id": "qwen3.8-flash",
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "price_in": 0.16,
        "price_out": 0.47,
    },
    # 대체 후보. alibabacloud.com/help/en/model-studio/qwen3-7-flash 확인 (2026-08-25)
    # 싱가포르 리전, 입력 32k 이하 요율. **12종 중 최저 단가**다.
    "qwen_flash": {
        "vendor": "alibaba",
        "model_id": "qwen3.7-flash",
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "price_in": 0.03,
        "price_out": 0.13,
    },

    # ⚠️ **조건이 다른 측정이다.** 사고 모드를 끈 `qwen3.7-plus`.
    #    v2 [사고 모드 유지 / 예람님] 결정을 뒤집는 것이 아니라, "서비스에 넣을 설정"으로
    #    쟀을 때 Alibaba가 달라 보이는지를 재는 별도 측정이다.
    #    타 벤더와 같은 표에 넣지 말 것 — v2에서 참고 측정을 섞어 오독한 사고가 있었다.
    "qwen_plus_nothink": {
        "vendor": "alibaba",
        "model_id": "qwen3.7-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "price_in": 0.40,
        "price_out": 1.60,
        "extra_body": {"enable_thinking": False},
    },

    # [확정 2026-08-25 / 예람님] OpenAI 상위 자리를 gpt-5.5 → gpt-5.6-sol로 교체.
    # 근거: v2 확정 기준이 "최신 플래그십, 급을 맞춤"이었고 5.6이 최신 세대다.
    # sol/terra/luna가 한 세대 안의 3티어라 **벤더 내 티어 비교가 세대 혼합 없이 성립**한다.
    # 부수적으로 gpt-5.5($5/$30)보다 싸다.
    "gpt_sol": {
        "vendor": "openai",
        "model_id": "gpt-5.6-sol",
        "env_key": "OPENAI_API_KEY",
        # developers.openai.com/api/docs/pricing 확인 (2026-08-25)
        "price_in": 4.00,
        "price_out": 20.00,
    },
}


# 2단계 예선 대상 12종 — 벤더당 3티어 [확정 2026-08-25] (PLAN.md 4-1)
# `gpt`(gpt-5.5)는 v2 기록 보존용이며 예선 대상이 아니다.
QUALIFIER_TIERS: dict[str, list[str]] = {
    "anthropic": ["claude", "claude_sonnet", "claude_haiku"],
    "openai":    ["gpt_sol", "gpt_terra", "gpt_luna"],
    "google":    ["gemini", "gemini_flash", "gemini_flash_lite"],
    # ⚠️ `qwen`(qwen3.8-max)은 **예선 실행에서 제외** [확정 2026-08-25 / 예람님].
    #    선실측 전체 환산 46분(문서당 2.7분) · 0.653$로, `qwen3.8-flash`를 뺀 것과
    #    같은 기준(서비스 부적합)에 걸린다. 등록·프로브는 남겨 제외 근거를 재현할 수 있게 둔다.
    "alibaba":   ["qwen_plus", "qwen_flash"],
}

# 조건이 다른 참고 측정. **후보 표에 섞지 말 것.**
REFERENCE_ONLY: dict[str, str] = {
    "qwen_plus_nothink": "사고 모드 off — 타 벤더와 조건이 다름",
    "qwen_mt_ref": "번역 전용 모델 — 시스템 프롬프트·JSON 불가",
    "claude_session": "세션 예비 실행 — 조건이 다름",
}

# LLM-as-judge 채점 모델 **2종 교차** [확정 2026-08-25] (PLAN.md 5장·7-5)
#   선정 근거 — 벤더가 다를 것(편향 상쇄) + 최저가 조합.
#   둘 다 후보이기도 하므로 **자기 채점 편향은 교차 결과로 검출**한다.
JUDGE_MODELS: list[str] = ["claude", "gemini"]

JUDGE_MODEL = JUDGE_MODELS[0]   # 옛 경로 호환 (v1 점수 폴더명 등)

# 교차 일치율이 이 값 미만이면 **judge 축을 판정에서 제외하고 육안으로 넘긴다.**
# 두 심사자가 서로 다른 것을 보고 있다는 뜻이므로 어느 쪽도 근거가 되지 않는다.
JUDGE_AGREEMENT_MIN = 0.70

# 저점 기준 — 이 점수 **이하**를 "문제 있음"으로 센다 (1~10점 척도).
#   평균만 보면 결함이 사라진다. 128건 중 3건이 2점이어도 평균은 9.81점이다.
#   그래서 분야별 평균과 **저점 건수**를 반드시 함께 낸다.
JUDGE_LOW = 7


def missing_settings() -> list[str]:
    """실행을 막아야 할 항목만 모은다. JUDGE_PASS는 집계 단계에서만 필요하므로 뺀다."""
    missing = []
    if TARGET_LANG is None:
        missing.append("TARGET_LANG (번역 목표 언어)")
    if JUDGE_SCALE is None:
        missing.append("JUDGE_SCALE (judge 점수 척도)")
    if REGULATION_TABLE is None:
        missing.append("REGULATION_TABLE (규제 매핑 테이블)")
    return missing


def pending_notes() -> list[str]:
    """실행은 되지만 결과 해석 시 유의할 항목."""
    notes = []
    if REGULATION_TABLE_IS_TEST:
        notes.append("REGULATION_TABLE이 테스트용 더미 — 모든 결론은 실제 표 확보 전까지 잠정")
    if len(JUDGE_MODELS) < 2:
        notes.append("judge가 1종 — 교차 검증 불가. 자기 채점 편향을 판별할 수 없음")
    return notes
