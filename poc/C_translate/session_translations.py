"""C. 로컬라이징 번역 — 세션 예비 실행 결과.

⚠️ 이것은 **벤치마크 결과가 아니다.**

Claude Code 세션(claude-opus-5)에서 prompts.py의 지시를 따라 직접 번역한 것이다.
세션에는 Claude Code 시스템 프롬프트와 PoC 전체 대화가 맥락으로 들어 있어
깨끗한 조건이 아니며, 다른 후보 모델은 그 맥락 없이 돌게 된다. 공정 비교 불가.

용도: 프롬프트·출력형식 배선 검증 + 품질 감 잡기 (비용 0)
결과 기록 시 "예비 실행"으로만 표기할 것.

작성일 2026-08-20 / 목표 언어 영어 / 규제표 테스트용 더미
"""

# id → (translation, note)
TRANSLATIONS: dict[str, tuple[str, str]] = {
    # 1.jpg
    "1-05": ("Keycap Keyring", ""),
    "1-06": ("While supplies last!", ""),
    "1-09": ("Oisyu", "캐릭터명으로 판단해 음역 유지"),
    "1-10": ("WONI's PICK! No.1", "OCR '윈이'를 인물명 '원이'로 추정"),
    "1-11": ("Makeup-Ready", "'화잘먹' = 화장이 잘 받는다는 은어. 직역 대신 의미 전달"),
    "1-12": ("Pore", ""),
    "1-13": ("Serum", ""),
    # 2.jpg
    "2-01": ("Buy the Collagen Peptide Serum", ""),
    "2-02": ("Lisenne WONI Oisyu♡", "OCR '오이쉬스'의 끝 글자를 하트 기호 오인식으로 추정"),
    "2-03": ("Keycap Keyring Gift!", ""),
    "2-04": ("Oisyu", ""),
    "2-12": ("Keycap Keyring", ""),
    "2-13": ("While supplies last!", ""),
    "2-14": ("· Gift period: 8/19–8/23 (first-come, ends when stock runs out)", ""),
    "2-15": ("· Gifts are limited in quantity, given on a first-come basis, and may run out early.", ""),
    "2-16": ("· Exact gift details can be checked in [Order Details] after ordering.", ""),
    "2-17": ("· Today Dream / Pickup service orders are not eligible for gifts", ""),
    "2-18": ("• Gifts must be returned together with the product upon return.", ""),
    # 4.jpg
    "4-04": ("Starting now,", "OCR '운'은 다음 세그먼트로 이어지는 조각으로 판단해 생략"),
    "4-05": ("WONI's Collagen", ""),
    "4-06": ("With radiant WONI", ""),
    "4-07": ("every day, light and easy", ""),
    "4-08": ("building up", ""),
    "4-09": ("bouncy", "OCR '쏜쏜한' → '쫀쫀한'으로 추정"),
    "4-10": ("makeup-ready", ""),
    "4-11": ("routine!", ""),
    # 6.jpg
    "6-03": ("Double", ""),
    "6-04": ("Deal", ""),
    "6-05": ("Exclusive", ""),
    "6-06": ("Limited", ""),
    "6-07": ("Deal", ""),
    "6-09": ("OLIVE YOUNG", "유통사명 원표기 유지"),
    "6-10": ("Exclusive Deal", ""),
    "6-11": ("Size", ""),
    "6-14": ("Pore-Tightening", "OCR '글 쪼쯤' → '모공 쫀쫀'으로 추정. 확신 낮음"),
    "6-16": ("Pore", ""),
    "6-18": ("Collagen", ""),
    "6-19": ("Serum", ""),
    "6-21": ("Collagen Pore Serum", ""),
    "6-22": ("Pore Perfecting Collagen Peptide Serum", "제품명 — 영문 공식 표기 사용"),
    "6-23": ("Limited Double Deal", ""),
    "6-26": ("Pore Perfecting Collagen Peptide Serum", ""),
    # 7.jpg
    "7-31": ("100 Million Sheets*", ""),
    "7-32": ("The same collagen mask know-how!", ""),
    "7-33": ("[Main] Pore Perfecting Collagen Peptide Serum 30ml + 30ml",
             "OCR '30m'을 '30ml'로 보정"),
    "7-34": ("*Based on Biodance Bio Collagen Real Deep Mask production volume, Apr 2021–Aug 2025",
             "'바이오던스' → 브랜드 영문 표기 Biodance"),
    # 8.jpg
    "8-03": ("Biodance's commitment to balanced skin", ""),
    "8-07": ("19 ingredients of concern", ""),
    "8-08": ("MFDS-listed allergens", "'식약처' → Ministry of Food and Drug Safety 약어"),
    "8-09": ("Low skin irritation", ""),
    "8-10": ("Free*", ""),
    "8-11": ("25 allergen triggers free", ""),
    "8-12": ("Test completed", ""),
    "8-13": ("· Items: Phenoxyethanol, Benzyl Alcohol, Benzoic Acid, Chlorphenesin, "
             "Diazolidinyl Urea, Sorbic Acid, Benzophenone-3, Isopropyl Alcohol, "
             "Triethanolamine, Benzalkonium Chloride (C12-C14)",
             "OCR 훼손 심함. 성분명 10개를 표준 INCI 표기로 복원 추정 — 원문 대조 필요"),
    "8-14": ("Butylated Hydroxytoluene, Propylene Glycol, Methylparaben, Ethylparaben, "
             "Isopropylparaben, Propylparaben, Isobutylparaben, Butylparaben, "
             "p-Hydroxybenzoic Acid",
             "OCR 훼손 심함. 성분명 9개 복원 추정 — 원문 대조 필요"),
    # 9.jpg
    "9-01": ("Biggest Ever Limited Deal", ""),
    "9-03": ("Double X Double", ""),
    "9-04": ("OLIVE YOUNG", ""),
    "9-05": ("Exclusive Deal", ""),
    "9-06": ("Black", "'블랙'+'헤드'가 blackhead로 이어지는 조각"),
    "9-11": ("head", "앞 조각과 합쳐 blackhead"),
    "9-28": ("Sensitive", ""),
    "9-32": ("Skin", ""),
    "9-35": ("Low Irritation", ""),
    # 10.jpg
    "10-02": ("Extra Gift", ""),
    "10-05": ("OLIVE YOUNG", ""),
    "10-06": ("Exclusive Deal", ""),
    "10-08": ("Skin Irritation", ""),
    "10-10": ("Review Event", ""),
    "10-11": ("KRW 3,000", "통화 단위 명시"),
    "10-12": ("SUNG HANBIN's PICK", "인물명 로마자 표기"),
    "10-14": ("No.1", ""),
    "10-15": ("Pack Cleanser", ""),
    "10-16": ("*No.1 in the OLIVE YOUNG online mall cleansing category sales ranking, "
              "as of 09:00 on 2026.01.30", ""),
    "10-17": ("*No.1 in the OLIVE YOUNG online mall cleansing category sales ranking, "
              "as of 08:00 and 09:00 on 2026.06.29", ""),
    # 11.jpg
    "11-09": ("Stick-On Collagen Ampoule", ""),
    "11-16": ("#ElasticityLifting #PoreFilling", "해시태그 형식 유지"),
    "11-26": ("MEDIHEAL Hyper Collagen Mask",
              "OCR '이디협 하이퍼 클라견아스크' → 문맥의 MEDIHEAL / HYPER COLLAGEN으로 복원"),
    "11-28": ("Limited Deal", ""),
    "11-31": ("Extra Gift!", ""),
    "11-32": ("", "OCR '이이' — 복원 불가. 문맥상 '8+1'의 일부로 보이나 확정 못 함"),
    "11-44": ("Exclusive", ""),
    "11-45": ("Deal", ""),
    "11-46": ("OLIVE YOUNG", ""),
    # 12.jpg
    "12-04": ("WONI", ""),
    "12-11": ("Collagen", ""),
    "12-12": ("Moisture", ""),
    "12-13": ("Cream", ""),
}
