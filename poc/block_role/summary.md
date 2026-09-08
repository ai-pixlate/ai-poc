# 줄·문단 병합 + 역할 분류 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **판정 칸은 사람이 채움.**
> 입력은 텍스트 인식 `baseline` 영역. 판정 기준·계획은 `PoC_추가검증_계획.md`.
> **정답 라벨 없음** — 병합·역할의 정오는 육안 A/B/C로 판정함.

## 1. 실행 조건

| variant | 조건 | 이미지 | 영역 | 블록 | 소요 |
|---|---|---|---|---|---|
| `heuristic_v1` | `line_gap=1.0` `para_gap=0.8` `h_ratio=2.0` `overlap=0.4` `gutter=False` | 12 | 280 | 159 | 0.13s |
| `heuristic_v2` | `line_gap=0.7` `para_gap=0.6` `h_ratio=1.5` `overlap=0.5` `gutter=True` | 12 | 280 | 176 | 0.13s |

## 2. 역할 분포 (기계 집계 — 정오 아님)

| variant | 제목 | 본문 | 캡션 | 가격 | 주의문구 |
|---|---|---|---|---|---|
| `heuristic_v1` | 46 | 78 | 33 | 1 | 1 |
| `heuristic_v2` | 50 | 85 | 39 | 1 | 1 |

## 3. 보조 지표 (정답 없이 계산 — 정오 아님)

- **겹침** = 블록 bbox가 서로 겹치는 쌍의 수. 과병합에서도 늘지만 **원래 겹쳐 배치된 레이아웃**(제품 패키지 사진 등)에서도 늚 — vis로 갈라야 함
- **이질** = 한 블록 안에서 글자 높이가 1.5배 넘게 벌어진 블록 수. `h_ratio`가 직접 누르는 값이라 **variant 간 차이는 설계상 당연** — 총수보다 어느 블록인지가 정보

| variant | 겹침 | 이질 | 겹침 있는 이미지 |
|---|---|---|---|
| `heuristic_v1` | 32 | 20 | 2.jpg(3), 3.jpg(3), 4.jpg(2), 5.jpg(2), 6.jpg(4), 7.jpg(2), 8.jpg(1), 9.jpg(4), 11.jpg(10), 12.jpg(1) |
| `heuristic_v2` | 38 | 4 | 2.jpg(3), 3.jpg(3), 4.jpg(2), 5.jpg(2), 6.jpg(4), 7.jpg(4), 8.jpg(1), 9.jpg(5), 11.jpg(13), 12.jpg(1) |

**`heuristic_v1` ↔ `heuristic_v2` 블록 경계 일치율** — 구성 영역이 완전히 같은 블록 기준.

| 이미지 | 일치 블록 | 일치율 |
|---|---|---|
| 1.jpg | 7 | 100% |
| 2.jpg | 9 | 100% |
| 3.jpg | 4 | 100% |
| 4.jpg | 5 | 100% |
| 5.jpg | 21 | 86% |
| 6.jpg | 14 | 90% |
| 7.jpg | 12 | 63% |
| 8.jpg | 10 | 100% |
| 9.jpg | 13 | 62% |
| 10.jpg | 8 | 80% |
| 11.jpg | 28 | 82% |
| 12.jpg | 7 | 82% |
| **전체** | **138** | **87%** |

## 4. 판정표

`병합`·`역할`은 이미지 단위 A/B/C. 나머지는 건수. **겹침·이질은 코드가 채움.**

- **과분할** = 한 문단이 여러 블록으로 쪼개진 건
- **과병합** = 서로 다른 문단이 한 블록으로 붙은 건
- **오분류** = 역할 5종을 잘못 준 블록 수

**등급 기준** — 건수만 채우면 6장이 산식 등급을 계산함.

| 축 | A | B | C |
|---|---|---|---|
| 병합 | 가중 오류율 ≤ 10% **그리고 과병합 0** | ≤ 25% | 그 외 |
| 역할 | 오분류율 ≤ 10% | ≤ 25% | 그 외 |

- 가중 오류 = 과분할 + 과병합 × 2. **과병합이 더 무거움** — 과분할은 조각이 제자리에 남지만 과병합은 되돌릴 수 없음
- 블록 10개 미만 이미지는 가중 오류 1건까지 A (과병합 0일 때만)
- **주의문구를 다른 역할로 준 건(미탐)이 1건 있으면 역할은 최대 B, 2건 이상이면 C.** 규제 판정이 통째로 빠지므로 산식보다 우선함 — 비고에 적고 사람이 직접 내릴 것

**제외 관례 — 제품 인쇄 글자(라벨)**

| 축 | 처리 |
|---|---|
| 역할 오분류 | **세지 않음.** 비고에 `라벨 n건 제외`로 적을 것 |
| 과분할·과병합 | **그대로 셈** — 라벨이든 아니든 블록 경계는 맞아야 함 |

