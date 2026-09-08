"""C. 로컬라이징 번역 — 합성 평가셋 세션 예비 실행 결과.

⚠️ 벤치마크 결과가 아니다. 세션(claude-opus-5)에서 prompts.py 지시대로 번역한 것.
   조건이 다르므로 다른 후보와 공정 비교할 수 없다. 배선 검증·품질 감 잡기 전용.

작성일 2026-08-20 / 한국어→영어 / 규제표 테스트용 더미 8종
"""

TRANSLATIONS: dict[str, tuple[str, str]] = {
    # 01_intro
    "01_intro-01": ("LUMIÈRE Collagen Ampoule", "브랜드명 원표기 유지"),
    "01_intro-02": ("Start your firming routine now", ""),
    "01_intro-03": ("One drop a day, lightly layered", ""),
    "01_intro-04": ("Low-molecular collagen that fills from within", ""),
    "01_intro-05": ("Time for a change in your skin", ""),
    "01_intro-06": ("Comfortable even for sensitive skin", ""),
    "01_intro-07": ("Daily Ampoule 30ml", ""),
    "01_intro-08": ("Celebrating our new launch", ""),
    # 02_benefit — 규제 치환 집중 구간
    "02_benefit-01": ("Brightening functional cosmetic", "규제표 적용: 미백 → brightening"),
    "02_benefit-02": ("Dual-function care that helps reduce the look of fine lines",
                      "규제표 적용: 주름 개선 → helps reduce the look of fine lines"),
    "02_benefit-03": ("Helps renew tired skin", "규제표 적용: 재생 → renewing"),
    "02_benefit-04": ("A fast-acting surge of moisture", "규제표 적용: 즉각 → fast-acting"),
    "02_benefit-05": ("The start of age-defying care", "규제표 적용: 안티에이징 → age-defying"),
    "02_benefit-06": ("Brightens a dull-looking skin tone", ""),
    "02_benefit-07": ("For skin that has lost its firmness", ""),
    "02_benefit-08": ("Even flakiness caused by dryness", ""),
    "02_benefit-09": ("A close-fitting texture that fills every pore", ""),
    "02_benefit-10": ("92% satisfaction after 4 weeks of use*", ""),
    # 03_ingredient
    "03_ingredient-01": ("3 key ingredients", ""),
    "03_ingredient-02": ("Hydrolyzed Collagen", "INCI 표기"),
    "03_ingredient-03": ("Contains 2% Niacinamide", "INCI 표기, 함량 표기 유지"),
    "03_ingredient-04": ("Contains 0.04% Adenosine", "INCI 표기, 함량 표기 유지"),
    "03_ingredient-05": ("5-type Hyaluronic Acid complex", ""),
    "03_ingredient-06": ("Panthenol and Ceramide form a moisture barrier", "INCI 표기"),
    "03_ingredient-07": ("Soothing with Centella Asiatica Extract",
                         "'병풀추출물'의 학명 표기를 채택 — 해외 시장 통용 표기"),
    "03_ingredient-08": ("An ingredient blend for blemish-prone skin",
                         "규제표 적용: 여드름 완화 → for blemish-prone skin"),
    "03_ingredient-09": ("Fragrance-free, colorant-free formula", ""),
    "03_ingredient-10": ("The full ingredient list is printed on the container and carton", ""),
    # 04_safety
    "04_safety-01": ("Low-irritation skin test completed", ""),
    "04_safety-02": ("Free of 25 allergen ingredients", ""),
    "04_safety-03": ("Complies with MFDS notification standards",
                     "'식약처' → Ministry of Food and Drug Safety 약어"),
    "04_safety-04": ("Vegan certified", "인증명"),
    "04_safety-05": ("Not tested on animals", ""),
    "04_safety-06": ("A verified gentle formula",
                     "규제표 적용: 부작용 없음 → gentle formula. "
                     "치환하면서 '순한 처방'과 의미가 겹쳐 한 구로 합침"),
    "04_safety-07": ("Clinical testing on sensitive skin completed", ""),
    "04_safety-08": ("*Human application test under dermatologist supervision, "
                     "32 adult women, 4 weeks", ""),
    # 05_howto
    "05_howto-01": ("How to Use", ""),
    "05_howto-02": ("After cleansing, smooth the skin with toner", ""),
    "05_howto-03": ("Dispense 2–3 drops and spread over the entire face", ""),
    "05_howto-04": ("Press in with your palms to help it absorb", ""),
    "05_howto-05": ("Recommended twice daily, morning and night", ""),
    "05_howto-06": ("Layer again on dry areas", ""),
    "05_howto-07": ("Best used before your cream step", ""),
    # 06_texture
    "06_texture-01": ("A watery texture that sinks in fresh", ""),
    "06_texture-02": ("Finishes without stickiness", ""),
    "06_texture-03": ("Light enough to wear before makeup", ""),
    "06_texture-04": ("Spreads thin and clings close", ""),
    "06_texture-05": ("Leaves a subtle glow", ""),
    # 07_promo
    "07_promo-01": ("Exclusive Limited Deal", ""),
    "07_promo-02": ("1+1 Double Deal", ""),
    "07_promo-03": ("First 3,000 customers", ""),
    "07_promo-04": ("Free 10ml miniature with purchase", ""),
    "07_promo-05": ("KRW 3,000 in points for writing a review", "통화 단위 명시"),
    "07_promo-06": ("Gift period: Aug 19 – Aug 23 (ends early if stock runs out)", ""),
    "07_promo-07": ("No.1 in online mall skincare category sales*", ""),
    "07_promo-08": ("*Based on our own online store, June 2026", ""),
    # 08_notice
    "08_notice-01": ("Precautions for Use", ""),
    "08_notice-02": ("Avoid use on wounded areas", ""),
    "08_notice-03": ("If red spots, swelling, or itching occur during use, "
                     "discontinue use and consult a specialist", ""),
    "08_notice-04": ("Store in a cool place away from direct sunlight", ""),
    "08_notice-05": ("Keep out of reach of children", ""),
    "08_notice-06": ("This product is not a drug and cannot be used for the purpose of "
                     "treating disease",
                     "⚠️ 규제표는 '치료 → care'를 지시하나 **따르지 않았음**. "
                     "이 문장은 효능을 주장하는 것이 아니라 '치료 목적으로 쓸 수 없다'고 "
                     "부인하는 법정 고지문이다. 치환하면 문장이 무의미해지고 고지 기능이 깨진다"),
    "08_notice-07": ("Use as soon as possible after opening", ""),
    "08_notice-08": ("Exchanges and refunds are available within 7 days of receipt", ""),
}
