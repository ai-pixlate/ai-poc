# 제품 라벨 판정 — 골든 샘플 섹션 판정

> `compare.py --sample golden`이 생성함. 재실행해도 **채운 칸은 보존함.**
> 계획 `PoC_골든샘플_재실행_계획.md` 단계 3. 입력은 단계 2 `llm_assist` 블록 + 섹션 이미지(긴 변 1024px). 12장 결과(`summary.md`)는 건드리지 않음.

## 1. 실행 조건

| 항목 | 값 |
|---|---|
| 조건 | `model=gemini-3.8-flash` `temperature=0` `image=True` `image_max_side=1024` `bbox=섹션 원본 좌표(확정 조건 그대로 — 축소 비율 환산 안 함)` |
| 섹션 · 호출 | 102 · 102 (캐시 0) |
| 블록 · 라벨 판정 | 803 · **95** (12%) |
| 토큰 · 비용 | in 216,415 · out 14,612 · $0.2171 |
| 소요 · 응답 적용 실패 | 440.18s · 0 |

## 2. 판정표 (섹션 단위 — 블록 번호로 채움)

대지 `results/golden/vlm_relation/board/{섹션}.jpg` — 왼쪽 빨강 = 라벨 판정 · 파랑 = 배경 판정, 오른쪽 블록 번호별 판정·텍스트.

- **미탐 번호** = 제품 라벨인데 `배경`으로 본 블록 번호 · **복구 불가**
- **오탐 번호** = 배경 텍스트인데 `라벨`로 본 블록 번호 · 검수 복구 가능
- 쉼표로 구분(`3, 7`). **없으면 `-`** — 빈 칸은 미판정으로 봄
- **컷 유형** = 겹친 패키지 · 라벨 없음 · 단일 제품 등(확인 항목 — 조건부 종결 사유). 해당 없으면 `-`
- 비텍스트 오검출 블록(얼굴·아이콘 등)은 배경으로 보는 게 맞음 — 라벨로 봤으면 오탐
- 판정 주체: Claude 1차 전수 확인(비고에 "Claude 육안 판정") → 예람님 검토. **이 판정이 라벨 정답지가 됨**
- 글자 없는 섹션(단계 1 `-`): `A000000213548_003_001`, `A000000213548_007_001` — 비텍스트 블록만 있음

