# 골든 샘플 재실행 결과

> 계획 `PoC_골든샘플_재실행_계획.md` · **결과 문서 `PoC_골든샘플_재실행_결과.md`**(단계별 결론·미결).
> 골든 샘플 3상품 34장 → 섹션 102개로 확정 기술 7종 재실행한 결과 모음.
> 등급·집계 원본은 각 단계 `summary.md`. 이 표는 현황·링크만 담음.

## 현황

| 단계 | 과업 | 코드 | 결과 · 판정표 | 상태 | 게이트 |
|---|---|---|---|---|---|
| 1 | 텍스트 추출 | `poc/B_ocr` | [1_B_ocr](1_B_ocr/summary.md) | 실행 완료 · Claude 1차 판정 완료 · 예람님 검토 대기 | 텍스트 98/100 · bbox 99/100 — 1차 기준 통과 |
| 2 | 줄·문단 병합 + 역할 분류 | `poc/block_role` | [2_block_role](2_block_role/summary.md) | 실행 완료($0.1761) · 병합·역할 Claude 1차 판정 완료 · 예람님 검토 대기 | 병합 89/100 · 역할 94/100 — 1차 기준 통과 · **주의문구 미탐 22** |
| 3 | 제품 라벨 판정 | `poc/product_label` | [3_product_label](3_product_label/summary.md) | 실행 완료($0.2171) · Claude 1차 전수 판정 완료 · 예람님 검토 대기 · 정답지 `results/vlm_relation/truth.json` | 미탐 0 · 오탐 0 — 1차 기준 통과 |
| 4 | 브랜드 로고 제외 재확인 | `poc/logo_match` | [4_logo_match](4_logo_match/summary.md) | 실행 완료(비용 0) · 기존 정답과 기계 대조 완료 | 찾음 5 · 놓침 2 · 오탐 0 — **미달**(기존 6·1·0보다 놓침 +1) · 대응 _미정_ |
| 5 | 원문 지우기 | `poc/E1_inpaint` | [5_E1_inpaint](5_E1_inpaint/summary.md) | 실행 완료(비용 0) · Claude 1차 판정 완료 · 예람님 검토 대기 | `erase_all` 66% · 사진 54% — **미달** / `erase_s50` 72% · 사진 71% — 통과 · 확정 조건 변경 _미정_ |
| 6 | 스타일 추출 | `poc/style_extract` | [6_style_extract](6_style_extract/summary.md) | 실행 완료(비용 0) · Claude 1차 판정 완료 · 예람님 검토 대기 | 색 95/99(96%) · 크기 99/99(100%) · 정렬 99/99(100%) — 통과 |
| 7 | 번역 길이 팽창률 | `poc/length_expansion` | [7_length_expansion](7_length_expansion/summary.md) | 실행 완료($0.2506) · 기계 집계(육안 등급 없음) | 잔여 초과율 97%(12장 94%) — 통과선 없음 · **12장 결론 유지** |

## 이동 규칙

| 항목 | 내용 |
|---|---|
| 실행 출력 | `poc/{과업}/results/golden/{variant}/` · `poc/{과업}/summary_golden.md` — 코드 출력 경로 그대로 |
| 이동 | `python poc/golden/move.py {단계}` → `poc/golden/{단계}_{과업}/results/{variant}/` · `summary.md` (판정표 링크 자동 수정) |
| 재실행 | `move.py {단계} --restore` → 실행 · compare → `move.py {단계}`. 채운 등급은 원위치 판정표에서 회수됨 |
| 다음 단계 입력 | 이동 위치(`poc/golden/`)에서 읽음 |
| git | `summary.md`만 추적. `results/`는 `.gitignore` |
| API 캐시 | 과업 폴더 `cache/`에 남김. 이동 안 함 |
