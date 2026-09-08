# C. 로컬라이징 번역 — 1차 정량 집계

> 자동 생성. `compare.py` 재실행 시 덮어씀.

- 평가셋: `synthetic` — 문서 17개 / 세그먼트 128개
- 목표 언어: 영어
- 판정 구조: **1차 정량(이 표) → 2차 judge → 육안 확정** (PLAN.md 7장)

> ⚠️ 규제 표가 **테스트용 더미**다. 결과는 실제 규제 준수 판단 근거가 아니며, 실제 표 확보 전까지 **잠정**이다.

## 1. 실행 요약

| 대상 | 모델 | 호출 | 입력tok | 출력tok | 소요 | 실측 비용 | 비고 |
|---|---|---|---|---|---|---|---|
| `v6_principle/gemini` | gemini-3.1-pro-preview | 17 | 21277 | 7238 | 2208s | 0.1294$ |  |
| `v6_principle/gemini_flash38` | gemini-3.8-flash | 17 | 21277 | 6628 | 209s | 0.0408$ |  |
| `v6_principle/claude` | claude-opus-5 | 17 | 33110 | 11515 | 171s | 0.4534$ |  |
| `v6_principle/gpt_sol` | gpt-5.6-sol | 17 | 20744 | 7965 | 139s | 0.2423$ |  |
| `v6_principle/gpt_terra` | gpt-5.6-terra | 17 | 20744 | 5927 | 77s | 0.1126$ |  |
| `v6_principle/qwen_plus` | qwen3.7-plus | 17 | 20115 | 53358 | 1532s | 0.0934$ |  |

## 2. 1차 정량 지표

| 대상 | 함정 정답률 | 불명 | 용어 정확도 | **숫자 보존** | 미번역 잔존 | 세그먼트 누락 | JSON 성공률 | 문자수 비율 |
|---|---|---|---|---|---|---|---|---|
| `v6_principle/gemini` | 100% | 0 | 12/12 (100%) | 30/30 (100%) | 0 | 0 | 100% | 2.27 |
| `v6_principle/gemini_flash38` | 93% | 0 | 12/12 (100%) | 30/30 (100%) | 0 | 0 | 100% | 2.39 |
| `v6_principle/claude` | 92% | 0 | 11/12 (92%) | 30/30 (100%) | 0 | 0 | 100% | 2.29 |
| `v6_principle/gpt_sol` | 92% | 0 | 11/12 (92%) | 30/30 (100%) | 0 | 0 | 100% | 2.27 |
| `v6_principle/gpt_terra` | 90% | 0 | 10/12 (83%) | 30/30 (100%) | 0 | 0 | 100% | 2.31 |
| `v6_principle/qwen_plus` | 82% | 0 | 12/12 (100%) | 30/30 (100%) | 0 | 0 | 100% | 2.18 |

> `함정 정답률` 분모에서 **미실행(`—`)과 불명(`?`)을 제외**한다. 미실행을 오답으로 세어 정답률을 52%로 오독한 사고가 있었다(PoC 문서 2.3).
> `불명`은 기계가 판정하지 않고 육안으로 올린 건수다 → `review_traps.md`
> `미번역 잔존`에서 제품명 유지 세그먼트는 제외한다 — 한글이 남는 것이 정답이다.
> `숫자 보존`은 **환각 축의 일부**다. 원문에 없는 정보를 지어내는 유형은 기계로 못 잡으며 3단계 결승에서 judge가 맡는다(7-4 `added_info`).

## 3. 예선 필수 통과 조건

정량 상위라도 하나라도 못 지키면 탈락 (PLAN.md 4-2).

| 대상 | JSON 파싱 실패 | 세그먼트 누락 | 미번역 잔존 | 판정 |
|---|---|---|---|---|
| `v6_principle/gemini` | 0 | 0 | 0 | 통과 |
| `v6_principle/gemini_flash38` | 0 | 0 | 0 | 통과 |
| `v6_principle/claude` | 0 | 0 | 0 | 통과 |
| `v6_principle/gpt_sol` | 0 | 0 | 0 | 통과 |
| `v6_principle/gpt_terra` | 0 | 0 | 0 | 통과 |
| `v6_principle/qwen_plus` | 0 | 0 | 0 | 통과 |

## 4. 함정 정답률 — 기대 동작 대비 정오

**치환 여부가 아니다.** 부인·고지 문맥 / 인용문 / 제품명은 **치환하지 않는 것**이 정답이다.

| 세그먼트 | 금지표현 | 유형 | 기대 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|---|---|
| 02_benefit-01 | 미백 | 대조군 | 치환 | O | O | O | O | O | O |
| 02_benefit-03 | 재생 | 대조군 | 치환 | O | O | O | O | O | O |
| 02_benefit-04 | 즉각 | 대조군 | 치환 | O | O | O | O | O | O |
| 03_ingredient-08 | 여드름 완화 | 대조군 | 치환 | O | O | O | O | O | O |
| 04_safety-06 | 부작용 없음 | 대조군 | 치환 | O | O | O | O | O | O |
| 08_notice-06 | 치료 | A 부인 문맥 | 유지 | O | O | O | O | **X** | O |
| 09_regulation_edge-01 | 미백 | A 주장 문맥 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-02 | 주름 개선 | A 주장 문맥 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-03 | 재생 | B 부분일치(재생력) | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-04 | 재생 | B 부분일치(재생 주기) | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-05 | 미백 | E 금지어 2개 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-05 | 주름 개선 | E 금지어 2개 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-06 | 재생 | F 조사 결합 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-06 | 탄력 강화 | F 조사 결합 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-07 | 안티에이징 | 중복 대체표현 | 치환 | O | O | O | O | O | O |
| 09_regulation_edge-07 | 노화 방지 | 중복 대체표현 | 치환 | O | O | O | O | O | O |
| 11_denial-01 | 미백 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-02 | 주름 개선 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-02 | 의학적 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-03 | 여드름 완화 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-04 | 부작용 없음 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-05 | 모공 축소 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-06 | 치료 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-06 | 기미 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 11_denial-07 | 안티에이징 | A 부인 문맥 | 유지 | O | O | O | O | O | O |
| 12_product_name-01 | 미백 | C 제품명(명시) | 유지 | O | O | O | O | O | **X** |
| 12_product_name-02 | 안티에이징 | C 제품명(명시) | 유지 | O | O | O | O | O | **X** |
| 12_product_name-03 | 재생 | C 제품명(명시) | 유지 | O | O | O | O | O | **X** |
| 12_product_name-04 | 트러블 | C 제품명(명시) | 유지 | O | O | O | O | O | **X** |
| 12_product_name-05 | 100% | C 제품명(명시) | 유지 | O | O | O | O | O | **X** |
| 12_product_name-06 | 안티에이징 | C 제품명(암시) | 유지 | O | **X** | **X** | **X** | **X** | **X** |
| 12_product_name-07 | 미백 | C 제품명(암시) | 유지 | O | **X** | **X** | **X** | **X** | **X** |
| 12_product_name-08 | 재생 | C 제품명(암시) | 유지 | O | **X** | **X** | **X** | **X** | **X** |
| 12_product_name-09 | 트러블 | C 제품명(암시) | 유지 | O | **X** | **X** | **X** | **X** | **X** |
| 12_product_name-10 | 탄력 강화 | C 제품명(암시) | 유지 | O | **X** | **X** | **X** | **X** | **X** |
| 13_quote-01 | 기미 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-02 | 치료 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-03 | 트러블 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-04 | 미백 | D 인용문 | 유지 | O | O | **X** | O | O | O |
| 13_quote-05 | 주름 개선 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-06 | 모공 축소 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-07 | 재생 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-08 | 즉각 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-09 | 의학적 | D 인용문 | 유지 | O | O | O | O | O | O |
| 13_quote-10 | 안티에이징 | D 인용문 | 유지 | O | O | O | O | O | O |
| 14_legal_ref-01 | 미백 | G 법령·고시 인용 | 유지 | O | O | O | O | O | **X** |
| 14_legal_ref-02 | 주름 개선 | G 법령·고시 인용 | 유지 | O | O | O | O | O | O |
| 14_legal_ref-03 | 여드름 완화 | G 법령·고시 인용 | 유지 | O | O | O | O | O | O |
| 14_legal_ref-04 | 미백 | G 법령·고시 인용 | 유지 | O | O | O | O | O | **X** |
| 14_legal_ref-04 | 주름 개선 | G 법령·고시 인용 | 유지 | O | O | O | O | O | O |
| 14_legal_ref-05 | 미백 | G 법령·고시 인용 | 유지 | O | O | O | O | O | **X** |
| 15_ui_label-01 | 미백 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-02 | 안티에이징 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-02 | 탄력 강화 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-03 | 재생 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-03 | 모공 축소 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-03 | 트러블 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-04 | 주름 개선 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 15_ui_label-05 | 기미 | H UI 라벨·카테고리 | 양립 | O | O | O | O | O | O |
| 16_award-01 | 미백 | I 수상·부문명 | 유지 | O | O | O | **X** | **X** | O |
| 16_award-02 | 안티에이징 | I 수상·부문명 | 유지 | O | O | O | O | O | O |
| 16_award-03 | 트러블 | I 수상·부문명 | 유지 | O | O | O | O | O | O |
| 16_award-04 | 재생 | I 수상·부문명 | 유지 | O | O | O | O | O | O |
| 16_award-05 | 모공 축소 | I 수상·부문명 | 유지 | O | O | O | O | O | O |
| 17_strong_claim-01 | 미백 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-01 | 주름 개선 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-02 | 안티에이징 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-03 | 즉각 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-03 | 모공 축소 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-04 | 재생 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-04 | 트러블 | J 강한 주장 | 치환 | O | O | O | O | O | O |
| 17_strong_claim-05 | 100% | J 강한 주장 | 치환 | O | O | O | O | O | O |

> `O` 정답 · `X` 오답 · `?` **불명(육안 판정 필요)** · `—` **미실행**

### 유형별 정답률

