# 제품 라벨 판정 — 실행 결과

> 이 파일은 `compare.py`가 생성함. **미탐·오탐 두 칸이 사람이 채우는 전부임.**
> 입력은 `block_role`의 `llm_assist` 블록. 계획은 `PoC_추가검증_계획.md`.
> **등급 산식 없음** — 미탐 1건 탈락 여부가 미결(계획 문서 미결 8)이라 두지 않음.

## 1. 실행 조건

| variant | 조건 | 블록 | 라벨 판정 | 비율 | 소요 | 비용 |
|---|---|---|---|---|---|---|
| `bg_texture` | `std=18.0` `ring=0.6` | 110 | 90 | 82% | 1.66s | 0 |
| `mask_overlap` | `cover=0.5` | 110 | 72 | 65% | 0.37s | 0 |
| `poly_skew` | `deg=2.0` `hdiff=0.06` | 110 | 55 | 50% | 0.31s | 0 |
| `role_ext` | `model=gemini-3.8-flash` `temperature=0` `image=False` `image_max_side=None` | 110 | 53 | 48% | 59.0s | $0.017 |
| `vlm_opus` | `model=claude-opus-5` `temperature=미지정(SDK 미지원)` `image=True` `image_max_side=1024` | 110 | 60 | 55% | 53.29s | $0.2128 |
| `vlm_relation` | `model=gemini-3.8-flash` `temperature=0` `image=True` `image_max_side=1024` | 110 | 60 | 55% | 41.85s | $0.027 |

## 2. 이미지별 라벨 판정 수 (기계 집계 — 정오 아님)

| 이미지 | 블록 | `bg_texture` | `mask_overlap` | `poly_skew` | `role_ext` | `vlm_opus` | `vlm_relation` |
|---|---|---|---|---|---|---|---|
| 1.jpg | 7 | 7 | 1 | 4 | 3 | 3 | 3 |
| 2.jpg | 7 | 6 | 3 | 3 | 3 | 3 | 3 |
| 3.jpg | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 4.jpg | 3 | 3 | 2 | 1 | 0 | 0 | 0 |
| 5.jpg | 17 | 8 | 12 | 11 | 16 | 16 | 16 |
| 6.jpg | 9 | 8 | 7 | 4 | 4 | 4 | 4 |
| 7.jpg | 7 | 6 | 5 | 4 | 5 | 5 | 5 |
| 8.jpg | 8 | 1 | 0 | 0 | 0 | 0 | 0 |
| 9.jpg | 12 | 12 | 9 | 5 | 4 | 4 | 4 |
| 10.jpg | 10 | 10 | 9 | 2 | 2 | 2 | 2 |
| 11.jpg | 23 | 22 | 20 | 17 | 13 | 20 | 20 |
| 12.jpg | 6 | 6 | 3 | 3 | 2 | 2 | 2 |

## 3. 합의도

블록마다 몇 개 variant가 `라벨`로 봤는지 센다. **갈리는 블록이 판정 대상임.**

| 이미지 | 전원 라벨 | 전원 배경 | **갈림** |
|---|---|---|---|
| 1.jpg | 1 | 0 | **6** |
| 2.jpg | 3 | 1 | **3** |
| 3.jpg | 1 | 0 | **0** |
| 4.jpg | 0 | 0 | **3** |
| 5.jpg | 7 | 1 | **9** |
| 6.jpg | 3 | 1 | **5** |
| 7.jpg | 4 | 1 | **2** |
| 8.jpg | 0 | 7 | **1** |
| 9.jpg | 4 | 0 | **8** |
| 10.jpg | 2 | 0 | **8** |
| 11.jpg | 8 | 0 | **15** |
| 12.jpg | 2 | 0 | **4** |
| **합계** | **35** | **11** | **64** |

## 4. 판정표

**채울 칸은 `미탐`·`오탐` 2개.** 블록·라벨 수는 코드가 채움.

- **미탐** = 제품 라벨인데 `배경`으로 본 블록 수. **복구 불가**
- **오탐** = 배경 텍스트인데 `라벨`로 본 블록 수. 번역 누락이나 검수 복구 가능

`vis/`에서 **빨강 = 라벨 판정 · 파랑 = 배경 판정**. 라벨 옆 숫자는 판정에 쓴 값임.

