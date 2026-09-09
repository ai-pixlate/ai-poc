# 스타일 추출 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **색·크기·정렬 3칸이 사람이 채우는 전부임.**
> 입력은 텍스트 인식 `baseline` 영역 + `vlm_relation` 블록(정렬·역할·라벨).
> 굵기·폰트 계열은 계획서상 범위 밖이나 **되는지만 시험함** — 6장.

## 1. 실행 조건

| variant | 색 추출 방식 | 이미지 | 영역 | 소요 |
|---|---|---|---|---|
| `contrast_split` | 밝기 Otsu 이진화. 적은 쪽을 글자로 | 12 | 280 | 0.52s |
| `dominant_color` | bbox 화소를 2색 군집(k-means). 적은 쪽을 글자로 | 12 | 280 | 0.71s |

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

**시각화는 `vis_target/` — 제품 라벨을 뺀 조판 대상만 그림.** 원본 오른쪽에 추출한 글자색·배경색 스와치를 붙였음. 번호는 전체 뷰(`vis/`)와 같음.

`영역`·`저대비`도 **조판 대상 기준**임. 라벨 포함 전체는 2장에 있음.

| 이미지 | variant | 영역 | 저대비 | 색 | 크기 | 정렬 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|
| 1.jpg | `contrast_split` | 10 | 0 |  |  |  |  | `results/contrast_split/vis_target/1.jpg` |
| 1.jpg | `dominant_color` | 10 | 0 |  |  |  |  | `results/dominant_color/vis_target/1.jpg` |
| 2.jpg | `contrast_split` | 10 | 0 |  |  |  |  | `results/contrast_split/vis_target/2.jpg` |
| 2.jpg | `dominant_color` | 10 | 0 |  |  |  |  | `results/dominant_color/vis_target/2.jpg` |
| 3.jpg | `contrast_split` | 0 | 0 |  |  |  |  | `results/contrast_split/vis_target/3.jpg` |
| 3.jpg | `dominant_color` | 0 | 0 |  |  |  |  | `results/dominant_color/vis_target/3.jpg` |
| 4.jpg | `contrast_split` | 11 | 0 |  |  |  |  | `results/contrast_split/vis_target/4.jpg` |
| 4.jpg | `dominant_color` | 11 | 0 |  |  |  |  | `results/dominant_color/vis_target/4.jpg` |
| 5.jpg | `contrast_split` | 2 | 0 |  |  |  |  | `results/contrast_split/vis_target/5.jpg` |
| 5.jpg | `dominant_color` | 2 | 0 |  |  |  |  | `results/dominant_color/vis_target/5.jpg` |
| 6.jpg | `contrast_split` | 12 | 0 |  |  |  |  | `results/contrast_split/vis_target/6.jpg` |
| 6.jpg | `dominant_color` | 12 | 0 |  |  |  |  | `results/dominant_color/vis_target/6.jpg` |
| 7.jpg | `contrast_split` | 4 | 0 |  |  |  |  | `results/contrast_split/vis_target/7.jpg` |
| 7.jpg | `dominant_color` | 4 | 0 |  |  |  |  | `results/dominant_color/vis_target/7.jpg` |
| 8.jpg | `contrast_split` | 14 | 2 |  |  |  |  | `results/contrast_split/vis_target/8.jpg` |
| 8.jpg | `dominant_color` | 14 | 2 |  |  |  |  | `results/dominant_color/vis_target/8.jpg` |
| 9.jpg | `contrast_split` | 15 | 0 |  |  |  |  | `results/contrast_split/vis_target/9.jpg` |
| 9.jpg | `dominant_color` | 15 | 0 |  |  |  |  | `results/dominant_color/vis_target/9.jpg` |
| 10.jpg | `contrast_split` | 15 | 0 |  |  |  |  | `results/contrast_split/vis_target/10.jpg` |
| 10.jpg | `dominant_color` | 15 | 0 |  |  |  |  | `results/dominant_color/vis_target/10.jpg` |
| 11.jpg | `contrast_split` | 8 | 0 |  |  |  |  | `results/contrast_split/vis_target/11.jpg` |
| 11.jpg | `dominant_color` | 8 | 0 |  |  |  |  | `results/dominant_color/vis_target/11.jpg` |
| 12.jpg | `contrast_split` | 9 | 0 |  |  |  |  | `results/contrast_split/vis_target/12.jpg` |
| 12.jpg | `dominant_color` | 9 | 0 |  |  |  |  | `results/dominant_color/vis_target/12.jpg` |

