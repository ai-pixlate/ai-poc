# 스타일 추출 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **색·크기·정렬 3칸이 사람이 채우는 전부임.**
> 입력은 텍스트 인식 `baseline` 영역 + `vlm_relation` 블록(정렬·역할·라벨).
> **굵기 추정·폰트 패밀리 식별은 범위 밖(12월).**

## 1. 실행 조건

| variant | 색 추출 방식 | 이미지 | 영역 | 소요 |
|---|---|---|---|---|
| `contrast_split` | 밝기 Otsu 이진화. 적은 쪽을 글자로 | 12 | 280 | 0.35s |
| `dominant_color` | bbox 화소를 2색 군집(k-means). 적은 쪽을 글자로 | 12 | 280 | 0.62s |

크기는 bbox 높이(글자 획 높이), em 환산 × **1.35**. 정렬 허용 오차는 블록 폭의 **12%**. 두 variant가 같음 — **변인은 색 추출 방식뿐임.**

## 2. 색 추출 (기계 집계 — 정오 아님)

**저대비** = 글자색·배경색 대비가 1.5 미만인 영역. 두 색이 갈리지 않았다는 뜻이라 **추출 실패 신호**임.

| variant | 대비 중앙 | 저대비 영역 | 저대비 비율 |
|---|---|---|---|
| `contrast_split` | 2.65 | 18 / 280 | 6% |
| `dominant_color` | 2.63 | 18 / 280 | 6% |

**`contrast_split` ↔ `dominant_color` 글자색 일치** — 완전 동일 134 / 다름 146 (48% 일치)

## 3. 정렬 분포 (기계 집계 — 정오 아님)

블록 안 행들의 좌·중앙·우 좌표 분산으로 판정함. **`불명`은 어느 축도 고르지 않은 것.**

| 구분 | left | center | right | 단일행 | 불명 | 합 |
|---|---|---|---|---|---|---|
| 라벨 아님 (조판 대상) | 4 | 43 | 4 | 13 | 46 | 110 |
| 제품 라벨 | 38 | 9 | 6 | 27 | 90 | 170 |

**라벨은 하류에서 제외되므로 `라벨 아님` 행만 실사용에 해당함.**

## 4. 판정표

**채울 칸은 `색`·`크기`·`정렬` 3개.** 이미지 단위 A/B/C. `영역`·`저대비`는 코드가 채움.

`vis/`는 원본 오른쪽에 **추출한 글자색·배경색 스와치**를 영역 번호 순으로 붙인 것. 원본 글자와 스와치를 나란히 놓고 대조하면 됨.

| 이미지 | variant | 영역 | 저대비 | 색 | 크기 | 정렬 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|
| 1.jpg | `contrast_split` | 13 | 2 |  |  |  |  | `results/contrast_split/vis/1.jpg` |
| 1.jpg | `dominant_color` | 13 | 2 |  |  |  |  | `results/dominant_color/vis/1.jpg` |
| 2.jpg | `contrast_split` | 18 | 4 |  |  |  |  | `results/contrast_split/vis/2.jpg` |
| 2.jpg | `dominant_color` | 18 | 4 |  |  |  |  | `results/dominant_color/vis/2.jpg` |
| 3.jpg | `contrast_split` | 5 | 1 |  |  |  |  | `results/contrast_split/vis/3.jpg` |
| 3.jpg | `dominant_color` | 5 | 1 |  |  |  |  | `results/dominant_color/vis/3.jpg` |
| 4.jpg | `contrast_split` | 11 | 0 |  |  |  |  | `results/contrast_split/vis/4.jpg` |
| 4.jpg | `dominant_color` | 11 | 0 |  |  |  |  | `results/dominant_color/vis/4.jpg` |
| 5.jpg | `contrast_split` | 38 | 9 |  |  |  |  | `results/contrast_split/vis/5.jpg` |
| 5.jpg | `dominant_color` | 38 | 9 |  |  |  |  | `results/dominant_color/vis/5.jpg` |
| 6.jpg | `contrast_split` | 28 | 0 |  |  |  |  | `results/contrast_split/vis/6.jpg` |
| 6.jpg | `dominant_color` | 28 | 0 |  |  |  |  | `results/dominant_color/vis/6.jpg` |
| 7.jpg | `contrast_split` | 34 | 0 |  |  |  |  | `results/contrast_split/vis/7.jpg` |
| 7.jpg | `dominant_color` | 34 | 0 |  |  |  |  | `results/dominant_color/vis/7.jpg` |
| 8.jpg | `contrast_split` | 14 | 2 |  |  |  |  | `results/contrast_split/vis/8.jpg` |
| 8.jpg | `dominant_color` | 14 | 2 |  |  |  |  | `results/dominant_color/vis/8.jpg` |
| 9.jpg | `contrast_split` | 39 | 0 |  |  |  |  | `results/contrast_split/vis/9.jpg` |
| 9.jpg | `dominant_color` | 39 | 0 |  |  |  |  | `results/dominant_color/vis/9.jpg` |
| 10.jpg | `contrast_split` | 17 | 0 |  |  |  |  | `results/contrast_split/vis/10.jpg` |
| 10.jpg | `dominant_color` | 17 | 0 |  |  |  |  | `results/dominant_color/vis/10.jpg` |
| 11.jpg | `contrast_split` | 46 | 0 |  |  |  |  | `results/contrast_split/vis/11.jpg` |
| 11.jpg | `dominant_color` | 46 | 0 |  |  |  |  | `results/dominant_color/vis/11.jpg` |
| 12.jpg | `contrast_split` | 17 | 0 |  |  |  |  | `results/contrast_split/vis/12.jpg` |
| 12.jpg | `dominant_color` | 17 | 0 |  |  |  |  | `results/dominant_color/vis/12.jpg` |

## 5. 집계

_판정 전_ — 채워진 칸 없음.

