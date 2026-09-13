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
| A000000213548_001.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_001.jpg` |
| A000000213548_001.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_001.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_gray` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_gray_lo` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_edge` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `template_edge_lo` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 1 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_002.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_003.jpg` |
| A000000213548_003.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_003.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_004.jpg` |
| A000000213548_004.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_004.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_005.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_006.jpg` |
| A000000213548_006.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_006.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_007.jpg` |
| A000000213548_007.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_007.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_008.jpg` |
| A000000213548_008.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_008.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_009.jpg` |
| A000000213548_009.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_009.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_010.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_011.jpg` |
| A000000213548_011.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_011.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_012.jpg` |
| A000000213548_012.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_012.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_013.jpg` |
| A000000213548_013.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_013.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_014.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_015.jpg` |
| A000000213548_015.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_015.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_016.jpg` |
| A000000213548_016.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_016.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_gray_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_017.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_gray` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_gray_lo` | 2 | 1 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/template_gray_lo/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_edge` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `template_edge_lo` | 1 | 1 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `b.clinicx` | `feature_orb` | 0 | 0 | 1 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000213548_018.jpg` |
| A000000219554_001.jpg | `goodal` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_gray_lo` | 1 | 0 | 0 | 0 | 다른 형태 페이지 로고 1건 잡음 · Claude 육안 판정 | `results/template_gray_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `template_edge_lo` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000219554_001.jpg` |
| A000000219554_002.jpg | `goodal` | `template_gray` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_gray_lo` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/template_gray_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_edge` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/template_edge/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `template_edge_lo` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/template_edge_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal` | `feature_orb` | 0 | 0 | 0 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000219554_002.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_gray` | 0 | 0 | 1 | 0 | Claude 육안 판정 | `results/template_gray/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_gray_lo` | 2 | 1 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/template_gray_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_edge` | 1 | 0 | 1 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/template_edge/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `template_edge_lo` | 9 | 1 | 0 | 5 | 패키지 로고 3건(라벨 소관) · 통과 박스 전수 확인 · Claude 육안 판정 | `results/template_edge_lo/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `goodal_serif` | `feature_orb` | 0 | 0 | 1 | 0 | Claude 육안 판정 | `results/feature_orb/vis/A000000219554_001.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_gray` | 0 | 0 | 1 | 0 | y36418 대형 페이지 로고 놓침 — 템플릿 배율 상한 2.0배로 크기 못 미침 · Claude 육안 판정 | `results/template_gray/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_gray_lo` | 3 | 0 | 1 | 0 | y36418 대형 페이지 로고 놓침 — 템플릿 배율 상한 2.0배로 크기 못 미침 · 다른 형태 페이지 로고 1건 잡음(템플릿 원본 자리) · 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/template_gray_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_edge` | 0 | 0 | 1 | 0 | y36418 대형 페이지 로고 놓침 — 템플릿 배율 상한 2.0배로 크기 못 미침 · Claude 육안 판정 | `results/template_edge/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `template_edge_lo` | 54 | 0 | 1 | 43 | y36418 대형 페이지 로고 놓침 — 템플릿 배율 상한 2.0배로 크기 못 미침 · 패키지 로고 11건(라벨 소관) · 통과 박스 전수 확인 · Claude 육안 판정 | `results/template_edge_lo/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `goodal_serif` | `feature_orb` | 0 | 0 | 1 | 0 | y36418 대형 페이지 로고 놓침 — 템플릿 배율 상한 2.0배로 크기 못 미침 · Claude 육안 판정 | `results/feature_orb/vis/A000000219554_002.jpg` |

## 4. 텍스트 대조 — 실행 조건

OCR은 텍스트 추출 확정 조건(`baseline`)을 **2000px 띠 · 300px 겹침**으로 돌려 합침. variant 공통 캐시 `results/_ocr/`.

| variant | 대조 방식 | 통과 | OCR (공통) | 대조 |
|---|---|---|---|---|
| `text_exact` | 정규화 텍스트 == 브랜드명 | 66 | 32.6s | 0.065s |
| `text_fuzzy` | 유사도 ≥ 0.8 | 70 | 32.6s | 0.049s |
| `text_contains` | 브랜드명 포함 (대조군) | 108 | 32.6s | 0.025s |
| `line_exact` | 줄 병합 후 == 브랜드명 | 56 | 32.6s | 0.215s |
| `block_exact` | 줄·문단 병합 후 == 브랜드명 | 54 | 32.6s | 0.245s |

브랜드명 사전 (**가정** — 페이지에서 확인한 표기)

| 상품 폴더 | 표기 |
|---|---|
| images_A000000213548 | `b.clinicx` · `비클리닉스` |
| images_A000000219554 | `goodal` · `구달` |
| images_A000000250199 | `celimax` · `셀리맥스` |

## 5. 텍스트 대조 — 통과 목록 (기계 집계)

통과 region 전체. 잘라 모은 대지는 `results/{variant}/hits.jpg`.

| 이미지 | y | 텍스트 | `text_exact` | `text_fuzzy` | `text_contains` | `line_exact` | `block_exact` |
|---|---|---|---|---|---|---|---|
| A000000213548_002.jpg | 162 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 653 | 비클리닉스 | ✓ | ✓ | ✓ |  |  |
| A000000213548_002.jpg | 1578 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 5565 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 6440 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 6737 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 9240 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_002.jpg | 11702 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_005.jpg | 431 | 비클리닉스만의 |  | ✓ 0.833 | ✓ |  |  |
| A000000213548_005.jpg | 622 | 비클리닉스만의 |  | ✓ 0.833 | ✓ |  |  |
| A000000213548_010.jpg | 2679 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_010.jpg | 3797 | 비클리닉스 | ✓ | ✓ | ✓ | ✓ |  |
| A000000213548_014.jpg | 867 | 비클리닉스 브라이트닝 세럼 론 코력팅 바디로션(농도 0.1%) 처리군에서는 2.839 Net AUC를 |  |  | ✓ |  |  |
| A000000213548_014.jpg | 1037 | 비클리닉스 브라이트닝 세럼 돈 코렉팅 바디로션(놓도0.1%) 처리군에서는2.839 Net AUC를 |  |  | ✓ |  |  |
| A000000213548_014.jpg | 1043 | 정상 성인30명(남2명 여28명 평규연형 422+4 8)을대상으로 "비클리닉스 |  |  | ✓ |  |  |
| A000000213548_014.jpg | 1074 | 비클리닉스브라이트닝 세럼 톤 코렉팅바디로션(농도 100%) 은 3371.07의 ORAC |  |  | ✓ |  |  |
| A000000213548_014.jpg | 1312 | 1)항산화테스트 완료[시험내용: 비클리닉스 브라이트닝 세럼 톤 코렉팅 바디로션의 항산화 in vitro test(ORAC assay)/ |  |  | ✓ |  |  |
| A000000213548_017.jpg | 867 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 5157 | 비클리닉스 | ✓ | ✓ | ✓ | ✓ |  |
| A000000213548_018.jpg | 5528 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 5715 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 6564 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 6575 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 6595 | bcinicx |  | ✓ 0.933 |  |  |  |
| A000000213548_018.jpg | 7292 | 1시험기관:엘리드\|비클리닉스 바디워시 바디로션 단독 및 병행 적용 팔꿈치 톤 균일도 4주 후 개선 평가 |  |  | ✓ |  |  |
| A000000213548_018.jpg | 7353 | 2LG생활건강 기술연구원\|비클리닉스 바디미스트 바디로션 복합사용 나이아신아마이드피부투과 비교평가 |  |  | ✓ |  |  |
| A000000213548_018.jpg | 7601 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 8284 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 8295 | b.clinicx | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000213548_018.jpg | 9358 | 비클리닉스 브라이트닝 세럼 톤 코렉팅 바디로션 |  |  | ✓ |  |  |
| A000000219554_001.jpg | 225 | 구달 맑은 어성초 진정 무기자차 선크림 50m1+1 기획 |  |  | ✓ |  |  |
| A000000219554_001.jpg | 525 | goodal | ✓ | ✓ | ✓ |  |  |
| A000000219554_001.jpg | 731 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_001.jpg | 734 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_001.jpg | 748 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_001.jpg | 758 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_001.jpg | 802 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_001.jpg | 1219 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 552 | 구달어성초 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 1754 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 2487 | 구달 맑은 어성초 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 3806 | 구달 맑은 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 3807 | 구달맑은 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 5279 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 8075 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 12747 | [구달 맑은 어성초 진정 무기자차 선크림의 외부 자극에 의한 피부 진정에 대한 인체적용시험] |  |  | ✓ |  |  |
| A000000219554_002.jpg | 13760 | [구달 맑은 어성초 진정 무기자차 선크림의 외부 자극에 의한 피부 진정에 대한 인체적용시험] |  |  | ✓ |  |  |
| A000000219554_002.jpg | 16492 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 27114 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 27142 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 27143 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28257 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28387 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28582 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28621 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28667 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28841 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 28988 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 29589 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 29610 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 29615 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 30426 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 30442 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 31239 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 31321 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 32304 | 구달은 자연과 사람을 생각하는 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 32930 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 32949 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 33080 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 33878 | Good all |  | ✓ 0.923 | ✓ |  |  |
| A000000219554_002.jpg | 33883 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 34099 | 구달은 자연과 사람이 공존하는 삶을 지향합니다. |  |  | ✓ |  |  |
| A000000219554_002.jpg | 35160 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 35435 | 구달의 Clear Clean Guide 기준으로 |  |  | ✓ |  |  |
| A000000219554_002.jpg | 36418 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000219554_002.jpg | 37169 | goodal | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000250199_001.jpg | 157 | 셀리맥스 | ✓ | ✓ | ✓ |  |  |
| A000000250199_001.jpg | 249 | 셀리맥스 | ✓ | ✓ | ✓ |  |  |
| A000000250199_001.jpg | 1165 | 셀리맥스 제품 구매 내역 캡쳐하기 |  |  | ✓ |  |  |
| A000000250199_001.jpg | 1722 | [UV 에이징/광노화]셀리맥스 브라이트닝 모공 |  |  | ✓ |  |  |
| A000000250199_001.jpg | 2668 | 셀리맥스 카카오 채널의 올영세일 구매인증 |  |  | ✓ |  |  |
| A000000250199_001.jpg | 4466 | 1.카카오톡에서 '셀리맥스'검색 →받은 상품권 확인 |  |  | ✓ |  |  |
| A000000250199_001.jpg | 4947 | ·본 이벤트는 셀리맥스 자체 이벤트입니다. |  |  | ✓ |  |  |
| A000000250199_001.jpg | 4977 | ·문의사항은 셀리맥스 고객센터를 통해 접수해 주세요. |  |  | ✓ |  |  |
| A000000250199_002.jpg | 86 | celimax× | ✓ | ✓ | ✓ |  |  |
| A000000250199_002.jpg | 1699 | celimax | ✓ | ✓ | ✓ |  |  |
| A000000250199_002.jpg | 1722 | celimax | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000250199_003.jpg | 247 | 셀리맥스 레티날 샷 부스터 |  |  | ✓ |  |  |
| A000000250199_004.jpg | 1109 | 제품을 오랫동안 사용한 사람으로써 사실셀리맥스의 레티날제품의 |  |  | ✓ |  |  |
| A000000250199_004.jpg | 3330 | *셀리맥스 공식몰 후기 발취 |  |  | ✓ |  |  |
| A000000250199_006.jpg | 416 | [셀리맥스 더 비타 A 레티날 샷 타이트닝 부스테]의 1회 사용 후 흡수율 증대 시험 |  |  | ✓ |  |  |
| A000000250199_007.jpg | 33 | [셀리맥스 더 비타 A레티날 샷 타이트닝 부스테의 1회 사용 후 흡수울증대 시험 |  |  | ✓ |  |  |
| A000000250199_007.jpg | 3065 | 셀리맥스 레티날 샷 부스터 |  |  | ✓ |  |  |
| A000000250199_007.jpg | 3913 | celimax | ✓ | ✓ | ✓ |  |  |
| A000000250199_008.jpg | 999 | celimax | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000250199_008.jpg | 1176 | celimax | ✓ | ✓ | ✓ |  |  |
| A000000250199_008.jpg | 4162 | 셀리맥스레티날 샷더 특별한 이유① |  |  | ✓ |  |  |
| A000000250199_008.jpg | 4718 | celimax | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000250199_008.jpg | 7222 | 셀리맥스레티날샷더 특별한 이유② |  |  | ✓ |  |  |
| A000000250199_009.jpg | 7850 | 셀리맥스 레티날 샷 타이트닝 부스터의 피부 3단 깊이(200,300,450mbar)탄력 개선에 대한 인체적용시험/ |  |  | ✓ |  |  |
| A000000250199_009.jpg | 9550 | 셀리맥스 레티날 샷 타이트닝 부스터의 피부 리프팅(눈꼬리,볼,입꼬리,턱리프팅)개선에 대한 인체적용시험/(주) |  |  | ✓ |  |  |
| A000000250199_011.jpg | 110 | 셀리맥스 레티날 샷 타이트닝 부스터의 피부 각질층 착색(턴오버개선)개선에 대한 인체 적용 시험 /(주)스킨메드 |  |  | ✓ |  |  |
| A000000250199_012.jpg | 45 | 셀리맥스 레티날 샷 타이트닝 부스터 사용 후 만족도 설문 평가/(주)스킨메드 임상시험센터 /2024.05.27~06.13 |  |  | ✓ |  |  |
| A000000250199_013.jpg | 1107 | celimax | ✓ | ✓ | ✓ |  |  |
| A000000250199_013.jpg | 2067 | "셀리맥스 더 비타 A 레티날 샷 타이트닝 부스터" |  |  | ✓ |  |  |
| A000000250199_013.jpg | 2342 | 위결과에따라(주)앱솔브랩에서의뢰한[셀리맥스더 비타A레티날샷 |  |  | ✓ |  |  |
| A000000250199_014.jpg | 5893 | celimax | ✓ | ✓ | ✓ | ✓ | ✓ |
| A000000250199_014.jpg | 8623 | "셀리맥스 레티놀 샷 타이트닝 세럼"과"셀리맥스 레티날 샷 타이트닝 부스터"의 병행 사용 시 눈가 주름,피부 모 |  |  | ✓ |  |  |
| A000000250199_014.jpg | 10942 | 셀리맥스 | ✓ | ✓ | ✓ |  |  |

## 6. 텍스트 대조 — 판정표

**채울 칸은 `찾음`·`놓침`·`오탐`.** 기준은 3장과 같음 — 페이지 디자인에 올린 로고만 셈. 패키지 위 로고는 세지 않음.

| 이미지 | variant | 통과 | 찾음 | 놓침 | 오탐 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|
| A000000213548_001.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_001.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_001.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_001.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_001.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_002.jpg | `text_exact` | 8 | 2 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `text_fuzzy` | 8 | 2 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `text_contains` | 8 | 2 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `line_exact` | 7 | 2 | 0 | 0 | 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000213548_002.jpg` |
| A000000213548_002.jpg | `block_exact` | 7 | 2 | 0 | 0 | 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000213548_002.jpg` |
| A000000213548_003.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_003.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_003.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_003.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_003.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_004.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_004.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_004.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_004.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_004.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_005.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_005.jpg | `text_fuzzy` | 2 | 0 | 0 | 2 | 오탐: `비클리닉스만의` · `비클리닉스만의` · Claude 육안 판정 | `results/text_fuzzy/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `text_contains` | 2 | 0 | 0 | 2 | 오탐: `비클리닉스만의` · `비클리닉스만의` · Claude 육안 판정 | `results/text_contains/vis/A000000213548_005.jpg` |
| A000000213548_005.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_005.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_006.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_006.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_006.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_006.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_006.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_007.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_007.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_007.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_007.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_007.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_008.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_008.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_008.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_008.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_008.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_009.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_009.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_009.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_009.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_009.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_010.jpg | `text_exact` | 2 | 0 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `text_fuzzy` | 2 | 0 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `text_contains` | 2 | 0 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `line_exact` | 2 | 0 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000213548_010.jpg` |
| A000000213548_010.jpg | `block_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000213548_010.jpg` |
| A000000213548_011.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_011.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_011.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_011.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_011.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_012.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_012.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_012.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_012.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_012.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_013.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_013.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_013.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_013.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_013.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_014.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_014.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_014.jpg | `text_contains` | 5 | 0 | 0 | 5 | 오탐: 브랜드명 포함 문장 5건 · Claude 육안 판정 | `results/text_contains/vis/A000000213548_014.jpg` |
| A000000213548_014.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_014.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_015.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_015.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_015.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_015.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_015.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_016.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_016.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_016.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_016.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_016.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000213548_017.jpg | `text_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `text_fuzzy` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `text_contains` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `line_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000213548_017.jpg` |
| A000000213548_017.jpg | `block_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000213548_017.jpg` |
| A000000213548_018.jpg | `text_exact` | 8 | 1 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `text_fuzzy` | 9 | 1 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 7건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `text_contains` | 11 | 1 | 0 | 4 | 오탐: 브랜드명 포함 문장 4건 · 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `line_exact` | 8 | 1 | 0 | 1 | 오탐: `비클리닉스` · 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000213548_018.jpg` |
| A000000213548_018.jpg | `block_exact` | 7 | 1 | 0 | 0 | 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000213548_018.jpg` |
| A000000219554_001.jpg | `text_exact` | 7 | 1 | 0 | 0 | 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `text_fuzzy` | 7 | 1 | 0 | 0 | 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `text_contains` | 8 | 1 | 0 | 1 | 오탐: `구달 맑은 어성초 진정 무기자차 선크` · 패키지 로고 6건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `line_exact` | 6 | 1 | 0 | 0 | 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000219554_001.jpg` |
| A000000219554_001.jpg | `block_exact` | 6 | 1 | 0 | 0 | 패키지 로고 5건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000219554_001.jpg` |
| A000000219554_002.jpg | `text_exact` | 28 | 2 | 0 | 0 | 패키지 로고 26건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `text_fuzzy` | 29 | 2 | 0 | 1 | 오탐: `Good all` · 패키지 로고 26건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `text_contains` | 38 | 2 | 0 | 10 | 오탐: 브랜드명 포함 문장 10건 · 패키지 로고 26건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `line_exact` | 28 | 2 | 0 | 0 | 패키지 로고 26건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000219554_002.jpg` |
| A000000219554_002.jpg | `block_exact` | 28 | 2 | 0 | 0 | 패키지 로고 26건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000219554_002.jpg` |
| A000000250199_001.jpg | `text_exact` | 2 | 0 | 0 | 2 | 오탐: `셀리맥스` · `셀리맥스` · Claude 육안 판정 | `results/text_exact/vis/A000000250199_001.jpg` |
| A000000250199_001.jpg | `text_fuzzy` | 2 | 0 | 0 | 2 | 오탐: `셀리맥스` · `셀리맥스` · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_001.jpg` |
| A000000250199_001.jpg | `text_contains` | 8 | 0 | 0 | 8 | 오탐: 브랜드명 포함 문장 8건 · Claude 육안 판정 | `results/text_contains/vis/A000000250199_001.jpg` |
| A000000250199_001.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_001.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_002.jpg | `text_exact` | 3 | 1 | 0 | 0 | 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000250199_002.jpg` |
| A000000250199_002.jpg | `text_fuzzy` | 3 | 1 | 0 | 0 | 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_002.jpg` |
| A000000250199_002.jpg | `text_contains` | 3 | 1 | 0 | 0 | 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000250199_002.jpg` |
| A000000250199_002.jpg | `line_exact` | 1 | 0 | 1 | 0 | 놓침 y86 — `celimax × OLIVE YOUNG` 공동 로고가 줄 병합으로 옆 글자와 묶임 · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000250199_002.jpg` |
| A000000250199_002.jpg | `block_exact` | 1 | 0 | 1 | 0 | 놓침 y86 — `celimax × OLIVE YOUNG` 공동 로고가 줄 병합으로 옆 글자와 묶임 · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000250199_002.jpg` |
| A000000250199_003.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_003.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_003.jpg | `text_contains` | 1 | 0 | 0 | 1 | 오탐: `셀리맥스 레티날 샷 부스터` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_003.jpg` |
| A000000250199_003.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_003.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_004.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_004.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_004.jpg | `text_contains` | 2 | 0 | 0 | 2 | 오탐: `제품을 오랫동안 사용한 사람으로써 사` · `*셀리맥스 공식몰 후기 발취` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_004.jpg` |
| A000000250199_004.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_004.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_005.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_005.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_005.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_005.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_005.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_006.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_006.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_006.jpg | `text_contains` | 1 | 0 | 0 | 1 | 오탐: `[셀리맥스 더 비타 A 레티날 샷 타` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_006.jpg` |
| A000000250199_006.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_006.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_007.jpg | `text_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000250199_007.jpg` |
| A000000250199_007.jpg | `text_fuzzy` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_007.jpg` |
| A000000250199_007.jpg | `text_contains` | 3 | 0 | 0 | 2 | 오탐: `[셀리맥스 더 비타 A레티날 샷 타이` · `셀리맥스 레티날 샷 부스터` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000250199_007.jpg` |
| A000000250199_007.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_007.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_008.jpg | `text_exact` | 3 | 0 | 0 | 0 | 패키지 로고 3건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000250199_008.jpg` |
| A000000250199_008.jpg | `text_fuzzy` | 3 | 0 | 0 | 0 | 패키지 로고 3건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_008.jpg` |
| A000000250199_008.jpg | `text_contains` | 5 | 0 | 0 | 2 | 오탐: `셀리맥스레티날 샷더 특별한 이유①` · `셀리맥스레티날샷더 특별한 이유②` · 패키지 로고 3건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000250199_008.jpg` |
| A000000250199_008.jpg | `line_exact` | 2 | 0 | 0 | 0 | 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000250199_008.jpg` |
| A000000250199_008.jpg | `block_exact` | 2 | 0 | 0 | 0 | 패키지 로고 2건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000250199_008.jpg` |
| A000000250199_009.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_009.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_009.jpg | `text_contains` | 2 | 0 | 0 | 2 | 오탐: `셀리맥스 레티날 샷 타이트닝 부스터의` · `셀리맥스 레티날 샷 타이트닝 부스터의` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_009.jpg` |
| A000000250199_009.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_009.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_010.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_010.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_010.jpg | `text_contains` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_010.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_010.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_011.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_011.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_011.jpg | `text_contains` | 1 | 0 | 0 | 1 | 오탐: `셀리맥스 레티날 샷 타이트닝 부스터의` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_011.jpg` |
| A000000250199_011.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_011.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_012.jpg | `text_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_012.jpg | `text_fuzzy` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_012.jpg | `text_contains` | 1 | 0 | 0 | 1 | 오탐: `셀리맥스 레티날 샷 타이트닝 부스터 ` · Claude 육안 판정 | `results/text_contains/vis/A000000250199_012.jpg` |
| A000000250199_012.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_012.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_013.jpg | `text_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000250199_013.jpg` |
| A000000250199_013.jpg | `text_fuzzy` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_013.jpg` |
| A000000250199_013.jpg | `text_contains` | 3 | 0 | 0 | 2 | 오탐: `"셀리맥스 더 비타 A 레티날 샷 타` · `위결과에따라(주)앱솔브랩에서의뢰한[셀` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000250199_013.jpg` |
| A000000250199_013.jpg | `line_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_013.jpg | `block_exact` | 0 | 0 | 0 | 0 | Claude 육안 판정 | — |
| A000000250199_014.jpg | `text_exact` | 2 | 0 | 0 | 1 | 오탐: `셀리맥스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_exact/vis/A000000250199_014.jpg` |
| A000000250199_014.jpg | `text_fuzzy` | 2 | 0 | 0 | 1 | 오탐: `셀리맥스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_fuzzy/vis/A000000250199_014.jpg` |
| A000000250199_014.jpg | `text_contains` | 3 | 0 | 0 | 2 | 오탐: `"셀리맥스 레티놀 샷 타이트닝 세럼"` · `셀리맥스` · 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/text_contains/vis/A000000250199_014.jpg` |
| A000000250199_014.jpg | `line_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/line_exact/vis/A000000250199_014.jpg` |
| A000000250199_014.jpg | `block_exact` | 1 | 0 | 0 | 0 | 패키지 로고 1건(라벨 소관) · Claude 육안 판정 | `results/block_exact/vis/A000000250199_014.jpg` |

## 7. 집계

| variant | 찾음 | 놓침 | 오탐 | 매칭 실패율 |
|---|---|---|---|---|
| `template_gray` | 2 | 2 | **0** | 50% |
| `template_gray_lo` | 3 | 1 | **0** | 25% |
| `template_edge` | 2 | 2 | **0** | 50% |
| `template_edge_lo` | 3 | 1 | **48** | 25% |
| `feature_orb` | 0 | 4 | **0** | 100% |
| `text_exact` | 7 | 0 | **6** | 0% |
| `text_fuzzy` | 7 | 0 | **9** | 0% |
| `text_contains` | 7 | 0 | **48** | 0% |
| `line_exact` | 6 | 1 | **2** | 14% |
| `block_exact` | 6 | 1 | **0** | 14% |