제품 용기·패키지에 인쇄된 글자는 5종(제목·본문·캡션·가격·주의문구) 중 무엇으로 불러도 의미가 없음. **제품 라벨 판정 과업에서 별도로 판정함** — 여기서 억지로 5종에 넣어 세면 같은 블록을 서로 다른 기준으로 두 번 판정하게 됨. 인페인팅 판정에서 쓴 관례와 같음(`PoC_검증_계획_및_기록.md` 2.2).

| 이미지 | variant | 영역 | 블록 | 겹침 | 이질 | 병합 | 역할 | 과분할 | 과병합 | 오분류 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.jpg | `heuristic_v1` | 13 | 7 | 0 | 0 |  |  |  |  |  |  | `results/heuristic_v1/vis/1.jpg` |
| 1.jpg | `heuristic_v2` | 13 | 7 | 0 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/1.jpg` |
| 2.jpg | `heuristic_v1` | 18 | 9 | 3 | 1 |  |  |  |  |  |  | `results/heuristic_v1/vis/2.jpg` |
| 2.jpg | `heuristic_v2` | 18 | 9 | 3 | 1 |  |  |  |  |  |  | `results/heuristic_v2/vis/2.jpg` |
| 3.jpg | `heuristic_v1` | 5 | 4 | 3 | 0 |  |  |  |  |  |  | `results/heuristic_v1/vis/3.jpg` |
| 3.jpg | `heuristic_v2` | 5 | 4 | 3 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/3.jpg` |
| 4.jpg | `heuristic_v1` | 11 | 5 | 2 | 0 |  |  |  |  |  |  | `results/heuristic_v1/vis/4.jpg` |
| 4.jpg | `heuristic_v2` | 11 | 5 | 2 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/4.jpg` |
| 5.jpg | `heuristic_v1` | 38 | 24 | 2 | 2 |  |  |  |  |  |  | `results/heuristic_v1/vis/5.jpg` |
| 5.jpg | `heuristic_v2` | 38 | 25 | 2 | 1 |  |  |  |  |  |  | `results/heuristic_v2/vis/5.jpg` |
| 6.jpg | `heuristic_v1` | 28 | 15 | 4 | 1 |  |  |  |  |  |  | `results/heuristic_v1/vis/6.jpg` |
| 6.jpg | `heuristic_v2` | 28 | 16 | 4 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/6.jpg` |
| 7.jpg | `heuristic_v1` | 34 | 17 | 2 | 4 |  |  |  |  |  |  | `results/heuristic_v1/vis/7.jpg` |
| 7.jpg | `heuristic_v2` | 34 | 21 | 4 | 1 |  |  |  |  |  |  | `results/heuristic_v2/vis/7.jpg` |
| 8.jpg | `heuristic_v1` | 14 | 10 | 1 | 0 |  |  |  |  |  |  | `results/heuristic_v1/vis/8.jpg` |
| 8.jpg | `heuristic_v2` | 14 | 10 | 1 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/8.jpg` |
| 9.jpg | `heuristic_v1` | 39 | 19 | 4 | 5 |  |  |  |  |  |  | `results/heuristic_v1/vis/9.jpg` |
| 9.jpg | `heuristic_v2` | 39 | 23 | 5 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/9.jpg` |
| 10.jpg | `heuristic_v1` | 17 | 9 | 0 | 1 |  |  |  |  |  |  | `results/heuristic_v1/vis/10.jpg` |
| 10.jpg | `heuristic_v2` | 17 | 11 | 0 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/10.jpg` |
| 11.jpg | `heuristic_v1` | 46 | 32 | 10 | 5 |  |  |  |  |  |  | `results/heuristic_v1/vis/11.jpg` |
| 11.jpg | `heuristic_v2` | 46 | 36 | 13 | 1 |  |  |  |  |  |  | `results/heuristic_v2/vis/11.jpg` |
| 12.jpg | `heuristic_v1` | 17 | 8 | 1 | 1 |  |  |  |  |  |  | `results/heuristic_v1/vis/12.jpg` |
| 12.jpg | `heuristic_v2` | 17 | 9 | 1 | 0 |  |  |  |  |  |  | `results/heuristic_v2/vis/12.jpg` |

## 5. `heuristic_v1` vs `heuristic_v2` — 블록 수 차이

차이가 큰 이미지부터 보면 임계 변경의 효과를 빨리 판단할 수 있음.

| 이미지 | `heuristic_v1` | `heuristic_v2` | 차이 |
|---|---|---|---|
| 7.jpg | 17 | 21 | +4 |
| 9.jpg | 19 | 23 | +4 |
| 11.jpg | 32 | 36 | +4 |
| 10.jpg | 9 | 11 | +2 |
| 5.jpg | 24 | 25 | +1 |
| 6.jpg | 15 | 16 | +1 |
| 12.jpg | 8 | 9 | +1 |
| 1.jpg | 7 | 7 | +0 |
| 2.jpg | 9 | 9 | +0 |
| 3.jpg | 4 | 4 | +0 |
| 4.jpg | 5 | 5 | +0 |
| 8.jpg | 10 | 10 | +0 |

## 6. 집계

_판정 전_ — 채워진 칸 없음.

