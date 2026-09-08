# 줄·문단 병합 + 역할 분류 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **판정 칸은 사람이 채움.**
> 입력은 텍스트 인식 `baseline` 영역. 판정 기준·계획은 `PoC_추가검증_계획.md`.

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

## 3. 판정표

`병합`·`역할`은 이미지 단위 A/B/C. 나머지는 건수.

- **과분할** = 한 문단이 여러 블록으로 쪼개진 건
- **과병합** = 서로 다른 문단이 한 블록으로 붙은 건
- **오분류** = 역할 5종을 잘못 준 블록 수

| 이미지 | variant | 영역 | 블록 | 병합 | 역할 | 과분할 | 과병합 | 오분류 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.jpg | `heuristic_v1` | 13 | 7 |  |  |  |  |  |  | `results/heuristic_v1/vis/1.jpg` |
| 1.jpg | `heuristic_v2` | 13 | 7 |  |  |  |  |  |  | `results/heuristic_v2/vis/1.jpg` |
| 2.jpg | `heuristic_v1` | 18 | 9 |  |  |  |  |  |  | `results/heuristic_v1/vis/2.jpg` |
| 2.jpg | `heuristic_v2` | 18 | 9 |  |  |  |  |  |  | `results/heuristic_v2/vis/2.jpg` |
| 3.jpg | `heuristic_v1` | 5 | 4 |  |  |  |  |  |  | `results/heuristic_v1/vis/3.jpg` |
| 3.jpg | `heuristic_v2` | 5 | 4 |  |  |  |  |  |  | `results/heuristic_v2/vis/3.jpg` |
| 4.jpg | `heuristic_v1` | 11 | 5 |  |  |  |  |  |  | `results/heuristic_v1/vis/4.jpg` |
| 4.jpg | `heuristic_v2` | 11 | 5 |  |  |  |  |  |  | `results/heuristic_v2/vis/4.jpg` |
| 5.jpg | `heuristic_v1` | 38 | 24 |  |  |  |  |  |  | `results/heuristic_v1/vis/5.jpg` |
| 5.jpg | `heuristic_v2` | 38 | 25 |  |  |  |  |  |  | `results/heuristic_v2/vis/5.jpg` |
| 6.jpg | `heuristic_v1` | 28 | 15 |  |  |  |  |  |  | `results/heuristic_v1/vis/6.jpg` |
| 6.jpg | `heuristic_v2` | 28 | 16 |  |  |  |  |  |  | `results/heuristic_v2/vis/6.jpg` |
| 7.jpg | `heuristic_v1` | 34 | 17 |  |  |  |  |  |  | `results/heuristic_v1/vis/7.jpg` |
| 7.jpg | `heuristic_v2` | 34 | 21 |  |  |  |  |  |  | `results/heuristic_v2/vis/7.jpg` |
| 8.jpg | `heuristic_v1` | 14 | 10 |  |  |  |  |  |  | `results/heuristic_v1/vis/8.jpg` |
| 8.jpg | `heuristic_v2` | 14 | 10 |  |  |  |  |  |  | `results/heuristic_v2/vis/8.jpg` |
| 9.jpg | `heuristic_v1` | 39 | 19 |  |  |  |  |  |  | `results/heuristic_v1/vis/9.jpg` |
| 9.jpg | `heuristic_v2` | 39 | 23 |  |  |  |  |  |  | `results/heuristic_v2/vis/9.jpg` |
| 10.jpg | `heuristic_v1` | 17 | 9 |  |  |  |  |  |  | `results/heuristic_v1/vis/10.jpg` |
| 10.jpg | `heuristic_v2` | 17 | 11 |  |  |  |  |  |  | `results/heuristic_v2/vis/10.jpg` |
| 11.jpg | `heuristic_v1` | 46 | 32 |  |  |  |  |  |  | `results/heuristic_v1/vis/11.jpg` |
| 11.jpg | `heuristic_v2` | 46 | 36 |  |  |  |  |  |  | `results/heuristic_v2/vis/11.jpg` |
| 12.jpg | `heuristic_v1` | 17 | 8 |  |  |  |  |  |  | `results/heuristic_v1/vis/12.jpg` |
| 12.jpg | `heuristic_v2` | 17 | 9 |  |  |  |  |  |  | `results/heuristic_v2/vis/12.jpg` |

## 4. `heuristic_v1` vs `heuristic_v2` — 블록 수 차이

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

## 5. 집계

_판정 전_ — 채워진 칸 없음.

