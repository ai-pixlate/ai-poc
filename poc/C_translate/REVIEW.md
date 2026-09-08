# C. 로컬라이징 번역 — 육안 확정 작업지

> 자동 생성. `compare.py` 재실행 시 덮어씀.
> **확정 칸은 비어 있다. 사람이 채운다**(CLAUDE.md — 등급을 코드가 채우지 않는다).

## 대기 현황

| 절 | 무엇을 정하는가 | 건수 | 우선순위 |
|---|---|---|---|
| 1 | 함정 **불명(`?`)** — 기계가 판정을 보류한 건 | 0 | **필수** |
| 2 | 함정 **오답(`X`)** 재확인 | 37 | 권장 |
| 3 | 번역 품질 **A/B/C 등급** | 대상 6종 | **필수** |

> **judge 불일치는 육안 대상이 아니다** [확정 2026-08-25 / 예람님].
> 채점자 2종이 갈린 건을 사람이 다시 채점하지 않는다. 대신 **불일치가 적은 모델**,
> 즉 두 채점자가 더 잘 합의한 모델을 우선한다. 건수는 `scores/FINALS.md` 1절 참조.

---

## 1. 함정 불명 — 기계가 판정하지 않은 건

대체표현·직역형이 둘 다 검출되거나 둘 다 없어 **기계가 정하지 않고 올린 것**이다.

_없음_

---

## 2. 함정 오답 재확인

기계가 오답으로 판정한 건이다. **정말 오답인지** 확인한다.

