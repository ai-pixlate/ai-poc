# 브랜드 로고 제외 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **자기 브랜드 페이지의 찾음·놓침·오탐만 사람이 채움.**
> ⚠️ 등록 로고 파일이 없어 **페이지에서 잘라낸 임시 템플릿**을 씀. 원래 자리는 평가에서 뺌.

## 1. 실행 조건

| variant | 방식 | 임계 | 소요 |
|---|---|---|---|
| `template_gray` | 다중 스케일 밝기 매칭(NCC) | 점수 ≥ 0.8 | 134.58s |
| `template_gray_lo` | 밝기 매칭 · **임계만 낮춤** | 점수 ≥ 0.6 | 347.52s |
| `template_edge` | 윤곽선끼리 매칭 | 점수 ≥ 0.45 | 182.44s |
| `template_edge_lo` | 윤곽선 매칭 · **임계만 낮춤** | 점수 ≥ 0.3 | 362.35s |
| `feature_orb` | ORB 특징점 + 호모그래피 | 인라이어 ≥ 12 | 6.11s |

템플릿 — `b.clinicx` · `goodal` · `goodal_serif`. 배율 0.4~2.0배. `results/_templates/`에 저장.

## 2. 확정 오탐 (기계 집계)

**남의 브랜드 페이지에서 임계를 넘은 매칭.** 정답 없이도 오탐임이 확실함.

| variant | `b.clinicx` 확정 오탐 | `goodal` 확정 오탐 | `goodal_serif` 확정 오탐 | 합계 | 자기 페이지 통과 |
|---|---|---|---|---|---|
| `template_gray` | 0 | 0 | 0 | **0** | 2 |
| `template_gray_lo` | 0 | 0 | 0 | **0** | 10 |
| `template_edge` | 0 | 0 | 0 | **0** | 3 |
| `template_edge_lo` | 0 | 0 | 248 | **248** | 66 |
| `feature_orb` | 0 | 0 | 0 | **0** | 0 |

**확정 오탐이 0이 아닌 variant는 탈락 후보임** — 판정 기준상 오탐이 놓침보다 나쁨.

## 3. 판정표 — 자기 브랜드 페이지

**채울 칸은 `찾음`·`놓침`·`오탐` 3개.** `vis/`에서 초록=임계 통과, 주황=미달, 회색=템플릿 원래 자리.

- **찾음** = 페이지 디자인에 올린 로고를 초록 박스로 잡은 수
- **놓침** = 실제 로고인데 초록 박스가 없는 수
- **오탐** = 로고가 아닌 곳에 초록 박스가 있는 수
- 제품 패키지 위 로고는 **세지 않음** — 라벨 판정 소관

| 이미지 | 로고 | variant | 통과 | 찾음 | 놓침 | 오탐 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|
| A000000213548_001.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_001.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_gray` | 1 |  |  |  |  | `results/template_gray/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_gray_lo` | 1 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_edge` | 1 |  |  |  |  | `results/template_edge/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_edge_lo` | 1 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_002.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_003.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_004.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_005.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_006.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_007.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_008.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_009.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_010.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_011.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_012.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_013.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_014.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_015.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_016.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_gray_lo` | 0 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_017.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_gray` | 1 |  |  |  |  | `results/template_gray/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_gray_lo` | 2 |  |  |  |  | `results/template_gray_lo/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_edge` | 1 |  |  |  |  | `results/template_edge/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_edge_lo` | 1 |  |  |  |  | `results/template_edge_lo/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000213548_018.jpg` |
| A000000219554_001.jpg | `goodal` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_gray_lo` | 1 |  |  |  |  | `results/template_gray_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_edge_lo` | 0 |  |  |  |  | `results/template_edge_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000219554_001.jpg` |
| A000000219554_002.jpg | `goodal` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_gray_lo` | 1 |  |  |  |  | `results/template_gray_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_edge_lo` | 1 |  |  |  |  | `results/template_edge_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000219554_002.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_gray_lo` | 2 |  |  |  |  | `results/template_gray_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_edge` | 1 |  |  |  |  | `results/template_edge/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_edge_lo` | 9 |  |  |  |  | `results/template_edge_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000219554_001.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_gray` | 0 |  |  |  |  | `results/template_gray/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_gray_lo` | 3 |  |  |  |  | `results/template_gray_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_edge` | 0 |  |  |  |  | `results/template_edge/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_edge_lo` | 54 |  |  |  |  | `results/template_edge_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `feature_orb` | 0 |  |  |  |  | `results/feature_orb/vis/A000000219554_002.jpg` |

## 4. 집계

_판정 전_ — 채워진 칸 없음.