| 섹션 | 블록 | 라벨 판정 | 보낸 크기 | 미탐 번호 | 오탐 번호 | 컷 유형 | 비고 | 대지 |
|---|---|---|---|---|---|---|---|---|
| A000000213548_001_001 | 2 | 0 | 1000×455 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_001_001.jpg) |
| A000000213548_002_001 | 9 | 1 | 409×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_001.jpg) |
| A000000213548_002_002 | 2 | 0 | 1000×436 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_002.jpg) |
| A000000213548_002_003 | 4 | 0 | 1000×975 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_003.jpg) |
| A000000213548_002_004 | 9 | 0 | 480×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_004.jpg) |
| A000000213548_002_005 | 7 | 2 | 695×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_005.jpg) |
| A000000213548_002_006 | 4 | 0 | 1000×583 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_006.jpg) |
| A000000213548_002_007 | 8 | 1 | 482×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_007.jpg) |
| A000000213548_002_008 | 10 | 1 | 373×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_008.jpg) |
| A000000213548_002_009 | 2 | 0 | 1000×448 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_002_009.jpg) |
| A000000213548_003_001 | 1 | 0 | 1000×540 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_003_001.jpg) |
| A000000213548_004_001 | 9 | 0 | 582×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_004_001.jpg) |
| A000000213548_005_001 | 6 | 1 | 502×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_005_001.jpg) |
| A000000213548_006_001 | 2 | 0 | 1000×679 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_006_001.jpg) |
| A000000213548_007_001 | 1 | 0 | 1000×710 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_007_001.jpg) |
| A000000213548_008_001 | 6 | 0 | 650×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_008_001.jpg) |
| A000000213548_009_001 | 5 | 0 | 1000×710 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_009_001.jpg) |
| A000000213548_010_001 | 8 | 0 | 524×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_010_001.jpg) |
| A000000213548_010_002 | 13 | 1 | 373×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_010_002.jpg) |
| A000000213548_011_001 | 4 | 0 | 595×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_011_001.jpg) |
| A000000213548_012_001 | 5 | 0 | 1000×830 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_012_001.jpg) |
| A000000213548_013_001 | 9 | 4 | 436×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_013_001.jpg) |
| A000000213548_014_001 | 29 | 0 | 635×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_014_001.jpg) |
| A000000213548_014_002 | 6 | 0 | 589×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_014_002.jpg) |
| A000000213548_015_001 | 4 | 0 | 1000×800 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_015_001.jpg) |
| A000000213548_016_001 | 1 | 0 | 1000×403 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_016_001.jpg) |
| A000000213548_017_001 | 4 | 1 | 1000×960 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_017_001.jpg) |
| A000000213548_018_001 | 2 | 0 | 1000×629 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_001.jpg) |
| A000000213548_018_002 | 6 | 0 | 1000×948 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_002.jpg) |
| A000000213548_018_003 | 13 | 0 | 340×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_003.jpg) |
| A000000213548_018_004 | 22 | 5 | 388×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_004.jpg) |
| A000000213548_018_005 | 2 | 0 | 1000×569 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_005.jpg) |
| A000000213548_018_006 | 38 | 2 | 343×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000213548_018_006.jpg) |
| A000000219554_001_001 | 20 | 13 | 753×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_001_001.jpg) |
| A000000219554_002_001 | 12 | 1 | 321×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_001.jpg) |
| A000000219554_002_002 | 13 | 2 | 388×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_002.jpg) |
| A000000219554_002_003 | 7 | 1 | 344×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_003.jpg) |
| A000000219554_002_004 | 10 | 0 | 739×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_004.jpg) |
| A000000219554_002_005 | 3 | 0 | 1000×506 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_005.jpg) |
| A000000219554_002_006 | 9 | 0 | 454×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_006.jpg) |
| A000000219554_002_007 | 11 | 0 | 1000×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_007.jpg) |
| A000000219554_002_008 | 3 | 0 | 693×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_008.jpg) |
| A000000219554_002_009 | 6 | 3 | 511×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_009.jpg) |
| A000000219554_002_010 | 9 | 0 | 542×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_010.jpg) |
| A000000219554_002_011 | 10 | 0 | 893×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_011.jpg) |
| A000000219554_002_012 | 3 | 0 | 567×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_012.jpg) |
| A000000219554_002_013 | 4 | 0 | 914×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_013.jpg) |
| A000000219554_002_014 | 2 | 0 | 987×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_014.jpg) |
| A000000219554_002_015 | 5 | 0 | 1000×824 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_015.jpg) |
| A000000219554_002_016 | 3 | 0 | 958×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_016.jpg) |
| A000000219554_002_017 | 12 | 10 | 362×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_017.jpg) |
| A000000219554_002_018 | 9 | 3 | 1000×879 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_018.jpg) |
| A000000219554_002_019 | 13 | 4 | 1000×825 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_019.jpg) |
| A000000219554_002_020 | 9 | 2 | 1000×763 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_020.jpg) |
| A000000219554_002_021 | 10 | 4 | 502×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_021.jpg) |
| A000000219554_002_022 | 17 | 1 | 389×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_022.jpg) |
| A000000219554_002_023 | 4 | 3 | 761×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000219554_002_023.jpg) |
| A000000250199_001_001 | 4 | 0 | 830×446 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_001_001.jpg) |
| A000000250199_001_002 | 6 | 3 | 830×546 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_001_002.jpg) |
| A000000250199_001_003 | 11 | 0 | 404×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_001_003.jpg) |
| A000000250199_001_004 | 8 | 0 | 830×419 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_001_004.jpg) |
| A000000250199_001_005 | 9 | 0 | 518×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_001_005.jpg) |
| A000000250199_002_001 | 10 | 4 | 484×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_002_001.jpg) |
| A000000250199_003_001 | 3 | 0 | 830×641 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_003_001.jpg) |
| A000000250199_004_001 | 14 | 0 | 220×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_004_001.jpg) |
| A000000250199_005_001 | 13 | 0 | 830×760 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_005_001.jpg) |
| A000000250199_006_001 | 6 | 0 | 830×643 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_006_001.jpg) |
| A000000250199_006_002 | 2 | 0 | 830×524 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_006_002.jpg) |
| A000000250199_006_003 | 2 | 0 | 830×733 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_006_003.jpg) |
| A000000250199_006_004 | 2 | 0 | 830×483 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_006_004.jpg) |
| A000000250199_007_001 | 13 | 0 | 314×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_007_001.jpg) |
| A000000250199_007_002 | 7 | 3 | 528×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_007_002.jpg) |
| A000000250199_008_001 | 6 | 1 | 347×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_001.jpg) |
| A000000250199_008_002 | 6 | 0 | 549×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_002.jpg) |
| A000000250199_008_003 | 7 | 1 | 698×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_003.jpg) |
| A000000250199_008_004 | 14 | 0 | 457×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_004.jpg) |
| A000000250199_008_005 | 10 | 0 | 347×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_005.jpg) |
| A000000250199_008_006 | 2 | 0 | 830×446 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_008_006.jpg) |
| A000000250199_009_001 | 11 | 0 | 633×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_001.jpg) |
| A000000250199_009_002 | 3 | 0 | 830×899 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_002.jpg) |
| A000000250199_009_003 | 6 | 0 | 495×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_003.jpg) |
| A000000250199_009_004 | 3 | 0 | 812×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_004.jpg) |
| A000000250199_009_005 | 13 | 0 | 549×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_005.jpg) |
| A000000250199_009_006 | 6 | 0 | 478×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_006.jpg) |
| A000000250199_009_007 | 7 | 0 | 553×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_009_007.jpg) |
| A000000250199_010_001 | 4 | 0 | 830×777 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_010_001.jpg) |
| A000000250199_010_002 | 2 | 0 | 830×437 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_010_002.jpg) |
| A000000250199_010_003 | 2 | 0 | 830×450 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_010_003.jpg) |
| A000000250199_010_004 | 5 | 0 | 830×935 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_010_004.jpg) |
| A000000250199_011_001 | 18 | 0 | 284×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_011_001.jpg) |
| A000000250199_012_001 | 1 | 0 | 800×220 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_012_001.jpg) |
| A000000250199_013_001 | 4 | 3 | 543×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_013_001.jpg) |
| A000000250199_013_002 | 10 | 0 | 512×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_013_002.jpg) |
| A000000250199_014_001 | 8 | 2 | 474×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_001.jpg) |
| A000000250199_014_002 | 23 | 0 | 331×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_002.jpg) |
| A000000250199_014_003 | 26 | 3 | 189×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_003.jpg) |
| A000000250199_014_004 | 6 | 1 | 718×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_004.jpg) |
| A000000250199_014_005 | 5 | 0 | 830×704 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_005.jpg) |
| A000000250199_014_006 | 12 | 1 | 259×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_006.jpg) |
| A000000250199_014_007 | 1 | 0 | 830×444 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_007.jpg) |
| A000000250199_014_008 | 10 | 7 | 830×722 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_008.jpg) |
| A000000250199_014_009 | 5 | 0 | 692×1024 |   |   |   |   | [보기](results/golden/vlm_relation/board/A000000250199_014_009.jpg) |

## 3. 집계

_판정 전_ — 채워진 행 없음.