| 대상 | 유형 | 기대 | **규제 매핑** | 원문 | 번역 | **확정(유지/정정)** |
|---|---|---|---|---|---|---|
| `v6_principle/gemini_flash38` | C 제품명(암시) | 유지 | `안티에이징` → `age-defying` | 안티에이징 라인 신제품 출시 | New Product Launch: Age-Defying Line |  |
| `v6_principle/gemini_flash38` | C 제품명(암시) | 유지 | `미백` → `brightening` | 미백 앰플 리필 파우치도 함께 준비했습니다 | We've also prepared a refill pouch for the brightening ampoule |  |
| `v6_principle/gemini_flash38` | C 제품명(암시) | 유지 | `재생` → `renewing` | 재생 크림과 함께 쓰면 더 좋습니다 | Works even better when used with the renewing cream |  |
| `v6_principle/gemini_flash38` | C 제품명(암시) | 유지 | `트러블` → `blemish-prone concerns` | 트러블 라인 전 품목 10% 할인 | 10% off all items in the blemish-prone concerns line |  |
| `v6_principle/gemini_flash38` | C 제품명(암시) | 유지 | `탄력 강화` → `for a firmer look` | 탄력 강화 세럼은 별매입니다 | Serum for a firmer look is sold separately |  |
| `v6_principle/claude` | C 제품명(암시) | 유지 | `안티에이징` → `age-defying` | 안티에이징 라인 신제품 출시 | New age-defying line now available |  |
| `v6_principle/claude` | C 제품명(암시) | 유지 | `미백` → `brightening` | 미백 앰플 리필 파우치도 함께 준비했습니다 | A brightening ampoule refill pouch is available too |  |
| `v6_principle/claude` | C 제품명(암시) | 유지 | `재생` → `renewing` | 재생 크림과 함께 쓰면 더 좋습니다 | Even better paired with the renewing cream |  |
| `v6_principle/claude` | C 제품명(암시) | 유지 | `트러블` → `blemish-prone concerns` | 트러블 라인 전 품목 10% 할인 | 10% off the entire line for blemish-prone concerns |  |
| `v6_principle/claude` | C 제품명(암시) | 유지 | `탄력 강화` → `for a firmer look` | 탄력 강화 세럼은 별매입니다 | The serum for a firmer look is sold separately |  |
| `v6_principle/claude` | D 인용문 | 유지 | `미백` → `brightening` | 리뷰 인용: "미백 효과를 기대했는데 보습이 더 좋았어요" | Review quote: "I expected a brightening effect, but the hydration was even better" |  |
| `v6_principle/gpt_sol` | C 제품명(암시) | 유지 | `안티에이징` → `age-defying` | 안티에이징 라인 신제품 출시 | Introducing Our New Age-Defying Line |  |
| `v6_principle/gpt_sol` | C 제품명(암시) | 유지 | `미백` → `brightening` | 미백 앰플 리필 파우치도 함께 준비했습니다 | Now Available with a Brightening Ampoule Refill Pouch |  |
| `v6_principle/gpt_sol` | C 제품명(암시) | 유지 | `재생` → `renewing` | 재생 크림과 함께 쓰면 더 좋습니다 | Works Even Better with the Renewing Cream |  |
| `v6_principle/gpt_sol` | C 제품명(암시) | 유지 | `트러블` → `blemish-prone concerns` | 트러블 라인 전 품목 10% 할인 | 10% Off the Entire Blemish-Prone Concerns Line |  |
| `v6_principle/gpt_sol` | C 제품명(암시) | 유지 | `탄력 강화` → `for a firmer look` | 탄력 강화 세럼은 별매입니다 | Serum for a Firmer Look Sold Separately |  |
| `v6_principle/gpt_sol` | I 수상·부문명 | 유지 | `미백` → `brightening` | 2026 뷰티 어워드 미백 부문 대상 | 2026 Beauty Awards Grand Prize in Brightening |  |
| `v6_principle/gpt_terra` | A 부인 문맥 | 유지 | `치료` → `care` | 본 제품은 의약품이 아니므로 질환의 치료를 목적으로 사용할 수 없습니다 | This product is not a medicine and cannot be used for the care of diseases. |  |
| `v6_principle/gpt_terra` | C 제품명(암시) | 유지 | `안티에이징` → `age-defying` | 안티에이징 라인 신제품 출시 | New Age-Defying Line Launch |  |
| `v6_principle/gpt_terra` | C 제품명(암시) | 유지 | `미백` → `brightening` | 미백 앰플 리필 파우치도 함께 준비했습니다 | Brightening Ampoule Refill Pouches Also Available |  |
| `v6_principle/gpt_terra` | C 제품명(암시) | 유지 | `재생` → `renewing` | 재생 크림과 함께 쓰면 더 좋습니다 | Even Better with Renewing Cream |  |
| `v6_principle/gpt_terra` | C 제품명(암시) | 유지 | `트러블` → `blemish-prone concerns` | 트러블 라인 전 품목 10% 할인 | 10% Off All Blemish-Prone Concerns Line Products |  |
| `v6_principle/gpt_terra` | C 제품명(암시) | 유지 | `탄력 강화` → `for a firmer look` | 탄력 강화 세럼은 별매입니다 | Serum for a Firmer Look Sold Separately |  |
| `v6_principle/gpt_terra` | I 수상·부문명 | 유지 | `미백` → `brightening` | 2026 뷰티 어워드 미백 부문 대상 | 2026 Beauty Awards Grand Prize, Brightening Category |  |
| `v6_principle/qwen_plus` | C 제품명(명시) | 유지 | `미백` → `brightening` | 루미에르 미백 앰플 30ml (제품명) | Lumière Brightening Ampoule 30ml (Product Name) |  |
| `v6_principle/qwen_plus` | C 제품명(명시) | 유지 | `안티에이징` → `age-defying` | 루미에르 안티에이징 크림 50ml (제품명) | Lumière Age-Defying Cream 50ml (Product Name) |  |
| `v6_principle/qwen_plus` | C 제품명(명시) | 유지 | `재생` → `renewing` | 루미에르 재생 에센스 (제품명) | Lumière Renewing Essence (Product Name) |  |
| `v6_principle/qwen_plus` | C 제품명(명시) | 유지 | `트러블` → `blemish-prone concerns` | 루미에르 트러블 스팟 세럼 15ml (제품명) | Lumière Spot Serum for Blemish-Prone Concerns 15ml (Product Name) |  |
| `v6_principle/qwen_plus` | C 제품명(명시) | 유지 | `100%` → `pure` | 루미에르 100% 오일 (제품명) | Lumière Pure Oil (Product Name) |  |
| `v6_principle/qwen_plus` | C 제품명(암시) | 유지 | `안티에이징` → `age-defying` | 안티에이징 라인 신제품 출시 | New Launch: Age-Defying Line |  |
| `v6_principle/qwen_plus` | C 제품명(암시) | 유지 | `미백` → `brightening` | 미백 앰플 리필 파우치도 함께 준비했습니다 | Brightening Ampoule Refill Pouch Also Available |  |
| `v6_principle/qwen_plus` | C 제품명(암시) | 유지 | `재생` → `renewing` | 재생 크림과 함께 쓰면 더 좋습니다 | Even Better with Renewing Cream |  |
| `v6_principle/qwen_plus` | C 제품명(암시) | 유지 | `트러블` → `blemish-prone concerns` | 트러블 라인 전 품목 10% 할인 | 10% Off All Blemish-Prone Concerns Line |  |
| `v6_principle/qwen_plus` | C 제품명(암시) | 유지 | `탄력 강화` → `for a firmer look` | 탄력 강화 세럼은 별매입니다 | Serum for a Firmer Look Sold Separately |  |
| `v6_principle/qwen_plus` | G 법령·고시 인용 | 유지 | `미백` → `brightening` | 화장품법 시행규칙의 미백 표시·광고 기준을 따릅니다 | Complies with brightening labeling and advertising standards under Enforcement Rules of the Cosmetics Act |  |
| `v6_principle/qwen_plus` | G 법령·고시 인용 | 유지 | `미백` → `brightening` | 고시 분류: 미백 / 주름 개선 / 자외선 차단 | Notification Category: Brightening / Wrinkle Improvement / UV Protection |  |
| `v6_principle/qwen_plus` | G 법령·고시 인용 | 유지 | `미백` → `brightening` | 「기능성화장품 기준 및 시험방법」의 미백 시험법을 적용했습니다 | Applied brightening test method per 'Standards and Test Methods for Functional Cosmetics' |  |

---

## 3. 번역 품질 등급

함정 정답률은 **규제 처리만** 잰다. 번역의 자연스러움·현지화는 이 표가 맡는다.

| 대상 | **등급 (A/B/C)** | 근거 |
|---|---|---|
| `v6_principle/gemini` |  |  |
| `v6_principle/gemini_flash38` |  |  |
| `v6_principle/claude` |  |  |
| `v6_principle/gpt_sol` |  |  |
| `v6_principle/gpt_terra` |  |  |
| `v6_principle/qwen_plus` |  |  |