## 5. 집계

_판정 전_ — 채워진 칸 없음.

## 6. 굵기·폰트 계열 (추가 축)

계획서에는 **범위 밖(12월)**으로 적힌 항목임. 되는지만 보려고 붙였음. 대상은 **조판 대상 영역 중 높이 18px 이상**만.

| 측정 | 방법 |
|---|---|
| 굵기 | 글자 획 두께 ÷ 글자 높이. 거리 변환 상위 20% 평균 × 2. **0.14 이상이면 bold** |
| 계열 | 설치 폰트 **14종**으로 같은 글자를 렌더해 겹침(IoU) 비교 |

- 대상 **108영역** · 폰트 대조 성공 **70건** (한글 2자 이상만 대조함)
- 획 두께 기준 굵기 — regular 70 / bold 38
- 계열 판정 — 고딕 69 / 명조 1

**글자 수별 대조 신뢰도** — IoU 중앙값. 길수록 무너짐.

| 글자 수 | 건수 | IoU 중앙 |
|---|---|---|
| 2~3자 | 24 | 0.509 |
| 4~6자 | 23 | 0.326 |
| 7~12자 | 11 | 0.295 |
| 13자 이상 | 12 | 0.206 |

> ⚠️ **굵기 신호 두 개가 어긋남.** 획 두께는 regular 우세인데 폰트 대조는 bold를 고름 — 일치 19/70 (27%). 겹침 비교가 획이 두꺼운 후보에 유리해 생기는 편향으로 보임. **굵기는 획 두께 쪽을 볼 것.**

> 계열 점수차(고딕 최고점 − 명조 최고점) 중앙 **0.109**, 0.05 미만이라 사실상 판별 불가인 건이 **14/70**임.

### 판정표 — 굵기·계열

**채울 칸은 `굵기`·`계열` 2개.** 이미지 단위 A/B/C. `vis/`의 띠에 `번호 크기 획비율 굵기 계열/굵기 IoU 텍스트` 순으로 찍혀 있음.

| 이미지 | variant | 대상 | IoU 중앙 | 굵기 | 계열 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|
| 1.jpg | `font_match` | 10 | 0.483 |  |  |  | `results_font/font_match/vis/1.jpg` |
| 2.jpg | `font_match` | 10 | 0.229 |  |  |  | `results_font/font_match/vis/2.jpg` |
| 3.jpg | `font_match` | 0 | — |  |  |  | `results_font/font_match/vis/3.jpg` |
| 4.jpg | `font_match` | 11 | 0.434 |  |  |  | `results_font/font_match/vis/4.jpg` |
| 5.jpg | `font_match` | 2 | — |  |  |  | `results_font/font_match/vis/5.jpg` |
| 6.jpg | `font_match` | 12 | 0.614 |  |  |  | `results_font/font_match/vis/6.jpg` |
| 7.jpg | `font_match` | 4 | 0.325 |  |  |  | `results_font/font_match/vis/7.jpg` |
| 8.jpg | `font_match` | 12 | 0.422 |  |  |  | `results_font/font_match/vis/8.jpg` |
| 9.jpg | `font_match` | 15 | 0.437 |  |  |  | `results_font/font_match/vis/9.jpg` |
| 10.jpg | `font_match` | 15 | 0.279 |  |  |  | `results_font/font_match/vis/10.jpg` |
| 11.jpg | `font_match` | 8 | 0.495 |  |  |  | `results_font/font_match/vis/11.jpg` |
| 12.jpg | `font_match` | 9 | 0.359 |  |  |  | `results_font/font_match/vis/12.jpg` |

