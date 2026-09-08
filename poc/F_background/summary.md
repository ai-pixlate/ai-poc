# F. 배경 가공 — 보정 기법 비교

> 자동 생성 파일. `compare.py` 재실행 시 덮어씀 (채운 칸은 보존됨).

## 1. 실행 요약

- 입력: `poc/E1_inpaint/results/lama/` (E1 채택 결과), 마스크 `d15`
- F는 Go/No-Go 대상이 아니라 **개선 폭 확인** 과업 (문서 2.5)

| variant | 처리 유형 (문서 2.5) | 이미지 | 소요(s) |
|---|---|---|---|
| `feather` | 이음새 제거 — 마스크 경계 블러·알파 혼합 | 12 | 0.52 |
| `ring_lama` | 지운 자국 보정 — LaMa 재적용 (경계 링 마스크) | 12 | 86.76 |
| `seamless` | 색상·톤 정합 — OpenCV 포아송 블렌딩 | 12 | 2.26 |

> 문서 2.5의 "조각 이음새 제거"는 A(리플로우)로 조각을 이어붙인 결과가 입력인데
> A가 미착수라 대상이 없다. `feather`는 그 대신 **인페인팅 경계의 이음새**를 다룬다.

## 2. 판정표 (개선 여부 — 빈 칸 채울 것)

| 표기 | 뜻 |
|---|---|
| **O** | E1 결과보다 나아짐 |
| **=** | 차이 없음 |
| **X** | 오히려 나빠짐 |

| 이미지 | variant | 개선 여부 | 비고 | 대조 |
|---|---|---|---|---|
| 1.jpg | `feather` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `ring_lama` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `seamless` |   |   | [보기](results/compare/1.jpg) |
| 2.jpg | `feather` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `ring_lama` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `seamless` |   |   | [보기](results/compare/2.jpg) |
| 3.jpg | `feather` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `ring_lama` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `seamless` |   |   | [보기](results/compare/3.jpg) |
| 4.jpg | `feather` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `ring_lama` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `seamless` |   |   | [보기](results/compare/4.jpg) |
| 5.jpg | `feather` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `ring_lama` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `seamless` |   |   | [보기](results/compare/5.jpg) |
| 6.jpg | `feather` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `ring_lama` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `seamless` |   |   | [보기](results/compare/6.jpg) |
| 7.jpg | `feather` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `ring_lama` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `seamless` |   |   | [보기](results/compare/7.jpg) |
| 8.jpg | `feather` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `ring_lama` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `seamless` |   |   | [보기](results/compare/8.jpg) |
| 9.jpg | `feather` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `ring_lama` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `seamless` |   |   | [보기](results/compare/9.jpg) |
| 10.jpg | `feather` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `ring_lama` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `seamless` |   |   | [보기](results/compare/10.jpg) |
| 11.jpg | `feather` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `ring_lama` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `seamless` |   |   | [보기](results/compare/11.jpg) |
| 12.jpg | `feather` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `ring_lama` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `seamless` |   |   | [보기](results/compare/12.jpg) |

**집계** — 위 표에서 자동 계산됨

| variant | O | = | X | 미판정 |
|---|---|---|---|---|
| `feather` | 0 | 0 | 0 | 12 |
| `ring_lama` | 0 | 0 | 0 | 12 |
| `seamless` | 0 | 0 | 0 | 12 |