| 이미지 | variant | 블록 | 라벨 | 미탐 | 오탐 | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|
| 1.jpg | `bg_texture` | 7 | 7 |  |  |  | `results/bg_texture/vis/1.jpg` |
| 1.jpg | `mask_overlap` | 7 | 1 |  |  |  | `results/mask_overlap/vis/1.jpg` |
| 1.jpg | `poly_skew` | 7 | 4 |  |  |  | `results/poly_skew/vis/1.jpg` |
| 1.jpg | `role_ext` | 7 | 3 |  |  |  | `results/role_ext/vis/1.jpg` |
| 1.jpg | `vlm_opus` | 7 | 3 |  |  |  | `results/vlm_opus/vis/1.jpg` |
| 1.jpg | `vlm_relation` | 7 | 3 |  |  |  | `results/vlm_relation/vis/1.jpg` |
| 2.jpg | `bg_texture` | 7 | 6 |  |  |  | `results/bg_texture/vis/2.jpg` |
| 2.jpg | `mask_overlap` | 7 | 3 |  |  |  | `results/mask_overlap/vis/2.jpg` |
| 2.jpg | `poly_skew` | 7 | 3 |  |  |  | `results/poly_skew/vis/2.jpg` |
| 2.jpg | `role_ext` | 7 | 3 |  |  |  | `results/role_ext/vis/2.jpg` |
| 2.jpg | `vlm_opus` | 7 | 3 |  |  |  | `results/vlm_opus/vis/2.jpg` |
| 2.jpg | `vlm_relation` | 7 | 3 |  |  |  | `results/vlm_relation/vis/2.jpg` |
| 3.jpg | `bg_texture` | 1 | 1 |  |  |  | `results/bg_texture/vis/3.jpg` |
| 3.jpg | `mask_overlap` | 1 | 1 |  |  |  | `results/mask_overlap/vis/3.jpg` |
| 3.jpg | `poly_skew` | 1 | 1 |  |  |  | `results/poly_skew/vis/3.jpg` |
| 3.jpg | `role_ext` | 1 | 1 |  |  |  | `results/role_ext/vis/3.jpg` |
| 3.jpg | `vlm_opus` | 1 | 1 |  |  |  | `results/vlm_opus/vis/3.jpg` |
| 3.jpg | `vlm_relation` | 1 | 1 |  |  |  | `results/vlm_relation/vis/3.jpg` |
| 4.jpg | `bg_texture` | 3 | 3 |  |  |  | `results/bg_texture/vis/4.jpg` |
| 4.jpg | `mask_overlap` | 3 | 2 |  |  |  | `results/mask_overlap/vis/4.jpg` |
| 4.jpg | `poly_skew` | 3 | 1 |  |  |  | `results/poly_skew/vis/4.jpg` |
| 4.jpg | `role_ext` | 3 | 0 |  |  |  | `results/role_ext/vis/4.jpg` |
| 4.jpg | `vlm_opus` | 3 | 0 |  |  |  | `results/vlm_opus/vis/4.jpg` |
| 4.jpg | `vlm_relation` | 3 | 0 |  |  |  | `results/vlm_relation/vis/4.jpg` |
| 5.jpg | `bg_texture` | 17 | 8 |  |  |  | `results/bg_texture/vis/5.jpg` |
| 5.jpg | `mask_overlap` | 17 | 12 |  |  |  | `results/mask_overlap/vis/5.jpg` |
| 5.jpg | `poly_skew` | 17 | 11 |  |  |  | `results/poly_skew/vis/5.jpg` |
| 5.jpg | `role_ext` | 17 | 16 |  |  |  | `results/role_ext/vis/5.jpg` |
| 5.jpg | `vlm_opus` | 17 | 16 |  |  |  | `results/vlm_opus/vis/5.jpg` |
| 5.jpg | `vlm_relation` | 17 | 16 |  |  |  | `results/vlm_relation/vis/5.jpg` |
| 6.jpg | `bg_texture` | 9 | 8 |  |  |  | `results/bg_texture/vis/6.jpg` |
| 6.jpg | `mask_overlap` | 9 | 7 |  |  |  | `results/mask_overlap/vis/6.jpg` |
| 6.jpg | `poly_skew` | 9 | 4 |  |  |  | `results/poly_skew/vis/6.jpg` |
| 6.jpg | `role_ext` | 9 | 4 |  |  |  | `results/role_ext/vis/6.jpg` |
| 6.jpg | `vlm_opus` | 9 | 4 |  |  |  | `results/vlm_opus/vis/6.jpg` |
| 6.jpg | `vlm_relation` | 9 | 4 |  |  |  | `results/vlm_relation/vis/6.jpg` |
| 7.jpg | `bg_texture` | 7 | 6 |  |  |  | `results/bg_texture/vis/7.jpg` |
| 7.jpg | `mask_overlap` | 7 | 5 |  |  |  | `results/mask_overlap/vis/7.jpg` |
| 7.jpg | `poly_skew` | 7 | 4 |  |  |  | `results/poly_skew/vis/7.jpg` |
| 7.jpg | `role_ext` | 7 | 5 |  |  |  | `results/role_ext/vis/7.jpg` |
| 7.jpg | `vlm_opus` | 7 | 5 |  |  |  | `results/vlm_opus/vis/7.jpg` |
| 7.jpg | `vlm_relation` | 7 | 5 |  |  |  | `results/vlm_relation/vis/7.jpg` |
| 8.jpg | `bg_texture` | 8 | 1 |  |  |  | `results/bg_texture/vis/8.jpg` |
| 8.jpg | `mask_overlap` | 8 | 0 |  |  |  | `results/mask_overlap/vis/8.jpg` |
| 8.jpg | `poly_skew` | 8 | 0 |  |  |  | `results/poly_skew/vis/8.jpg` |
| 8.jpg | `role_ext` | 8 | 0 |  |  |  | `results/role_ext/vis/8.jpg` |
| 8.jpg | `vlm_opus` | 8 | 0 |  |  |  | `results/vlm_opus/vis/8.jpg` |
| 8.jpg | `vlm_relation` | 8 | 0 |  |  |  | `results/vlm_relation/vis/8.jpg` |
| 9.jpg | `bg_texture` | 12 | 12 |  |  |  | `results/bg_texture/vis/9.jpg` |
| 9.jpg | `mask_overlap` | 12 | 9 |  |  |  | `results/mask_overlap/vis/9.jpg` |
| 9.jpg | `poly_skew` | 12 | 5 |  |  |  | `results/poly_skew/vis/9.jpg` |
| 9.jpg | `role_ext` | 12 | 4 |  |  |  | `results/role_ext/vis/9.jpg` |
| 9.jpg | `vlm_opus` | 12 | 4 |  |  |  | `results/vlm_opus/vis/9.jpg` |
| 9.jpg | `vlm_relation` | 12 | 4 |  |  |  | `results/vlm_relation/vis/9.jpg` |
| 10.jpg | `bg_texture` | 10 | 10 |  |  |  | `results/bg_texture/vis/10.jpg` |
| 10.jpg | `mask_overlap` | 10 | 9 |  |  |  | `results/mask_overlap/vis/10.jpg` |
| 10.jpg | `poly_skew` | 10 | 2 |  |  |  | `results/poly_skew/vis/10.jpg` |
| 10.jpg | `role_ext` | 10 | 2 |  |  |  | `results/role_ext/vis/10.jpg` |
| 10.jpg | `vlm_opus` | 10 | 2 |  |  |  | `results/vlm_opus/vis/10.jpg` |
| 10.jpg | `vlm_relation` | 10 | 2 |  |  |  | `results/vlm_relation/vis/10.jpg` |
| 11.jpg | `bg_texture` | 23 | 22 |  |  |  | `results/bg_texture/vis/11.jpg` |
| 11.jpg | `mask_overlap` | 23 | 20 |  |  |  | `results/mask_overlap/vis/11.jpg` |
| 11.jpg | `poly_skew` | 23 | 17 |  |  |  | `results/poly_skew/vis/11.jpg` |
| 11.jpg | `role_ext` | 23 | 13 |  |  |  | `results/role_ext/vis/11.jpg` |
| 11.jpg | `vlm_opus` | 23 | 20 |  |  |  | `results/vlm_opus/vis/11.jpg` |
| 11.jpg | `vlm_relation` | 23 | 20 |  |  |  | `results/vlm_relation/vis/11.jpg` |
| 12.jpg | `bg_texture` | 6 | 6 |  |  |  | `results/bg_texture/vis/12.jpg` |
| 12.jpg | `mask_overlap` | 6 | 3 |  |  |  | `results/mask_overlap/vis/12.jpg` |
| 12.jpg | `poly_skew` | 6 | 3 |  |  |  | `results/poly_skew/vis/12.jpg` |
| 12.jpg | `role_ext` | 6 | 2 |  |  |  | `results/role_ext/vis/12.jpg` |
| 12.jpg | `vlm_opus` | 6 | 2 |  |  |  | `results/vlm_opus/vis/12.jpg` |
| 12.jpg | `vlm_relation` | 6 | 2 |  |  |  | `results/vlm_relation/vis/12.jpg` |

## 5. 집계

_판정 전_ — 채워진 칸 없음.