| 유형 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|
| A 부인 문맥 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 |
| A 주장 문맥 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| B 부분일치(재생 주기) | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| B 부분일치(재생력) | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| C 제품명(명시) | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 0/5 |
| C 제품명(암시) | 5/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| D 인용문 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 |
| E 금지어 2개 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| F 조사 결합 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| G 법령·고시 인용 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 3/6 |
| H UI 라벨·카테고리 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| I 수상·부문명 | 5/5 | 5/5 | 5/5 | 4/5 | 4/5 | 5/5 |
| J 강한 주장 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| 대조군 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| 중복 대체표현 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

> `유지` 기대 유형(A 부인 / C 제품명 / D 인용)이 변별의 핵심이다.

### 양립 유형 처리 방침 — 우열이 아니라 **모델 특성**

`양립`은 치환·유지 둘 다 정답으로 인정한 자리다. 어느 쪽을 골랐는지는 점수에 반영하지 않되, **벤더별 방침 차이가 실재하므로 기록한다.**

| 대상 | 치환 | 유지 | 방침 |
|---|---|---|---|
| `v6_principle/gemini` | 8 | 0 | **치환형** |
| `v6_principle/gemini_flash38` | 8 | 0 | **치환형** |
| `v6_principle/claude` | 8 | 0 | **치환형** |
| `v6_principle/gpt_sol` | 1 | 5 | **유지형** |
| `v6_principle/gpt_terra` | 1 | 6 | **유지형** |
| `v6_principle/qwen_plus` | 0 | 8 | **유지형** |

> `치환형` — UI 라벨·카테고리도 규제 적용 대상으로 본다
> `유지형` — 분류 체계이므로 바꾸지 않는다
> **팀이 규제 표의 적용 범위를 정하면 어느 쪽이 맞는지 결정된다**(PLAN.md 3-4).

## 5. 세그먼트별 대조

### 01_intro

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 루미에르 콜라겐 앰플 | Lumiere Collagen Ampoule | Lumiere Collagen Ampoule | Lumière Collagen Ampoule _('루미에르' rendered as the brand's French-style spelling Lumière; brand name kept untranslated)_ | 루미에르 콜라겐 앰플 | 루미에르 Collagen Ampoule | Lumiere Collagen Ampoule |
| 02 | 지금 시작하는 탄력 루틴 | Start your firming routine now | Start your firmness routine now | Your bounce routine starts now | Start Your Firming Routine Now | Start Your Firming Routine Today _(‘탄력’ rendered as “firming” without applying the regulatory mapping, as this is a routine name/tagline rather than a direct efficacy claim.)_ | Start Your Firmness Routine |
| 03 | 매일 한 방울, 가볍게 쌓아가는 하루 | One light drop a day, building up your routine | One drop a day, effortlessly layered | One drop a day, layered lightly | One Drop a Day, Layered Lightly | One Drop a Day, Building Lightly Over Time | One Drop a Day, Gently Building Up |
| 04 | 속부터 채우는 저분자 콜라겐 | Low-molecular collagen filling from within | Low-molecular collagen replenishing from deep within | Low-molecular collagen that fills from within | Low-Molecular-Weight Collagen That Replenishes from Within | Low-Molecular Collagen That Fills from Within | Low-Molecular Collagen from Within |
| 05 | 피부가 달라지는 시간 | Time for your skin to transform | The moment your skin transforms | Time for your skin to change | Time for Your Skin to Transform | Time for Skin That Feels Different | Time for Your Skin to Transform |
| 06 | 민감한 피부도 편안하게 | Comforting even for sensitive skin | Comforting even for sensitive skin | Comfortable even for sensitive skin | Comfortable Even for Sensitive Skin | Comfortable Even for Sensitive Skin | Soothing Even Sensitive Skin |
| 07 | 데일리 앰플 30ml | Daily Ampoule 30ml | Daily Ampoule 30ml | Daily Ampoule 30ml | Daily Ampoule 30 mL | Daily Ampoule 30 mL | Daily Ampoule 30ml |
| 08 | 신제품 출시 기념 | New launch celebration | New Launch Special | Celebrating our new launch | Celebrating Our New Launch | Celebrating Our New Product Launch | New Release |

### 02_benefit

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 미백 기능성 화장품 | Brightening functional cosmetic _(규제 매핑 적용: '미백'을 'Brightening'으로 대체)_ | Brightening functional cosmetic _(규제 매핑 표 적용: '미백' → 'brightening')_ | Brightening functional cosmetic | Brightening Functional Cosmetic _(Replaced “미백” with “brightening” per regulatory mapping.)_ | Brightening functional cosmetic | Brightening Functional Cosmetics _(Regulatory mapping applied: 미백 -> brightening)_ |
| 02 | 탄력 케어에 도움을 주는 이중 기능성 | Dual-functional for elasticity care | Dual-functional care to support elasticity | Dual-function care that supports firmness | Dual-functional care that supports elasticity | Dual-function formula that helps support firmness care | Dual functionality for firming care |
| 03 | 지친 피부의 재생을 돕습니다 | Helps with renewing tired skin _(규제 매핑 적용: '재생'을 'renewing'으로 대체)_ | Helps renew tired skin _(규제 매핑 표 적용: '재생' → 'renewing')_ | Helps renew tired-looking skin | Helps renew tired-looking skin _(Replaced “재생” with “renew” per regulatory mapping.)_ | Helps renew tired-looking skin | Helps renew tired skin _(Regulatory mapping applied: 재생 -> renewing)_ |
| 04 | 즉각 차오르는 수분감 | Fast-acting plumping moisture _(규제 매핑 적용: '즉각'을 'fast-acting'으로 대체)_ | Fast-acting surge of moisture _(규제 매핑 표 적용: '즉각' → 'fast-acting')_ | Fast-acting surge of moisture | Fast-acting hydration boost _(Replaced “즉각” with “fast-acting” per regulatory mapping.)_ | Fast-acting burst of hydration | Fast-acting surging hydration _(Regulatory mapping applied: 즉각 -> fast-acting)_ |
| 05 | 데일리 케어의 시작 | The start of daily care | The beginning of daily care | The start of daily care | The start of daily care | The start of daily care | Start your daily care |
| 06 | 칙칙한 피부톤을 환하게 | Brightens dull skin tone | Brightens dull skin tone | Brightens a dull-looking complexion | Brightens dull-looking skin | For a brighter-looking dull skin tone | Brightens dull skin tone |
| 07 | 탄력 없이 처진 피부에 | For sagging skin lacking elasticity | For sagging skin lacking elasticity | For skin that looks loose and lax | For sagging skin lacking firmness | For skin lacking firmness and looking saggy | For sagging skin lacking firmness |
| 08 | 건조함으로 인한 각질까지 | Even flakiness caused by dryness | Even flakiness caused by dryness | Even dryness-related flakiness | Even dryness-induced flakiness | Even dry-skin flakes caused by dryness | Even flakiness from dryness |
| 09 | 모공 하나하나 채우는 밀착 텍스처 | Adhering texture that fills every pore | A seamless texture that fills every pore | Close-fitting texture that fills every pore | Close-fitting texture that smooths over every pore | A close-adhering texture that fills every pore | Skin-hugging texture that fills every pore |
| 10 | 사용 4주 후 만족도 92%* | 92% satisfaction after 4 weeks of use* | 92% satisfaction after 4 weeks of use* | 92% satisfaction after 4 weeks of use* | 92% satisfaction after 4 weeks of use* | 92% satisfaction after 4 weeks of use* | 92% satisfaction after 4 weeks of use* |

### 03_ingredient

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 핵심 성분 3종 | 3 key ingredients | 3 Key Ingredients | 3 Key Ingredients | 3 Key Ingredients | 3 Key Ingredients | 3 Key Ingredients |
| 02 | 가수분해 콜라겐 | Hydrolyzed Collagen | Hydrolyzed Collagen | Hydrolyzed Collagen | Hydrolyzed Collagen | Hydrolyzed Collagen | Hydrolyzed Collagen |
| 03 | 나이아신아마이드 2% 함유 | Contains 2% Niacinamide | Contains 2% Niacinamide | 2% Niacinamide | Contains 2% Niacinamide | Contains 2% Niacinamide | Contains 2% Niacinamide |
| 04 | 아데노신 0.04% 함유 | Contains 0.04% Adenosine | Contains 0.04% Adenosine | 0.04% Adenosine | Contains 0.04% Adenosine | Contains 0.04% Adenosine | Contains 0.04% Adenosine |
| 05 | 히알루론산 5종 복합체 | 5-Hyaluronic Acid Complex | 5-Type Hyaluronic Acid Complex | 5-Type Hyaluronic Acid Complex | 5-Type Hyaluronic Acid Complex | 5-Type Hyaluronic Acid Complex | 5-Type Hyaluronic Acid Complex |
| 06 | 판테놀과 세라마이드로 보습막 형성 | Forms a moisture barrier with Panthenol and Ceramide | Moisture barrier formulated with Panthenol and Ceramide | Panthenol & ceramides form a moisture barrier | Forms a moisture barrier with panthenol and ceramides | Moisture barrier with Panthenol and Ceramides | Moisture Barrier with Panthenol & Ceramide |
| 07 | 병풀추출물(센텔라아시아티카)로 진정 | Soothing with Centella Asiatica Extract | Soothes with Centella Asiatica Extract | Soothing Centella Asiatica extract | Soothes with Centella Asiatica Extract | Soothing with Centella Asiatica Extract _(병풀추출물의 통용 성분명인 Centella Asiatica Extract로 옮김.)_ | Soothing with Centella Asiatica Extract |
| 08 | 여드름 완화에 도움을 주는 성분 배합 | Formulated with ingredients for blemish-prone skin _('여드름 완화'를 규제 매핑 표에 따라 'for blemish-prone skin'으로 대체함)_ | Ingredient blend for blemish-prone skin _(규제 매핑 적용: '여드름 완화'를 'for blemish-prone skin'으로 대체)_ | Ingredient blend for blemish-prone skin _('여드름 완화' replaced with 'for blemish-prone skin' per regulatory mapping)_ | Ingredient blend for blemish-prone skin _(Replaced the acne-relief claim with “for blemish-prone skin” per the regulatory mapping.)_ | Ingredient blend for blemish-prone skin _(브랜드 효능 주장 내 '여드름 완화'를 규제 매핑에 따라 대체.)_ | Formulated for Blemish-Prone Skin _(여드름 완화 → for blemish-prone skin (규제 매핑 적용))_ |
| 09 | 무향료 무색소 처방 | Fragrance-free and colorant-free formula | Fragrance-free and artificial color-free formula | Fragrance-free, colorant-free formula | Fragrance-Free, Colorant-Free Formula | Fragrance-Free, Colorant-Free Formula | Fragrance-Free, Colorant-Free Formula |
| 10 | 전 성분은 제품 용기 및 단상자에 표기 | Full ingredients are listed on the product container and carton | Full ingredient list is marked on the container and packaging box | Full ingredient list on the bottle and carton | Full ingredients listed on the container and carton | Full ingredient list on product container and carton | Full Ingredient List on Container & Box |

### 04_safety

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 피부 저자극 테스트 완료 | Skin irritation test completed | Skin Irritation Test Completed | Low-irritation skin test passed | Skin Irritation Test Completed | Skin irritation test completed | Hypoallergenic Test Completed |
| 02 | 알레르기 유발 성분 25종 무첨가 | Free of 25 allergenic ingredients | Free of 25 Common Allergens | Free of 25 known allergens | Formulated Without 25 Allergenic Ingredients | Free from 25 allergy-inducing ingredients | Free of 25 Allergens |
| 03 | 식약처 고시 기준 준수 | Complies with MFDS standards | Complies with MFDS Standards | Meets MFDS (Korea) standards _(식약처 = Ministry of Food and Drug Safety)_ | Complies with MFDS Standards | Meets MFDS notice standards _(MFDS rendered as the Ministry of Food and Drug Safety.)_ | Complies with MFDS Standards |
| 04 | 비건 인증 획득 | Certified vegan | Certified Vegan | Vegan certified | Vegan Certified | Vegan certified | Certified Vegan |
| 05 | 동물실험 미실시 | No animal testing | Cruelty-Free (No Animal Testing) | Never tested on animals | Not Tested on Animals | Not tested on animals | Cruelty-Free |
| 06 | 부작용 없음이 확인된 순한 처방 | Proven gentle formula _(규제 매핑('부작용 없음' -> 'gentle formula') 적용 후 중복을 피해 자연스럽게 다듬음)_ | Verified gentle formula for mild care _(규제 매핑 적용: '부작용 없음' → 'gentle formula')_ | A verified gentle formula _('부작용 없음' replaced with 'gentle formula' per regulatory mapping)_ | Verified Gentle Formula _(Replaced “confirmed no side effects” with “gentle formula” per the regulatory mapping.)_ | Confirmed gentle formula _(Replaced 'no side effects' with 'gentle formula' per regulatory mapping.)_ | Clinically Proven Gentle Formula |
| 07 | 민감성 피부 대상 임상 시험 완료 | Clinically tested on sensitive skin | Clinically Tested on Sensitive Skin | Clinically tested on sensitive skin | Clinical Testing on Sensitive Skin Completed | Clinical test completed on sensitive skin | Clinically Tested on Sensitive Skin |
| 08 | *피부과 전문의 감독 하 인체적용시험, 성인 여성 32명, 4주 | *Clinical test under dermatologist supervision, 32 adult women, 4 weeks | *Clinical test conducted under dermatological supervision, 32 adult females, 4 weeks | *Human application test under dermatologist supervision, 32 adult women, 4 weeks | *Human study under dermatologist supervision; 32 adult women; 4 weeks | *Human application test supervised by a dermatologist, 32 adult women, 4 weeks | *Human Application Test Under Dermatologist Supervision, 32 Adult Women, 4 Weeks |

### 05_howto

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 사용 방법 | How to Use | How to Use | How to Use | How to Use | How to Use | How to Use |
| 02 | 세안 후 토너로 피부결을 정돈합니다 | Refine skin texture with toner after cleansing. | After cleansing, prep skin texture with toner. | After cleansing, smooth skin's texture with toner | After cleansing, prep skin with toner | After cleansing, refine skin texture with toner. | After cleansing, prep skin with toner |
| 03 | 앰플을 2~3방울 덜어 얼굴 전체에 펴 바릅니다 | Apply 2-3 drops of ampoule evenly over the face. | Dispense 2–3 drops of ampoule and smooth evenly across the face. | Dispense 2–3 drops of ampoule and spread over the entire face | Apply 2–3 drops of the ampoule evenly over your face | Apply 2–3 drops of ampoule evenly over the face. | Dispense 2-3 drops and spread evenly across face |
| 04 | 손바닥으로 감싸듯 흡수시켜 주세요 | Gently press with your palms to aid absorption. | Gently press with palms to aid absorption. | Press with palms to help it absorb | Gently press in with your palms to help absorption | Gently press into skin with your palms. | Gently press palms to aid absorption |
| 05 | 아침 저녁 하루 두 번 사용을 권장합니다 | Recommended to use twice a day, morning and evening. | Recommended for use twice daily, morning and night. | Recommended twice daily, morning and night | Use twice daily, morning and evening | Recommended for use twice daily, morning and night. | Recommended twice daily, morning and night |
| 06 | 건조한 부위는 덧발라 주세요 | Apply an extra layer to dry areas. | Reapply an extra layer onto dry areas. | Layer more on dry areas | Apply an extra layer to dry areas | Apply an extra layer to dry areas. | Reapply to dry areas as needed |
| 07 | 크림 단계 전에 사용하면 더욱 좋습니다 | For best results, use before the cream step. | Best applied right before your cream step. | Best used before your cream step | For best results, use before your cream | For best results, use before cream. | Use before applying cream for best results |

### 06_texture

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 산뜻하게 스며드는 워터리 제형 | Refreshing watery texture | Refreshing, fast-absorbing watery texture | A watery texture that sinks in fresh | Fresh, fast-absorbing watery texture | A fresh, watery formula that absorbs effortlessly | Refreshing watery texture that absorbs seamlessly |
| 02 | 끈적임 없이 마무리되는 사용감 | Non-sticky finish | Non-sticky, comfortable finish | Finishes without any sticky feel | A non-sticky finish | A non-sticky finish | Non-sticky, comfortable finish |
| 03 | 메이크업 전에도 부담 없이 | Weightless even under makeup | Effortless wear even before makeup | Light enough to wear before makeup | Lightweight even under makeup | Comfortable even before makeup | Lightweight enough to wear under makeup |
| 04 | 얇게 발리는 밀착력 | Thin, seamless adhesion | Thin, seamless adherence | Spreads thin, hugs the skin | A thin, seamless fit | A thin, skin-hugging application | Adheres seamlessly in a thin layer |
| 05 | 은은한 광채가 남는 마무리 | Subtle glowing finish | Leaves a subtle, luminous glow | Leaves a soft, subtle radiance | A subtle, radiant finish | A finish with a subtle glow | Leaves a subtle, radiant finish |

### 07_promo

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 단독 한정 기획 | Exclusive Limited Set | Exclusive Limited Edition | Exclusive Limited Edition | Exclusive Limited-Edition Set | Exclusive Limited Offer | Exclusive Limited Offer |
| 02 | 1+1 더블 기획 | 1+1 Double Set | 1+1 Double Set | 1+1 Double Set | Buy 1, Get 1 Double Set | Buy 1, Get 1 Double Offer | 1+1 Double Offer |
| 03 | 선착순 3,000명 | First 3,000 customers | First 3,000 Customers | First 3,000 Customers | First 3,000 Customers Only | First 3,000 Customers | First 3,000 Buyers |
| 04 | 구매 시 미니어처 10ml 증정 | Free 10ml miniature with purchase | Free 10ml Miniature with Purchase | Free 10ml Miniature with Purchase | Free 10 mL Miniature with Purchase | Receive a 10 mL Miniature with Purchase | Free 10ml Mini with Purchase |
| 05 | 리뷰 작성 시 적립금 3,000원 | Earn 3,000 reward points for writing a review | 3,000 Reward Points for Review | 3,000 KRW Points for Your Review _(적립금은 자사몰 포인트로 보아 'points'로 옮기고 통화 단위를 KRW로 명시)_ | Earn 3,000 Won in Points for a Review | Receive 3,000 Reward Points for Writing a Review | 3,000 Points for Review |
| 06 | 증정 기간: 8월 19일 ~ 8월 23일 (재고 소진 시 조기 종료) | Promo period: Aug 19 - Aug 23 (While supplies last) | Promo Period: Aug 19 – Aug 23 (While Supplies Last) | Gift Period: Aug 19 – Aug 23 (ends early while supplies last) | Gift Period: Aug. 19–23 (May End Early While Supplies Last) | Gift Period: Aug 19–Aug 23 (Ends Early When Supplies Run Out) | Offer Period: Aug 19-23 (Ends early when stock runs out) |
| 07 | 온라인몰 스킨케어 부문 판매 1위* | No. 1 in Online Mall Skincare Sales* | #1 Best Seller in Skincare on Online Store* | No.1 in Online Skincare Sales* | No. 1 in Online Skincare Sales* | No. 1 in Online Mall Skincare Sales* | #1 Skincare Sales Online* |
| 08 | *2026년 6월 자사몰 기준 | *Based on official mall data, June 2026 | *Based on official brand store sales, June 2026 | *Based on our own online store, June 2026 | *Based on the Brand’s Official Online Store, June 2026 | *Based on the brand's online store, June 2026 | *Based on our official store, Jun 2026 |

### 08_notice

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 사용상의 주의사항 | Cautions for Use | Precautions for Use | Precautions for Use | Precautions for Use | Precautions for Use | Precautions for Use |
| 02 | 상처가 있는 부위에는 사용을 피해 주세요 | Avoid using on wounded areas. | Avoid using on areas with wounds. | Avoid applying to wounded or broken skin. | Do not use on wounded areas. | Avoid use on wounded areas. | Avoid use on wounded skin. |
| 03 | 사용 중 붉은 반점, 부어오름, 가려움 등의 이상이 있는 경우 사용을 중지하고 전문의와 상담하십시오 | Stop using and consult a specialist if you experience red spots, swelling, or itchiness. | If abnormal symptoms such as red spots, swelling, or itching occur during use, discontinue use and consult a specialist. | If redness, swelling, itching or other irritation occurs, stop use and consult a specialist. | If redness, swelling, itching, or other irritation occurs during use, discontinue use and consult a doctor. | If redness, swelling, itching, or other abnormalities occur during use, discontinue use and consult a specialist. | If redness, swelling, or itching occurs during use, discontinue use and consult a specialist. |
| 04 | 직사광선을 피해 서늘한 곳에 보관하십시오 | Store in a cool place away from direct sunlight. | Store in a cool place away from direct sunlight. | Store in a cool place away from direct sunlight. | Store in a cool place away from direct sunlight. | Store in a cool place away from direct sunlight. | Store in a cool place away from direct sunlight. |
| 05 | 어린이의 손이 닿지 않는 곳에 보관하십시오 | Keep out of reach of children. | Keep out of reach of children. | Keep out of reach of children. | Keep out of reach of children. | Keep out of reach of children. | Keep out of reach of children. |
| 06 | 본 제품은 의약품이 아니므로 질환의 치료를 목적으로 사용할 수 없습니다 | This product is not a medicine and cannot be used for the treatment of diseases. _('치료'는 효능을 부인하는 주의사항 문맥이므로 규제 매핑을 적용하지 않고 원뜻을 살려 'treatment'로 번역함)_ | This product is not a medical drug and cannot be used for the treatment of diseases. _(의약품 오인 방지 면책 고지문이므로 '치료' 매핑을 적용하지 않고 원문의 법적 고지 의미를 유지함)_ | This product is not a pharmaceutical and must not be used to treat any disease. _(규제 매핑의 '치료 → care'를 적용하지 않았다. 이 문장은 브랜드가 효능을 주장하는 자리가 아니라 의약적 효능을 부인하는 법적 고지이므로, 'care'로 바꾸면 고지 기능과 사실관계가 깨진다.)_ | This product is not a medicine and is not intended to treat any disease. | This product is not a medicine and cannot be used for the care of diseases. | This product is not a medicine and cannot be used for the treatment of diseases. |
| 07 | 개봉 후에는 가능한 빠르게 사용하십시오 | Use as soon as possible after opening. | Use as soon as possible after opening. | Use as soon as possible after opening. | Use as soon as possible after opening. | Use as soon as possible after opening. | Use as soon as possible after opening. |
| 08 | 교환 및 환불은 수령 후 7일 이내 가능합니다 | Exchanges and refunds are available within 7 days of receipt. | Exchanges and refunds are available within 7 days of receipt. | Exchanges and refunds are available within 7 days of delivery. | Exchanges and refunds are available within 7 days of receipt. | Exchanges and refunds are available within 7 days of receipt. | Exchanges and refunds are available within 7 days of receipt. |

### 09_regulation_edge

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 임상 시험에서 미백 효과가 확인되었습니다 | Brightening effect confirmed in clinical trials _(미백 -> brightening 대체 적용)_ | Brightening efficacy confirmed in clinical trials. _(미백 → brightening 대체 적용)_ | Brightening results confirmed in clinical testing _('미백' → 'brightening' (규제 매핑 적용))_ | Clinically proven brightening benefits _(Replaced “미백” with “brightening” per regulatory mapping.)_ | Clinical testing confirmed brightening benefits _(Applied regulatory mapping: 미백 → brightening)_ | Brightening effects confirmed in clinical trials |
| 02 | 주름 개선에 도움을 줍니다 | Helps reduce the look of fine lines _(주름 개선 -> helps reduce the look of fine lines 대체 적용)_ | Helps reduce the look of fine lines. _(주름 개선 → helps reduce the look of fine lines 대체 적용)_ | Helps reduce the look of fine lines _('주름 개선' → 매핑 표현 적용)_ | Helps reduce the look of fine lines _(Replaced “주름 개선” with the required regulatory wording.)_ | Helps reduce the look of fine lines _(Applied regulatory mapping: 주름 개선 → helps reduce the look of fine lines)_ | Helps reduce the look of fine lines |
| 03 | 재생력이 떨어진 피부를 위한 집중 케어 | Intensive care for skin lacking renewing power _(재생 -> renewing 대체 적용)_ | Intensive care for skin with diminished renewing power. _(재생 → renewing 대체 적용)_ | Intensive care for skin with diminished renewing power _('재생' → 'renewing' 적용)_ | Intensive care for skin with reduced renewing power _(Replaced “재생” with “renewing” per regulatory mapping.)_ | Intensive care for skin with diminished renewing power _(Applied regulatory mapping: 재생 → renewing)_ | Intensive care for skin with diminished renewing ability |
| 04 | 피부 재생 주기에 맞춘 4주 루틴 | A 4-week routine tailored to the skin renewing cycle _(재생 -> renewing 대체 적용)_ | A 4-week routine tailored to the skin's renewing cycle. _(재생 → renewing 대체 적용)_ | A 4-week routine timed to skin's renewing cycle _('재생' → 'renewing' 적용)_ | A 4-week routine aligned with the skin renewal cycle | A 4-week routine tailored to the skin’s renewing cycle _(Applied regulatory mapping: 재생 → renewing)_ | 4-week routine aligned with skin's renewing cycle |
| 05 | 미백과 주름 개선을 동시에 케어하는 이중 기능성 | Dual functionality that provides brightening and helps reduce the look of fine lines simultaneously _(미백 -> brightening, 주름 개선 -> helps reduce the look of fine lines 대체 적용 (문맥에 맞게 구문 조정))_ | Dual-functional care that provides brightening and helps reduce the look of fine lines. _(미백 → brightening, 주름 개선 → helps reduce the look of fine lines 대체 적용)_ | Dual function: brightening while helping reduce the look of fine lines _('미백'·'주름 개선' 매핑 적용, 길이 유지 위해 문장 압축)_ | Dual-functional care for brightening and reducing the look of fine lines _(Replaced “미백” and “주름 개선” with the required regulatory wording.)_ | Dual-function care for brightening and the look of fine lines _(Applied regulatory mappings: 미백 → brightening; 주름 개선 → helps reduce the look of fine lines)_ | Dual-function care for brightening and reducing the look of fine lines |
| 06 | 재생을 돕고 탄력 강화에도 기여합니다 | Aids renewing and provides care for a firmer look _(재생 -> renewing, 탄력 강화 -> for a firmer look 대체 적용)_ | Supports skin renewing and contributes to achieving a firmer look. _(재생 → renewing, 탄력 강화 → for a firmer look 대체 적용)_ | Supports renewing and contributes to a firmer look _('재생'·'탄력 강화' 매핑 적용)_ | Supports renewal and a firmer look _(Replaced “재생” and “탄력 강화” with the required regulatory wording.)_ | Supports renewing and contributes to a firmer look _(Applied regulatory mappings: 재생 → renewing; 탄력 강화 → for a firmer look)_ | Helps with renewing and contributes to a firmer look |
| 07 | 노화 방지와 안티에이징을 한 번에 | Double age-defying benefits at once _(노화 방지, 안티에이징 모두 age-defying으로 대체 적용됨에 따라, 중복 표기를 피하고 자연스럽게 의역함)_ | Complete age-defying care all at once. _('노화 방지'와 '안티에이징'이 모두 'age-defying'으로 매핑되어 중복을 피해 단일 age-defying 표현으로 통합)_ | Age-defying care, all in one _('노화 방지'와 '안티에이징' 모두 'age-defying'으로 매핑되어 중복되므로 한 번만 표기하고 '한 번에'를 'all in one'으로 살림)_ | Age-defying and age-defying care in one _(Both “노화 방지” and “안티에이징” were replaced with “age-defying” per regulatory mapping.)_ | Two age-defying benefits in one _(Applied regulatory mappings: 노화 방지 → age-defying; 안티에이징 → age-defying)_ | Age-defying and age-defying, all at once _(Both 노화 방지 and 안티에이징 mapped to age-defying per regulation table; source redundancy preserved)_ |

### 10_longform

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 매일 반복되는 자극과 건조함으로 지친 피부에, 저분자 콜라겐과 히알루론산이 층층이 스며들어 속부터 편안하게 채워 줍니다 | For skin exhausted by daily irritation and dryness, low-molecular-weight collagen and hyaluronic acid absorb layer by layer to comfortably plump from within. | For skin fatigued by daily irritation and dryness, low molecular weight collagen and hyaluronic acid absorb layer by layer to comfortably replenish from deep within. | For skin worn down by daily irritation and dryness, low-molecular collagen and hyaluronic acid sink in layer by layer, comfortably replenishing it from within. | For skin tired from daily irritation and dryness, low-molecular-weight collagen and hyaluronic acid absorb layer by layer, leaving it comfortably hydrated from within. | For skin tired from daily irritation and dryness, low-molecular collagen and hyaluronic acid absorb layer by layer, replenishing moisture from within for lasting comfort. | For skin tired from daily irritation and dryness, low-molecular-weight collagen and hyaluronic acid penetrate layer by layer to comfort and fill from within. |
| 02 | 세안 직후 물기가 남아 있을 때 사용하면 유효 성분이 더 깊이 자리 잡아 하루 종일 촉촉함이 이어집니다 | When applied right after cleansing on damp skin, active ingredients settle deeper to maintain moisture all day long. | When used on damp skin right after cleansing, active ingredients settle deeper to lock in all-day hydration. | Apply while skin is still damp right after cleansing so the active ingredients settle in more deeply, keeping skin moisturized all day. | Apply while skin is still damp after cleansing to help beneficial ingredients absorb more deeply and keep skin moisturized all day. | Apply while skin is still damp right after cleansing to help active ingredients absorb more deeply and keep skin hydrated all day. | Apply right after cleansing while skin is still damp so active ingredients absorb deeper for all-day moisture. |
| 03 | 끈적임 없이 산뜻하게 마무리되면서도 속당김은 잡아 주어, 메이크업 전 단계로도 부담 없이 쓸 수 있습니다 | It leaves a fresh, non-sticky finish while relieving inner dryness, making it perfect for use before makeup. | Delivering a fresh, non-sticky finish while relieving inner tightness, it effortlessly preps skin before makeup. | It finishes fresh without stickiness while easing that tight feeling, so it layers easily as a pre-makeup step. | It leaves a fresh, non-sticky finish while easing inner tightness, making it ideal before makeup. | Leaves a fresh, non-sticky finish while relieving inner dryness, making it easy to use before makeup. | Finishes fresh without stickiness while relieving inner tightness, making it perfect for use before makeup. |
| 04 | 화잘먹 피부를 만드는 쫀쫀한 밀착 텍스처 | A bouncy, skin-hugging texture that creates makeup-ready skin. | A bouncy, close-fitting texture for perfectly makeup-ready skin. | A supple, close-hugging texture for skin that makes makeup sit beautifully _('화잘먹' is slang for '화장이 잘 먹는' (makeup applies well); rendered as makeup sitting beautifully.)_ | A bouncy, skin-hugging texture that helps makeup apply beautifully | A bouncy, skin-hugging texture for makeup-ready skin _(Interpreted “화잘먹” as the Korean shorthand for skin that helps makeup apply and wear well.)_ | A bouncy, skin-hugging texture for a flawless makeup base. |
| 05 | 겉은 산뜻, 속은 촉촉하게 채우는 이중 보습 설계 | A dual hydration design that keeps the surface fresh and the inside deeply moisturized. | A dual-layer moisture design that stays fresh on the surface while deeply hydrating within. | Dual moisture design: fresh on the surface, deeply hydrated within | Dual-layer hydration: fresh on the surface, moisturized within | Dual moisturizing design: fresh on the outside, deeply hydrated within | Dual-hydration formula that feels fresh on the outside and deeply moisturizing on the inside. |
| 06 | 환절기마다 뒤집어지는 예민한 피부에도 순하게 스며듭니다 | It gently absorbs even into sensitive skin that acts up during changing seasons. | Absorbs gently, even into sensitive skin that easily flares up during seasonal changes. | It sinks in gently, even on sensitive skin that flares up each change of season. | Gently absorbs even into sensitive skin that acts up with seasonal changes. | Gently absorbs even into sensitive skin prone to seasonal flare-ups. | Gently absorbs even into sensitive skin that flares up with changing seasons. |
| 07 | 바르는 순간 피부 위에 얇은 보습막이 형성되어 수분이 날아가는 것을 막아 줍니다 | Upon application, a thin moisture barrier forms on the skin to prevent moisture loss. | Upon application, a thin moisture barrier instantly forms to lock in hydration and prevent moisture loss. | The moment it's applied, a thin moisture veil forms on the skin to help prevent water from escaping. | Upon application, it forms a thin moisture barrier to help prevent moisture loss. | Upon application, a thin moisture barrier forms on the skin to help prevent moisture loss. | Forms a thin moisture barrier upon application to prevent moisture loss. |
| 08 | 본 제품에 사용된 병풀추출물은 마다가스카르산 원료를 저온 추출 방식으로 정제하여 유효 성분의 손실을 최소화했습니다 | The Centella Asiatica Extract in this product is refined from Madagascan ingredients via a low-temperature extraction method to minimize the loss of active ingredients. | The Centella Asiatica Extract in this formula is purified from Madagascar-sourced botanicals via low-temperature extraction to minimize the loss of active nutrients. | The Centella Asiatica extract used in this product is refined from Madagascar-sourced material via low-temperature extraction, minimizing loss of active ingredients. | The Centella Asiatica Extract in this product is refined from Madagascar-sourced material using low-temperature extraction to minimize the loss of beneficial components. | The Centella asiatica extract used in this product is refined from Madagascar-sourced ingredients through low-temperature extraction to minimize the loss of active components. | The Centella Asiatica Extract used in this product is refined from Madagascar-sourced ingredients via low-temperature extraction to minimize the loss of active ingredients. |
| 09 | 사용 전 손등 안쪽에 소량을 발라 이상 반응이 없는지 확인한 뒤 얼굴에 사용하시기를 권장합니다 | We recommend applying a small amount to your inner wrist to check for adverse reactions before applying it to your face. _('손등 안쪽'은 뷰티 제품 패치 테스트의 문맥상 'inner wrist(손목 안쪽)'를 의미하는 것으로 추정하여 번역함.)_ | Before use, we recommend applying a small amount to the inner back of your hand to test for sensitivity before applying to the face. | Before use, we recommend applying a small amount to the inner back of the hand to check for any adverse reaction before applying to the face. | Before use, apply a small amount to the inner hand and check for any adverse reaction before applying to the face. | Before use, apply a small amount to the inner back of your hand to check for any adverse reaction before applying to the face. | We recommend applying a small amount to your inner wrist before use to check for any adverse reactions before applying to your face. |
| 10 | 본 광고 문구는 개인의 사용 경험을 바탕으로 작성되었으며 모든 사용자에게 동일한 결과를 보장하지 않습니다 | This copy is based on personal experiences and does not guarantee the same results for all users. | This copy is based on individual user experiences and does not guarantee identical results for all users. | This advertising copy is based on individual user experience and does not guarantee the same results for all users. | These advertising claims are based on individual user experiences and do not guarantee the same results for everyone. | This advertising copy is based on individual user experiences and does not guarantee the same results for all users. | This advertising copy is based on personal usage experience and does not guarantee the same results for all users. |

### 11_denial

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 본 제품은 미백 효과를 보장하지 않으며 개인차가 있을 수 있습니다 | This product does not guarantee whitening effects, and individual results may vary. _(고지(효능 부인) 문장이므로 '미백' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | This product does not guarantee whitening effects, and individual results may vary. | This product does not guarantee any whitening effect, and results may vary by individual. _(효능을 부인하는 고지 문장이므로 규제 매핑(미백→brightening)을 적용하지 않고 원문 의미대로 옮김.)_ | This product does not guarantee whitening effects; results may vary. | This product does not guarantee whitening effects, and results may vary by individual. | This product does not guarantee whitening effects; results may vary. |
| 02 | 주름 개선 효과는 의학적으로 입증된 바 없습니다 | Wrinkle improvement effects have not been medically proven. _(고지 문장이므로 '주름 개선', '의학적' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | Wrinkle improvement effects have not been medically proven. | Wrinkle-improving effects have not been medically proven. _(효능 부인 고지문이므로 '주름 개선', '의학적' 대체 표현을 적용하지 않음. 적용 시 부인 대상이 달라져 고지 기능이 깨짐.)_ | Wrinkle-reducing effects have not been medically proven. | Wrinkle-improving effects have not been medically proven. | Wrinkle improvement effects are not medically proven. |
| 03 | 여드름 완화를 표방하지 않으며 질환이 있는 경우 전문의와 상담하십시오 | It does not claim acne relief; please consult a specialist if you have a medical condition. _(고지 문장이므로 '여드름 완화' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | This product does not claim acne relief; please consult a specialist if you have a medical condition. | This product does not claim to relieve acne; if you have a skin condition, please consult a specialist. _(효능 주장을 부인하는 문장이므로 '여드름 완화' 대체 표현 미적용.)_ | This product does not claim to relieve acne. Consult a healthcare professional if you have a medical condition. | This product does not claim to relieve acne. Consult a specialist if you have a skin condition. | Does not claim to relieve acne; consult a specialist if you have a skin condition. |
| 04 | 부작용 없음을 단정할 수 없으므로 이상 반응 시 사용을 중지하십시오 | We cannot guarantee no side effects; please stop use if abnormal reactions occur. _(고지 문장이므로 '부작용 없음' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | The absence of side effects cannot be guaranteed; discontinue use if any adverse reactions occur. | We cannot guarantee the absence of side effects; discontinue use if any adverse reaction occurs. _(안전성 단정을 부인하는 문장이므로 '부작용 없음' 대체 표현 미적용.)_ | This product cannot be guaranteed free of side effects. Discontinue use if adverse reactions occur. | As the absence of side effects cannot be guaranteed, discontinue use if adverse reactions occur. | Cannot guarantee no side effects; discontinue use if adverse reactions occur. |
| 05 | 모공 축소와 같은 물리적 변화는 확인된 바 없습니다 | Physical changes such as pore reduction have not been confirmed. _(고지 문장이므로 '모공 축소' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | Physical changes such as pore reduction have not been confirmed. | Physical changes such as pore reduction have not been confirmed. _(효과 부인 고지문이므로 '모공 축소' 대체 표현 미적용.)_ | Physical changes such as pore reduction have not been confirmed. | Physical changes such as pore reduction have not been confirmed. | Physical changes such as pore reduction have not been verified. |
| 06 | 본 제품은 기미 치료를 목적으로 하지 않습니다 | This product is not intended for the treatment of melasma. _(고지 문장이므로 '기미', '치료' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | This product is not intended for the treatment of melasma. | This product is not intended to treat dark spots. _(목적을 부인하는 문장이므로 '기미', '치료' 대체 표현 미적용.)_ | This product is not intended to treat melasma. | This product is not intended to treat melasma. | This product is not intended for melasma treatment. |
| 07 | 안티에이징 효과를 보장하는 표현이 아니며 사용감에 대한 설명입니다 | This does not guarantee anti-aging effects but describes the feel of use. _(고지 문장이므로 '안티에이징' 규제 매핑을 적용하지 않고 원뜻 그대로 번역함)_ | This expression does not guarantee anti-aging effects and describes only the feel of use. | This is not a claim guaranteeing anti-aging effects, but a description of how the product feels. _(효능 보장을 부인하는 문장이므로 '안티에이징' 대체 표현 미적용.)_ | This is not a claim guaranteeing anti-aging effects, but a description of how the product feels. | This is not a guarantee of anti-aging effects, but a description of the product feel. | Not a guarantee of anti-aging effects; describes texture and feel. |

### 12_product_name

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 루미에르 미백 앰플 30ml (제품명) | Lumiere Whitening Ampoule 30ml (Product name) _(제품명(고유 대상)이므로 지칭 대상이 달라지는 것을 막기 위해 규제 매핑(brightening)을 적용하지 않고 원뜻대로 번역함)_ | 루미에르 미백 앰플 30ml (Product Name) _(지침 3(브랜드명·제품명 원표기 유지)에 따라 제품명은 번역하지 않고 원표기를 유지함.)_ | 루미에르 미백 앰플 30ml (product name) _(제품명은 제품을 특정하는 식별자이므로 규제 매핑을 적용하지 않고 원표기 유지(규칙 3). 표기를 바꾸면 다른 SKU를 가리키게 됨.)_ | 루미에르 미백 앰플 30ml (Product Name) | 루미에르 미백 앰플 30ml (제품명) _(Product name retained in original notation.)_ | Lumière Brightening Ampoule 30ml (Product Name) |
| 02 | 루미에르 안티에이징 크림 50ml (제품명) | Lumiere Anti-aging Cream 50ml (Product name) _(제품명이므로 규제 매핑(age-defying)을 적용하지 않음)_ | 루미에르 안티에이징 크림 50ml (Product Name) _(지침 3(브랜드명·제품명 원표기 유지)에 따라 제품명은 번역하지 않고 원표기를 유지함.)_ | 루미에르 안티에이징 크림 50ml (product name) _(제품명이므로 원표기 유지, 매핑 미적용.)_ | 루미에르 안티에이징 크림 50ml (Product Name) | 루미에르 안티에이징 크림 50ml (제품명) _(Product name retained in original notation.)_ | Lumière Age-Defying Cream 50ml (Product Name) |
| 03 | 루미에르 재생 에센스 (제품명) | Lumiere Regenerating Essence (Product name) _(제품명이므로 규제 매핑(renewing)을 적용하지 않음)_ | 루미에르 재생 에센스 (Product Name) _(지침 3(브랜드명·제품명 원표기 유지)에 따라 제품명은 번역하지 않고 원표기를 유지함.)_ | 루미에르 재생 에센스 (product name) _(제품명이므로 원표기 유지, 매핑 미적용.)_ | 루미에르 재생 에센스 (Product Name) | 루미에르 재생 에센스 (제품명) _(Product name retained in original notation.)_ | Lumière Renewing Essence (Product Name) |
| 04 | 루미에르 트러블 스팟 세럼 15ml (제품명) | Lumiere Trouble Spot Serum 15ml (Product name) _(제품명이므로 규제 매핑(blemish-prone concerns)을 적용하지 않음)_ | 루미에르 트러블 스팟 세럼 15ml (Product Name) _(지침 3(브랜드명·제품명 원표기 유지)에 따라 제품명은 번역하지 않고 원표기를 유지함.)_ | 루미에르 트러블 스팟 세럼 15ml (product name) _(제품명이므로 원표기 유지, 매핑 미적용.)_ | 루미에르 트러블 스팟 세럼 15ml (Product Name) | 루미에르 트러블 스팟 세럼 15ml (제품명) _(Product name retained in original notation.)_ | Lumière Spot Serum for Blemish-Prone Concerns 15ml (Product Name) |
| 05 | 루미에르 100% 오일 (제품명) | Lumiere 100% Oil (Product name) _(제품명이므로 규제 매핑(pure)을 적용하지 않음)_ | 루미에르 100% 오일 (Product Name) _(지침 3(브랜드명·제품명 원표기 유지)에 따라 제품명은 번역하지 않고 원표기를 유지함.)_ | 루미에르 100% 오일 (product name) _(제품명이므로 원표기 유지, 매핑 미적용.)_ | 루미에르 100% 오일 (Product Name) | 루미에르 100% 오일 (제품명) _(Product name retained in original notation.)_ | Lumière Pure Oil (Product Name) |
| 06 | 안티에이징 라인 신제품 출시 | Launch of the new Anti-aging line _(라인명이므로 규제 매핑(age-defying)을 적용하지 않음)_ | New Product Launch: Age-Defying Line _(규제 매핑 표에 따라 '안티에이징'을 'age-defying'으로 대체함.)_ | New age-defying line now available _(브랜드 자체 효능 소구 문구이므로 매핑 적용(안티에이징 → age-defying).)_ | Introducing Our New Age-Defying Line _(Replaced 안티에이징 with age-defying per the regulatory mapping.)_ | New Age-Defying Line Launch _(Replaced '안티에이징' with 'age-defying' per regulatory mapping.)_ | New Launch: Age-Defying Line |
| 07 | 미백 앰플 리필 파우치도 함께 준비했습니다 | Whitening Ampoule refill pouch is also available _(특정 제품(미백 앰플)을 지칭하므로 규제 매핑(brightening)을 적용하지 않음)_ | We've also prepared a refill pouch for the brightening ampoule _(규제 매핑 표에 따라 '미백'을 'brightening'으로 대체함.)_ | A brightening ampoule refill pouch is available too _(매핑 적용(미백 → brightening).)_ | Now Available with a Brightening Ampoule Refill Pouch _(Replaced 미백 with brightening per the regulatory mapping.)_ | Brightening Ampoule Refill Pouches Also Available _(Replaced '미백' with 'brightening' per regulatory mapping.)_ | Brightening Ampoule Refill Pouch Also Available |
| 08 | 재생 크림과 함께 쓰면 더 좋습니다 | Best when used with the Regenerating Cream _(특정 제품(재생 크림)을 지칭하므로 규제 매핑(renewing)을 적용하지 않음)_ | Works even better when used with the renewing cream _(규제 매핑 표에 따라 '재생'을 'renewing'으로 대체함.)_ | Even better paired with the renewing cream _(매핑 적용(재생 → renewing).)_ | Works Even Better with the Renewing Cream _(Replaced 재생 with renewing per the regulatory mapping.)_ | Even Better with Renewing Cream _(Replaced '재생' with 'renewing' per regulatory mapping.)_ | Even Better with Renewing Cream |
| 09 | 트러블 라인 전 품목 10% 할인 | 10% off all Trouble line products _(라인명이므로 규제 매핑(blemish-prone concerns)을 적용하지 않음)_ | 10% off all items in the blemish-prone concerns line _(규제 매핑 표에 따라 '트러블'을 'blemish-prone concerns'로 대체함.)_ | 10% off the entire line for blemish-prone concerns _(매핑 적용(트러블 → blemish-prone concerns).)_ | 10% Off the Entire Blemish-Prone Concerns Line _(Replaced 트러블 with blemish-prone concerns per the regulatory mapping.)_ | 10% Off All Blemish-Prone Concerns Line Products _(Replaced '트러블' with 'blemish-prone concerns' per regulatory mapping.)_ | 10% Off All Blemish-Prone Concerns Line |
| 10 | 탄력 강화 세럼은 별매입니다 | Firming Serum is sold separately _(특정 제품(탄력 강화 세럼)을 지칭하므로 규제 매핑(for a firmer look)을 적용하지 않음)_ | Serum for a firmer look is sold separately _(규제 매핑 표에 따라 '탄력 강화'를 'for a firmer look'으로 대체함.)_ | The serum for a firmer look is sold separately _(매핑 적용(탄력 강화 → for a firmer look).)_ | Serum for a Firmer Look Sold Separately _(Replaced 탄력 강화 with for a firmer look per the regulatory mapping.)_ | Serum for a Firmer Look Sold Separately _(Replaced '탄력 강화' with 'for a firmer look' per regulatory mapping.)_ | Serum for a Firmer Look Sold Separately |

### 13_quote

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 고객 후기: "기미가 옅어진 것 같아요" (사용자 개인 의견) | Customer Review: "I think my dark spots have faded" (Individual user opinion) _(제3자(고객)의 발화이므로 규제 매핑(기미 -> uneven-looking areas)을 적용하지 않고 원문 의미 유지)_ | Customer Review: "I feel like my dark spots have faded" (Individual user opinion) | Customer review: "My dark spots seem to have faded" (individual user opinion) _(제3자 후기 인용이므로 규제 매핑('기미'→uneven-looking areas)을 적용하지 않고 원문 발화를 그대로 옮김)_ | Customer Review: “I think my dark spots have faded.” (Individual user opinion) | Customer review: "I think my dark spots have faded." (Personal user opinion) | Customer review: "I feel like my melasma has faded." (Personal opinion) |
| 02 | 피부과 전문의 인터뷰 중: "이 성분은 치료 목적이 아닙니다" | Dermatologist Interview: "This ingredient is not for treatment purposes" _(효능을 부인하는 문장이므로 규제 매핑(치료 -> care)을 적용하지 않고 원문 의미(고지 기능) 유지)_ | From a Dermatologist Interview: "This ingredient is not intended for therapeutic purposes" | From a dermatologist interview: "This ingredient is not intended for treatment" _(효능을 부인하는 고지성 발화이므로 '치료'를 care로 대체하지 않고 원뜻을 유지)_ | From a Dermatologist Interview: “This ingredient is not intended for treatment.” | In an interview with a dermatologist: "This ingredient is not intended for treatment." | Dermatologist interview: "This ingredient is not for therapeutic purposes." |
| 03 | 구매자 리뷰: "트러블이 줄어든 느낌이에요" | Buyer Review: "I feel like my breakouts have reduced" _(제3자(구매자)의 발화이므로 규제 매핑(트러블 -> blemish-prone concerns)을 적용하지 않고 원문 의미 유지)_ | Buyer Review: "I feel like my breakouts have lessened" | Buyer review: "It feels like my breakouts have gone down" _(제3자 후기 인용이므로 '트러블' 대체 표현을 적용하지 않음)_ | Buyer Review: “I feel like I’ve had fewer breakouts.” | Buyer review: "I feel like my breakouts have decreased." | Buyer review: "I feel like my breakouts have decreased." |
| 04 | 리뷰 인용: "미백 효과를 기대했는데 보습이 더 좋았어요" | Review Quote: "I expected a whitening effect, but the moisturizing was better" _(제3자(리뷰)의 발화이므로 규제 매핑(미백 -> brightening)을 적용하지 않고 원문 의미 유지)_ | Review Excerpt: "I expected a whitening effect, but the moisturizing was even better" | Review quote: "I expected a brightening effect, but the hydration was even better" _(제3자 후기 인용. 'brightening'은 영어권에서 통용되는 자연스러운 표기로 일치)_ | Review Quote: “I expected a whitening effect, but the hydration was even better.” | Review excerpt: "I expected a whitening effect, but the hydration was even better." | Review excerpt: "I expected a whitening effect, but the hydration was better." |
| 05 | 인터뷰: "주름 개선을 약속드릴 수는 없습니다" | Interview: "We cannot guarantee wrinkle improvement" _(효능을 부인하는 문장이므로 규제 매핑(주름 개선 -> helps reduce the look of fine lines)을 적용하지 않고 원문 의미(고지 기능) 유지)_ | Interview: "We cannot promise wrinkle reduction" | Interview: "We cannot promise wrinkle improvement" _(효능을 부인하는 발화이므로 '주름 개선' 대체 표현을 적용하지 않음)_ | Interview: “We cannot promise wrinkle improvement.” | Interview: "We cannot promise wrinkle improvement." | Interview: "We cannot promise wrinkle improvement." |
| 06 | 사용자 후기: "모공 축소까지는 모르겠지만 결이 좋아졌어요" | User Review: "Not sure about pore reduction, but my skin texture got better" _(제3자(사용자)의 발화이므로 규제 매핑(모공 축소 -> pore-refining appearance)을 적용하지 않고 원문 의미 유지)_ | User Review: "I'm not sure about pore shrinking, but my skin texture improved" | User review: "Not sure about pore shrinking, but my skin texture improved" _(제3자 후기 인용이므로 '모공 축소' 대체 표현을 적용하지 않음)_ | User Review: “I’m not sure about pore reduction, but my skin texture has improved.” | User review: "I’m not sure about pore shrinkage, but my skin texture improved." | Customer review: "I'm not sure about pore minimization, but my skin texture improved." |
| 07 | 전문가 코멘트: "이 제형은 재생을 표방하지 않습니다" | Expert Comment: "This formula does not claim regeneration" _(효능을 부인하는 문장이므로 규제 매핑(재생 -> renewing)을 적용하지 않고 원문 의미(고지 기능) 유지)_ | Expert Comment: "This formula does not claim skin regeneration" | Expert comment: "This formula does not claim to regenerate skin" _(효능 주장을 부인하는 발화이므로 '재생' 대체 표현을 적용하지 않음)_ | Expert Comment: “This formula does not claim to promote regeneration.” | Expert comment: "This formula does not claim to promote regeneration." | Expert comment: "This formula does not claim regenerative effects." |
| 08 | 고객 인터뷰: "즉각 효과를 본 건 아니에요" | Customer Interview: "I didn't see immediate results" _(제3자(고객)의 발화이며 효능을 부인하므로 규제 매핑(즉각 -> fast-acting)을 적용하지 않고 원문 의미 유지)_ | Customer Interview: "I didn't see immediate results" | Customer interview: "It's not like I saw immediate results" _(효과를 부인하는 제3자 발화이므로 '즉각' 대체 표현을 적용하지 않음)_ | Customer Interview: “I didn’t see immediate results.” | Customer interview: "I didn’t see an immediate effect." | Customer interview: "I didn't see immediate results." |
| 09 | 연구원 발언: "의학적 판단은 저희 영역이 아닙니다" | Researcher Statement: "Medical judgment is not our domain" _(의학적 판단을 부인하는 고지이므로 규제 매핑(의학적 -> dermatologist-informed)을 적용하지 않고 원문 의미 유지)_ | Researcher Statement: "Medical diagnosis is beyond our scope" | Researcher statement: "Medical judgment is not our domain" _(의료 영역을 부인하는 발화이므로 '의학적' 대체 표현을 적용하지 않음)_ | Researcher Statement: “Medical judgment is outside our scope.” | Researcher’s comment: "Medical judgment is not within our scope." | Researcher statement: "Medical judgment is not within our scope." |
| 10 | 후기 발췌: "안티에이징 목적으로 산 건 아니었어요" | Review Excerpt: "I didn't buy it for anti-aging purposes" _(제3자(후기)의 발화이므로 규제 매핑(안티에이징 -> age-defying)을 적용하지 않고 원문 의미 유지)_ | Review Excerpt: "I didn't buy it for anti-aging purposes" | Review excerpt: "I didn't buy it for anti-aging purposes" _(구매 목적을 부인하는 제3자 발화이므로 '안티에이징' 대체 표현을 적용하지 않음)_ | Review Excerpt: “I didn’t buy it for anti-aging purposes.” | Review excerpt: "I didn’t buy it for anti-aging purposes." | Review excerpt: "I didn't buy it for anti-aging purposes." |

### 14_legal_ref

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 화장품법 시행규칙의 미백 표시·광고 기준을 따릅니다 | Complies with the whitening labeling and advertising standards under the Enforcement Rule of the Cosmetics Act. _('미백'은 법적 기준을 지칭하므로 규제 매핑을 적용하지 않고 원뜻(whitening)대로 번역함)_ | Complies with the whitening labeling and advertising standards of the Enforcement Rule of the Cosmetics Act. | Complies with the skin-whitening labeling and advertising standards of the Enforcement Rule of the Cosmetics Act _('미백' retained as the statutory functional-cosmetics category name (official MFDS term 'skin whitening'); this is a citation of a legal standard, not a brand efficacy claim, so the mapping table was not applied.)_ | Complies with the whitening labeling and advertising standards under the Enforcement Rule of the Cosmetics Act | Complies with the whitening labeling and advertising standards under the Enforcement Rule of the Cosmetics Act. | Complies with brightening labeling and advertising standards under Enforcement Rules of the Cosmetics Act _(Legal reference to Korean regulatory standards, not a brand efficacy claim. '미백' translated as 'brightening' per standard English rendering of the Korean regulatory category.)_ |
| 02 | 식약처 고시 「기능성화장품 심사에 관한 규정」의 주름 개선 항목에 해당합니다 | Falls under the anti-wrinkle category of the MFDS notification, "Regulation on the Examination of Functional Cosmetics". _('주름 개선'은 고시 항목명이므로 규제 매핑을 적용하지 않고 원뜻(anti-wrinkle)대로 번역함)_ | Corresponds to the wrinkle improvement category under the MFDS Regulation on the Examination of Functional Cosmetics. | Falls under the wrinkle-improvement category of the MFDS Notice "Regulation on Review of Functional Cosmetics" _('주름 개선' retained as the official regulatory category name in a citation of an MFDS notice, not a brand claim.)_ | Falls under the wrinkle improvement category of the MFDS Notice, “Regulations on the Review of Functional Cosmetics” | Falls under the wrinkle improvement category of the MFDS Notification, “Regulations on the Review of Functional Cosmetics.” | Falls under wrinkle improvement category per MFDS 'Regulations on Functional Cosmetics Review' _(Legal reference to a regulatory category name. '주름 개선' rendered as 'wrinkle improvement' (the official category name), not replaced with the mapped claim phrase.)_ |
| 03 | 「화장품 표시·광고 실증에 관한 규정」에 따른 여드름 완화 실증 자료를 보유합니다 | Holds substantiation data for acne relief according to the "Regulation on Substantiation of Cosmetics Labeling and Advertising". _('여드름 완화'는 실증 자료의 대상 명칭이므로 규제 매핑을 적용하지 않고 원뜻(acne relief)대로 번역함)_ | Holds substantiation data for acne relief in accordance with the Regulation on the Substantiation of Cosmetic Labeling and Advertising. | Holds substantiation data for acne alleviation under the "Regulation on Substantiation of Cosmetic Labeling and Advertising" _('여드름 완화' retained as the term used in the cited substantiation regulation; altering it would misstate what the substantiation data covers.)_ | Substantiation data for acne alleviation is available in accordance with the “Regulations on Substantiating Cosmetics Labeling and Advertising Claims” | Holds substantiating data for acne relief in accordance with the “Regulations on Substantiation of Cosmetic Labeling and Advertising.” | Holds acne relief efficacy data per 'Regulations on Cosmetics Labeling and Advertising Substantiation' _(Legal reference to a regulatory category. '여드름 완화' rendered as 'acne relief' (the official Korean regulatory category name), not replaced with the mapped expression.)_ |
| 04 | 고시 분류: 미백 / 주름 개선 / 자외선 차단 | Notification category: Whitening / Anti-wrinkle / UV protection _(고시 분류 명칭이므로 규제 매핑을 적용하지 않고 원뜻대로 번역함)_ | Official Classification: Whitening / Wrinkle Improvement / UV Protection | Notified categories: Skin whitening / Wrinkle improvement / UV protection _(Official functional-cosmetics category names listed as legal classifications, so original regulatory terminology retained.)_ | Regulatory categories: Whitening / Wrinkle Improvement / UV Protection | Notification classification: Whitening / Wrinkle Improvement / UV Protection | Notification Category: Brightening / Wrinkle Improvement / UV Protection _(Official regulatory classification labels. Translated using standard English equivalents of Korean functional cosmetics categories.)_ |
| 05 | 「기능성화장품 기준 및 시험방법」의 미백 시험법을 적용했습니다 | Applied the whitening test method from the "Standards and Testing Methods for Functional Cosmetics". _('미백'은 시험법 명칭이므로 규제 매핑을 적용하지 않고 원뜻(whitening)대로 번역함)_ | Applied the whitening test method from the Standards and Test Methods for Functional Cosmetics. | Applies the skin-whitening test method of the "Functional Cosmetics Standards and Test Methods" _('미백' retained as the name of the official test method cited; substituting it would misidentify the referenced testing standard.)_ | Tested using the whitening test method specified in the “Standards and Test Methods for Functional Cosmetics” | Applied the whitening test method under the “Standards and Test Methods for Functional Cosmetics.” | Applied brightening test method per 'Standards and Test Methods for Functional Cosmetics' _(Legal reference to a test method name. '미백' translated as 'brightening' per standard English rendering of the Korean regulatory test method.)_ |

### 15_ui_label

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 카테고리: 스킨케어 > 미백 > 앰플 | Category: Skincare > Brightening > Ampoule _(미백 -> Brightening 규제 매핑 적용)_ | Category: Skincare > Brightening > Ampoule _(규제 매핑 적용: 미백 → brightening)_ | Category: Skincare > Brightening > Ampoule | Category: Skincare > Brightening > Ampoules | Category: Skincare > Brightening > Ampoules | Category: Skincare > Whitening > Ampoule |
| 02 | 연관 검색어: 안티에이징, 탄력 강화 | Related Searches: Age-defying, For a firmer look _(안티에이징 -> Age-defying, 탄력 강화 -> For a firmer look 규제 매핑 적용)_ | Related Searches: Age-defying, For a firmer look _(규제 매핑 적용: 안티에이징 → age-defying, 탄력 강화 → for a firmer look)_ | Related searches: age-defying, for a firmer look | Related Searches: Anti-Aging, Firming | Related Searches: Anti-Aging, Firmness Enhancement | Related Searches: Anti-aging, Firming |
| 03 | 필터: 트러블 / 모공 축소 / 재생 | Filter: Blemish-prone concerns / Pore-refining appearance / Renewing _(트러블 -> Blemish-prone concerns, 모공 축소 -> Pore-refining appearance, 재생 -> Renewing 규제 매핑 적용)_ | Filter: Blemish-prone concerns / Pore-refining appearance / Renewing _(규제 매핑 적용: 트러블 → blemish-prone concerns, 모공 축소 → pore-refining appearance, 재생 → renewing)_ | Filters: blemish-prone concerns / pore-refining appearance / renewing | Filters: Blemish Care / Pore Minimizing / Skin Renewal | Filter: Skin Concerns / Pore Reduction / Regeneration | Filters: Trouble / Pore Minimizing / Regeneration |
| 04 | 탭 메뉴 — 성분 \| 사용법 \| 주름 개선 정보 | Tab Menu — Ingredients \| How to Use \| Helps reduce the look of fine lines info _(주름 개선 -> Helps reduce the look of fine lines 규제 매핑 적용)_ | Tab Menu — Ingredients \| How to Use \| Helps reduce the look of fine lines info _(규제 매핑 적용: 주름 개선 → helps reduce the look of fine lines)_ | Tabs — Ingredients \| How to Use \| Reducing the Look of Fine Lines _(탭 라벨 길이 제약상 '주름 개선' 대체표현(helps reduce the look of fine lines)을 명사구 형태로 축약함)_ | Tabs — Ingredients \| How to Use \| Wrinkle Improvement Info | Tab Menu — Ingredients \| How to Use \| Wrinkle Improvement Info | Tab Menu — Ingredients \| How to Use \| Wrinkle Improvement Info |
| 05 | 정렬: 기미 개선 인기순 | Sort by: Popular for improving uneven-looking areas _(기미 -> Uneven-looking areas 규제 매핑 적용)_ | Sort: Most popular for improving uneven-looking areas _(규제 매핑 적용: 기미 → uneven-looking areas)_ | Sort: Popular for uneven-looking areas | Sort: Most Popular for Melasma Improvement | Sort: Most Popular for Melasma Improvement | Sort: Popularity for Melasma Improvement |

### 16_award

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 2026 뷰티 어워드 미백 부문 대상 | 2026 Beauty Awards Grand Prize in Whitening _(규제 매핑 예외 적용(2번 규칙): 어워드 부문명이라는 사실관계를 훼손하지 않기 위해 brightening 대신 Whitening으로 번역함.)_ | 2026 Beauty Awards Grand Prize in Whitening Category _(외부 어워드 공식 수상 부문명이므로 사실관계 유지를 위해 규제 대체어 대신 원 부문명을 직관적으로 번역함)_ | 2026 Beauty Awards — Grand Prize, Whitening Category _(제3자 시상 부문명(고유명사)이므로 규제 매핑을 적용하지 않고 원문 그대로 옮김. 부문명을 바꾸면 수상 사실 자체가 달라짐.)_ | 2026 Beauty Awards Grand Prize in Brightening | 2026 Beauty Awards Grand Prize, Brightening Category | 2026 Beauty Awards Whitening Category Grand Prize |
| 02 | 코스메틱 이노베이션 안티에이징 부문 수상 | Cosmetic Innovation Winner in Anti-aging _(규제 매핑 예외 적용(2번 규칙): 어워드 부문명이므로 age-defying 대신 Anti-aging으로 유지함.)_ | Cosmetic Innovation Award Winner in Anti-Aging Category _(어워드 부문명이므로 사실관계 유지를 위해 원 부문명을 유지 번역함)_ | Cosmetic Innovation Awards — Anti-Aging Category Winner _(외부 어워드의 부문명이라 원표기 유지. 브랜드 자체 효능 주장이 아님.)_ | Cosmetic Innovation Anti-Aging Category Winner | Cosmetic Innovation Award, Anti-Aging Category | Cosmetic Innovation Anti-Aging Category Award |
| 03 | 소비자 선정 트러블 케어 브랜드 1위 | #1 Consumer Choice Trouble Care Brand _(규제 매핑 예외 적용(2번 규칙): 선정 카테고리명이므로 blemish-prone concerns 대신 Trouble Care로 번역함.)_ | Consumer's Choice No. 1 Trouble Care Brand _(제3자 선정 타이틀 명칭이므로 사실관계 유지를 위해 규제 대체어 대신 원 명칭을 유지 번역함)_ | No.1 Consumer-Selected Trouble Care Brand _(소비자 선정 어워드의 부문·타이틀 명칭이므로 원문 유지.)_ | Consumer-Voted No. 1 Blemish Care Brand | No. 1 Consumer-Selected Blemish Care Brand | Consumer's Choice #1 Trouble Care Brand |
| 04 | 「재생 앰플 부문」 3년 연속 선정 | Selected 3 Consecutive Years in the "Regenerating Ampoule Category" _(규제 매핑 예외 적용(2번 규칙): 고유 부문명이므로 renewing 대신 Regenerating으로 번역함.)_ | Selected 3 Consecutive Years in "Regenerating Ampoule" Category _(어워드/선정 공식 부문명이므로 사실관계 왜곡 방지를 위해 원 명칭을 유지 번역함)_ | Selected 3 Years in a Row in the “Regeneration Ampoule Category” _(인용부호로 표시된 부문명이므로 원표기 유지.)_ | Selected for 3 Consecutive Years in the “Regenerating Ampoule Category” | Selected for 3 Consecutive Years in the “Renewal Ampoule Category” | "Regenerating Ampoule Category" 3 Years Running |
| 05 | 모공 축소 카테고리 어워드 본상 | Main Award in the Pore Minimizing Category _(규제 매핑 예외 적용(2번 규칙): 카테고리명이므로 pore-refining appearance 대신 Pore Minimizing으로 번역함.)_ | Main Prize in Pore Minimizing Category Award _(어워드 공식 카테고리 명칭이므로 사실관계 유지를 위해 원 부문명을 유지 번역함)_ | Pore Minimizing Category Awards — Main Prize _(어워드 카테고리 명칭이므로 원문 그대로 옮김.)_ | Pore Reduction Category Main Award | Main Prize, Pore-Minimizing Category Award | Pore Minimizing Category Award Main Prize |

### 17_strong_claim

| # | 원문 | `v6_principle/gemini` | `v6_principle/gemini_flash38` | `v6_principle/claude` | `v6_principle/gpt_sol` | `v6_principle/gpt_terra` | `v6_principle/qwen_plus` |
|---|---|---|---|---|---|---|---|
| 01 | 미백은 물론 주름 개선까지 한 번에 | Brightening and helps reduce the look of fine lines all at once _(규제 매핑 적용: '미백' -> 'brightening', '주름 개선' -> 'helps reduce the look of fine lines')_ | Brightening as well as helps reduce the look of fine lines, all in one _(규제 매핑 적용: '미백' → 'brightening', '주름 개선' → 'helps reduce the look of fine lines')_ | Brightening and helps reduce the look of fine lines, all in one _('미백' → brightening, '주름 개선' → helps reduce the look of fine lines (규제 매핑 적용))_ | Brightening and helps reduce the look of fine lines—all in one _(Replaced efficacy claims with compliant wording.)_ | Brightening and helps reduce the look of fine lines, all in one _(Replaced 미백 with “brightening” and 주름 개선 with “helps reduce the look of fine lines.”)_ | Brightening and helps reduce the look of fine lines, all at once |
| 02 | 안티에이징 효과를 직접 확인하세요 | Experience the age-defying effect yourself _(규제 매핑 적용: '안티에이징' -> 'age-defying')_ | Experience the age-defying effect for yourself _(규제 매핑 적용: '안티에이징' → 'age-defying')_ | See the age-defying results for yourself _('안티에이징' → age-defying (규제 매핑 적용))_ | See the age-defying effects for yourself _(Replaced “anti-aging” with “age-defying.”)_ | See the age-defying results for yourself _(Replaced 안티에이징 with “age-defying.”)_ | See the age-defying results for yourself |
| 03 | 즉각 달라지는 모공 축소 효과 | Fast-acting changes for a pore-refining appearance _(규제 매핑 적용: '즉각' -> 'fast-acting', '모공 축소' -> 'pore-refining appearance')_ | Fast-acting, visible pore-refining appearance _(규제 매핑 적용: '즉각' → 'fast-acting', '모공 축소' → 'pore-refining appearance')_ | Fast-acting pore-refining appearance _('즉각' → fast-acting, '모공 축소' → pore-refining appearance (규제 매핑 적용))_ | Fast-acting pore-refining appearance _(Replaced “instant” and “pore reduction” with compliant wording.)_ | Fast-acting pore-refining appearance _(Replaced 즉각 with “fast-acting” and 모공 축소 with “pore-refining appearance.”)_ | Fast-acting pore-refining appearance |
| 04 | 트러블 걱정 없는 재생 케어 | Renewing care without blemish-prone concerns _(규제 매핑 적용: '트러블' -> 'blemish-prone concerns', '재생' -> 'renewing')_ | Renewing care without worry of blemish-prone concerns _(규제 매핑 적용: '트러블' → 'blemish-prone concerns', '재생' → 'renewing')_ | Renewing care without blemish-prone concerns _('재생' → renewing, '트러블' → blemish-prone concerns (규제 매핑 적용))_ | Renewing care without blemish-prone concerns _(Replaced “trouble” and “regeneration” with compliant wording.)_ | Renewing care without worries about blemish-prone concerns _(Replaced 트러블 with “blemish-prone concerns” and 재생 with “renewing.”)_ | Worry-free renewing care for blemish-prone concerns |
| 05 | 100% 만족을 약속드립니다 | We promise pure satisfaction _(규제 매핑 적용: '100%' -> 'pure')_ | We promise pure satisfaction _(규제 매핑 적용: '100%' → 'pure')_ | We promise pure satisfaction _('100%' → pure (규제 매핑 적용))_ | We promise pure satisfaction _(Replaced “100%” with “pure.”)_ | We promise pure satisfaction _(Replaced 100% with “pure.”)_ | Pure satisfaction guaranteed |
