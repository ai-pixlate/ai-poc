# B. 텍스트 추출 — variant 비교

> 자동 생성 파일. `compare.py` 재실행 시 덮어씀 — 등급은 여기 말고 PoC 문서에 옮겨 적을 것.

## 1. 실행 요약

| variant | 이미지 | 검출 영역 | 이미지당 평균 | 초기화(s) | 인식(s) | 조건 |
|---|---|---|---|---|---|---|
| `baseline` | 12 | 280 | 23.3 | 6.29 | 3.47 | lang=korean |
| `det_side_1280` *(제외)* | 12 | 280 | 23.3 | 2.69 | 3.11 | lang=korean, text_det_limit_side_len=1280, text_det_limit_type=max |
| `vl_spotting` *(제외)* | 12 | 239 | 19.9 | 8.45 | 1042.37 | prompt_label=spotting |

> 검출 영역 수는 많다고 좋은 게 아님. 과분할·오검출도 같이 늘어남. 시각화로 확인 필요.

## 2. 판정표 (육안 A/B/C — 빈 칸 채울 것)

- `사진영역` 열: 사진·그라데이션 배경 위 글자만 따로 본 등급. 해당 영역이 없으면 `-`
- 시각화 이미지를 띄워놓고 3장 텍스트와 대조하며 매길 것

**등급 기준** (PoC 문서 2.1)

| 등급 | 텍스트 열 | bbox 열 |
|---|---|---|
| **A** | 대부분 정확, 오탈자 거의 없음 — 그대로 번역에 넘겨도 됨 | 텍스트 영역을 정확히 감쌈 |
| **B** | 일부 오탈자 있으나 1차 검수로 고칠 수 있는 수준 | 약간 어긋나지만 마스크 확장으로 흡수 가능 |
| **C** | 오탈자 과다하거나 인식 실패 — 사용 불가 | 크게 빗나가거나 영역 누락 |
| **-** | 사진·그라데이션 배경 위 글자가 없는 이미지 (`사진영역` 두 열 전용) | 〃 |

> A와 B를 가르는 선은 **1차 검수로 고칠 수 있는가**. C는 손보느니 다시 뽑는 게 빠른 상태.
> 집계는 A+B를 묶어 세므로 A/B 구분보다 **B와 C의 경계**가 결과를 좌우한다.

**판정 대상에서 제외된 variant** — 실행 결과는 1·3장에 남아 있으니 참고용으로 볼 것

| variant | 제외 사유 |
|---|---|
| `det_side_1280` | baseline과 인식 결과 완전 동일 — 판정 불필요 (2026-08-20) |
| `vl_spotting` | 12장 1042초로 baseline의 약 300배 — 속도상 채택 제외 (2026-08-20) |

| 이미지 | variant | 영역 | 텍스트 | bbox | 사진영역 텍스트 | 사진영역 bbox | 비고 | 시각화 |
|---|---|---|---|---|---|---|---|---|
| 1.jpg | `baseline` | 13 |   |   |   |   |   | [보기](results/baseline/vis/1.jpg) |
| 2.jpg | `baseline` | 18 |   |   |   |   |   | [보기](results/baseline/vis/2.jpg) |
| 3.jpg | `baseline` | 5 |   |   |   |   |   | [보기](results/baseline/vis/3.jpg) |
| 4.jpg | `baseline` | 11 |   |   |   |   |   | [보기](results/baseline/vis/4.jpg) |
| 5.jpg | `baseline` | 38 |   |   |   |   |   | [보기](results/baseline/vis/5.jpg) |
| 6.jpg | `baseline` | 28 |   |   |   |   |   | [보기](results/baseline/vis/6.jpg) |
| 7.jpg | `baseline` | 34 |   |   |   |   |   | [보기](results/baseline/vis/7.jpg) |
| 8.jpg | `baseline` | 14 |   |   |   |   |   | [보기](results/baseline/vis/8.jpg) |
| 9.jpg | `baseline` | 39 |   |   |   |   |   | [보기](results/baseline/vis/9.jpg) |
| 10.jpg | `baseline` | 17 |   |   |   |   |   | [보기](results/baseline/vis/10.jpg) |
| 11.jpg | `baseline` | 46 |   |   |   |   |   | [보기](results/baseline/vis/11.jpg) |
| 12.jpg | `baseline` | 17 |   |   |   |   |   | [보기](results/baseline/vis/12.jpg) |

**집계** — 위 판정표에서 자동 계산됨. 직접 채우지 말 것

| variant | 텍스트 | bbox | 사진영역 텍스트 | 사진영역 bbox | 70% 통과 |
|---|---|---|---|---|---|
| `baseline` | 판정 0/12 | 판정 0/12 | 판정 0/12 | 판정 0/12 | 판정 미완 |

> `70% 통과`는 네 열이 **모두** 70% 이상일 때만 O. 한 열이라도 미달이면 X — 어느 축이 걸렸는지는 왼쪽 칸으로 확인할 것.

## 3. 인식 텍스트 나란히 보기

괄호 안은 인식 신뢰도. 행 번호는 시각화 이미지의 빨간 번호와 같다.
**variant마다 검출 영역이 다르므로 같은 행이 같은 위치를 뜻하지는 않는다.** 세로로 훑어 읽을 것.

### 1.jpg

[baseline 시각화](results/baseline/vis/1.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/1.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/1.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | My (0.99) | My (0.99) | My First Collagen |
| 2 | First (0.91) | First (0.91) | 1+1 |
| 3 | Collagen (0.99) | Collagen (0.99) | 귀캡 귀링 |
| 4 | 1+1 (1.00) | 1+1 (1.00) | BIODADE |
| 5 | 키캡키링 (0.98) | 키캡키링 (0.98) | 선착순! |
| 6 | 선착순! (1.00) | 선착순! (1.00) | BIODADE |
| 7 | Biodan (0.96) | Biodan (0.96) | 오이취 |
| 8 | Buodance (0.76) | Buodance (0.76) | WON |
| 9 | 오이쉬 (0.84) | 오이쉬 (0.84) | 원이 PICK! 1등 화잘먹 모공 세럼 |
| 10 | 윈이 PICK!1등 (0.96) | 윈이 PICK!1등 (0.96) |  |
| 11 | 화잘먹 (0.99) | 화잘먹 (0.99) |  |
| 12 | 모공 (1.00) | 모공 (1.00) |  |
| 13 | 세럼 (0.99) | 세럼 (0.99) |  |

### 2.jpg

[baseline 시각화](results/baseline/vis/2.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/2.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/2.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | 콜라겐 펩타이드 세럼 구매하면 (0.96) | 콜라겐 펩타이드 세럼 구매하면 (0.96) | 올라겐 펩타이드 세럼 구매하면 |
| 2 | 리센느 원이 오이쉬스 (0.90) | 리센느 원이 오이쉬스 (0.90) | 리셀느 윈이 오이쉬 키캡 키링 증정! |
| 3 | 키캡 키링 증정! (0.95) | 키캡 키링 증정! (0.95) | 오이쉬 |
| 4 | 오이쉬 (0.91) | 오이쉬 (0.91) | Biodance |
| 5 | Biodance (1.00) | Biodance (1.00) | WONI |
| 6 | × (0.60) | × (0.60) | Biodance |
| 7 | WONI (0.99) | WONI (0.99) | COLLAGEN |
| 8 | Biodance (1.00) | Biodance (1.00) | PORE PERFECTING |
| 9 | COULAGEN (0.90) | COULAGEN (0.90) | PEPTIDE SERUM |
| 10 | PEPTIDE SERUM (0.96) | PEPTIDE SERUM (0.96) | Perf. Marketing. |
| 11 | Siog. Pen (0.43) | Siog. Pen (0.43) | NET 1.01 fl.oz. (30 ml) |
| 12 | 키캡키링 (1.00) | 키캡키링 (1.00) | Smoothie Fishing |
| 13 | 선착순! (1.00) | 선착순! (1.00) | 키캡키링 |
| 14 | ·증정 기간:8/19~ 8/23 (선착순 증정, 재고 소진 시 종료) (0.96) | ·증정 기간:8/19~ 8/23 (선착순 증정, 재고 소진 시 종료) (0.96) | 선착순! |
| 15 | ·증정품은 한정 수량으로 선착순 지급되며 조기 소진될 수 있습니다. (0.99) | ·증정품은 한정 수량으로 선착순 지급되며 조기 소진될 수 있습니다. (0.99) | - 증정 기간: 8/19 ~ 8/23 (선착순 증정, 재고 소진 시 종료) |
| 16 | ·정확한 증정품 내역은 주문 후 [주문상세내역]에서 확인 가능합니다. (0.98) | ·정확한 증정품 내역은 주문 후 [주문상세내역]에서 확인 가능합니다. (0.98) | - 증정품은 한정 수량으로 선착순 지급되며 조기 소진될 수 있습니다. |
| 17 | ·오늘 드림/픽업 서비스 주문 건은 증정품 제공되지 않습니다 (0.98) | ·오늘 드림/픽업 서비스 주문 건은 증정품 제공되지 않습니다 (0.98) | - 정확한 증정품 내역은 주문 후 [주문상세내역]에서 확인 가능합니다. |
| 18 | •반품 시 증정품도 함께 반품해주셔야 합니다. (0.98) | •반품 시 증정품도 함께 반품해주셔야 합니다. (0.98) | - 오늘 드림/픽업 서비스 주문 건은 증정품 제공되지 않습니다 |
| 19 |  |  | - 반품 시 증정품도 함께 반품해주셔야 합니다. |

### 3.jpg

[baseline 시각화](results/baseline/vis/3.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/3.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/3.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | Biodanee (0.91) | Biodanee (0.91) | Biodance |
| 2 | PORE PERFEETIN (0.89) | PORE PERFEETIN (0.89) | PORT PERFECTING |
| 3 | PEPTIDE SEELA (0.89) | PEPTIDE SEELA (0.89) | COLLAGEN |
| 4 | COLLAGEN (0.99) | COLLAGEN (0.99) | PEPTIDE SBUM |
| 5 | NET (0.98) | NET (0.98) | NET 1.0 |

### 4.jpg

[baseline 시각화](results/baseline/vis/4.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/4.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/4.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | My (1.00) | My (1.00) | My First |
| 2 | First (0.88) | First (0.88) | Collagen |
| 3 | Collagen (0.90) | Collagen (0.90) | 지금부터 시작하는 원이의 콜라겐 |
| 4 | 지금부터 시작하는 운 (0.95) | 지금부터 시작하는 운 (0.95) | 빛나는 원이와 함께 |
| 5 | 원이의 콜라겐 (0.95) | 원이의 콜라겐 (0.95) | 매일 가볍게 쌓아가는 |
| 6 | 빛나는 원이와 함께 (0.97) | 빛나는 원이와 함께 (0.97) | 쫀쭙한 화잘먹 루틴! |
| 7 | 매일 가볍게 (0.98) | 매일 가볍게 (0.98) |  |
| 8 | 쌓아가는 (1.00) | 쌓아가는 (1.00) |  |
| 9 | 쏜쏜한 (0.58) | 쏜쏜한 (0.58) |  |
| 10 | 화잘먹 (1.00) | 화잘먹 (1.00) |  |
| 11 | 루틴! (1.00) | 루틴! (1.00) |  |

### 5.jpg

[baseline 시각화](results/baseline/vis/5.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/5.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/5.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | Blodanee (0.76) | Blodanee (0.76) | Biodance |
| 2 | BIO COLLAGEN (0.99) | BIO COLLAGEN (0.99) | BIO COLLAGEN |
| 3 | Biodance (1.00) | Biodance (1.00) | REAL DEEP MASK |
| 4 | REAL DEEP MASK (0.98) | REAL DEEP MASK (0.98) | Biodance |
| 5 | FACIAL, SHEST MABK (0.77) | FACIAL, SHEST MABK (0.77) | FACIAL SHEET MASK |
| 6 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 7 | COLLAGEN MASK (0.99) | COLLAGEN MASK (0.99) | COLLAGEN MASK |
| 8 | PORE PERFECTING (0.96) | PORE PERFECTING (0.96) | PORE PERFECTING |
| 9 | TO FOAM CLEANSER (0.99) | TO FOAM CLEANSER (0.99) | PORE PERFECTING |
| 10 | OOLLAGEN (0.89) | OOLLAGEN (0.89) | TO FOAM CLEANSER |
| 11 | PEPTIDE CREAM (0.98) | PEPTIDE CREAM (0.98) | PEPTIDE CREAM |
| 12 | Biodance (0.94) | Biodance (0.94) | COLLAGEN |
| 13 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 14 | NET 1.69 11.02.(50m0 (0.81) | NET 1.69 11.02.(50m0 (0.81) | Biodance |
| 15 | COLLAGEN (1.00) | COLLAGEN (1.00) | NET 1.69 fl.oz. (50 ml) |
| 16 | CLEANSING OIL (0.99) | CLEANSING OIL (0.99) | COLLAGEN |
| 17 |  (0.00) |  (0.00) | CLEANSING OIL |
| 18 | Biodance (1.00) | Biodance (1.00) | (2) |
| 19 | tuoo Pon semerc, fimurg (0.47) | tuoo Pon semerc, fimurg (0.47) | Biodance |
| 20 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 21 | NET 5.07 11.0z, (150 m) (0.84) | NET 5.07 11.0z, (150 m) (0.84) | NET 5.07 fl.oz. (150 ml) |
| 22 | COLLAGEN (0.96) | COLLAGEN (0.96) | Net Wt. 1.19 oz (34 g) |
| 23 | NET WT 118o2(349) (0.83) | NET WT 118o2(349) (0.83) | NET WT. 1.19 oz (34 g) |
| 24 | GEL TONER PADS (0.98) | GEL TONER PADS (0.98) | COLLAGEN |
| 25 | COL PERFECTING (0.88) | COL PERFECTING (0.88) | PORE PERFECTING |
| 26 | COILAGCN (0.81) | COILAGCN (0.81) | GEL TONER PADS |
| 27 | a.Daop Cean (0.64) | a.Daop Cean (0.64) | COLLAGEN |
| 28 | L0z.200mi (0.71) | L0z.200mi (0.71) | $  1.02 \times 100 \, ml  $ |
| 29 | UTIDESERUM (0.90) | UTIDESERUM (0.90) | PEPTIDE SERUM |
| 30 | 00500s (0.35) | 00500s (0.35) |  |
| 31 | NET WT 4.80 02(140) (0.69) | NET WT 4.80 02(140) (0.69) |  |
| 32 | Siodance (0.91) | Siodance (0.91) |  |
| 33 | COLLAGEN PEPHIDE EYEIUO (0.83) | COLLAGEN PEPHIDE EYEIUO (0.83) |  |
| 34 | ROCHSPOURLESYIUXAR (0.74) | ROCHSPOURLESYIUXAR (0.74) |  |
| 35 | (30m) (0.80) | (30m) (0.80) |  |
| 36 | h (0.23) | h (0.23) |  |
| 37 | Biodance (1.00) | Biodance (1.00) |  |
| 38 | XWONI (0.93) | XWONI (0.93) |  |

### 6.jpg

[baseline 시각화](results/baseline/vis/6.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/6.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/6.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | Biodance \| OLIVE YOUNG (0.93) | Biodance \| OLIVE YOUNG (0.93) | Biodance \| OLIVE YOUNG |
| 2 | 1+1 (0.98) | 1+1 (0.98) | 1+1 덕남기획 |
| 3 | 더블 (1.00) | 더블 (1.00) | 닌독 한정 기획 |
| 4 | 기획 (1.00) | 기획 (1.00) | ONLY |
| 5 | 단독 (1.00) | 단독 (1.00) | 올리브영 |
| 6 | 한정 (1.00) | 한정 (1.00) | 닌독기획 |
| 7 | 기획 (1.00) | 기획 (1.00) | Biodance |
| 8 | ONLY (1.00) | ONLY (1.00) | x2 |
| 9 | 올리브영 (1.00) | 올리브영 (1.00) | 모공 쪽쪽 |
| 10 | 단독기획 (1.00) | 단독기획 (1.00) | Biodance |
| 11 | 용량 (1.00) | 용량 (1.00) | 30 ml |
| 12 | UP (1.00) | UP (1.00) | 콜라겐 모공 세럼 |
| 13 | Biodance (1.00) | Biodance (1.00) | 30 ml |
| 14 | 글 쪼쯤 (0.48) | 글 쪼쯤 (0.48) | Biodance |
| 15 | x2 (0.84) | x2 (0.84) | Biodance |
| 16 | 모공 (1.00) | 모공 (1.00) | PORE PERFECTING |
| 17 | Biodance (1.00) | Biodance (1.00) | COLLAGEN |
| 18 | 콜라겐 (1.00) | 콜라겐 (1.00) |  |
| 19 | 세럼 (1.00) | 세럼 (1.00) |  |
| 20 | 30ml (0.97) | 30ml (0.97) |  |
| 21 | 콜라겐 모공 세럼 (0.95) | 콜라겐 모공 세럼 (0.95) |  |
| 22 | 포어 퍼펙팅 콜라겐 펩타이드 세럼 (0.98) | 포어 퍼펙팅 콜라겐 펩타이드 세럼 (0.98) |  |
| 23 | 한정 더블 기획 (0.97) | 한정 더블 기획 (0.97) |  |
| 24 | 30ml (0.97) | 30ml (0.97) |  |
| 25 | Biodance (1.00) | Biodance (1.00) |  |
| 26 | 포어 퍼펙팅 콜라겐 펩타이드 세럼 (0.95) | 포어 퍼펙팅 콜라겐 펩타이드 세럼 (0.95) |  |
| 27 | Biodance (1.00) | Biodance (1.00) |  |
| 28 | PORE PERFECTING (0.97) | PORE PERFECTING (0.97) |  |

### 7.jpg

[baseline 시각화](results/baseline/vis/7.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/7.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/7.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | PORE PERFECIING (0.97) | PORE PERFECIING (0.97) | PORE PERFECTING |
| 2 | COLLAGEN (1.00) | COLLAGEN (1.00) | COLLABEN |
| 3 | PEPTIDE SERUM (0.98) | PEPTIDE SERUM (0.98) | PEPTIDE SERUM |
| 4 | siodance (0.96) | siodance (0.96) | PEPTIDE SERUM |
| 5 | PEPTIDE SERUM (0.98) | PEPTIDE SERUM (0.98) | Biodance |
| 6 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 7 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 8 | siodance (0.97) | siodance (0.97) | PORE PERFECTING |
| 9 | Pore Perfecting, (1.00) | Pore Perfecting, (1.00) | PORE PERFECTING |
| 10 | PORE PERFECTING (0.98) | PORE PERFECTING (0.98) | Pore Perfecting, |
| 11 | PORE PERFECTING (0.98) | PORE PERFECTING (0.98) | PORE PERFECTING |
| 12 | PEPECING (0.47) | PEPECING (0.47) | Pore Perfecting, |
| 13 | LAGEN (0.54) | LAGEN (0.54) | COLLABEN |
| 14 | Pore Perfecting, (0.97) | Pore Perfecting, (0.97) | COLLABEN |
| 15 | COLLAGEN (1.00) | COLLAGEN (1.00) | PEPTIDE SERUM |
| 16 | COLLAGEN (1.00) | COLLAGEN (1.00) | Smoothing, Firming |
| 17 | SL (0.43) | SL (0.43) | PEPTIDE SERUM |
| 18 | Smoothing,Firming (1.00) | Smoothing,Firming (1.00) | PEPTIDE SERUM |
| 19 | PEPTIDE SERUM (0.99) | PEPTIDE SERUM (0.99) | Smoothing, Firming |
| 20 | PEPTIDE SERUM (0.99) | PEPTIDE SERUM (0.99) | NET 1.01 fl.oz. (30 ml) |
| 21 | Smoothing, Firming (0.99) | Smoothing, Firming (0.99) | NET 1.01 fl.oz. (30 ml) |
| 22 | NET 1.01 f1.0z. (30ml) (0.90) | NET 1.01 f1.0z. (30ml) (0.90) | NET 1.01 fl.oz. (30 ml) |
| 23 | NET 1.01 f1.0Z. (30 m) (0.90) | NET 1.01 f1.0Z. (30 m) (0.90) | NET 1.01 fl.oz. (30 ml) |
| 24 | Pore Perlecting. (0.90) | Pore Perlecting. (0.90) | NET 1.0 |
| 25 | 1toe.00m (0.41) | 1toe.00m (0.41) |  |
| 26 | Poce Pertectier (0.79) | Poce Pertectier (0.79) |  |
| 27 | Smoothing. Firming (0.95) | Smoothing. Firming (0.95) |  |
| 28 | semoothing.F (0.88) | semoothing.F (0.88) |  |
| 29 | NET 1.01 11.02. (30m (0.88) | NET 1.01 11.02. (30m (0.88) |  |
| 30 | NET 1.0 (0.98) | NET 1.0 (0.98) |  |
| 31 | 1억장* (1.00) | 1억장* (1.00) |  |
| 32 | 콜라겐 팩 노하우를 그대로! (0.99) | 콜라겐 팩 노하우를 그대로! (0.99) |  |
| 33 | [본품]포어 퍼펙팅콜라겐펩타이드세럼30m +30ml (0.93) | [본품]포어 퍼펙팅콜라겐펩타이드세럼30m +30ml (0.93) |  |
| 34 | *2021.04-2025.08 바이오던스 바이오 콜라겐 리얼 딥 마스크 생산 실적 기준 (0.94) | *2021.04-2025.08 바이오던스 바이오 콜라겐 리얼 딥 마스크 생산 실적 기준 (0.94) |  |

### 8.jpg

[baseline 시각화](results/baseline/vis/8.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/8.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/8.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | Biodance (1.00) | Biodance (1.00) | Biodance |
| 2 | BIODANCE'S SAFETY (0.97) | BIODANCE'S SAFETY (0.97) | BIODANCE'S SAFETY |
| 3 | 바이오던스만의 균형있는피부를위한고집 (0.95) | 바이오던스만의 균형있는피부를위한고집 (0.95) | 바이오던스만의 균형있는 피부를 위한 고집 |
| 4 | 25 (1.00) | 25 (1.00) | 25 |
| 5 |  (0.00) |  (0.00) | 無 |
| 6 | FREE (1.00) | FREE (1.00) | FREE |
| 7 | 19가지의심성분 (1.00) | 19가지의심성분 (1.00) | 19가지 의심 성분 |
| 8 | 식약처 고시알레르기 (0.95) | 식약처 고시알레르기 (0.95) | 식약처 고시 알레르기 |
| 9 | 피부저자극 (0.99) | 피부저자극 (0.99) | 피부 저자극 |
| 10 | 무첨가* (1.00) | 무첨가* (1.00) | 무첨가* |
| 11 | 유발25가지무첨가 (0.99) | 유발25가지무첨가 (0.99) | 유발 25가지 무첨가 |
| 12 | 테스트완료 (0.99) | 테스트완료 (0.99) | 테스트 완료 |
| 13 | ·항목 페녹시에탄음 벤질알코을 벤즈익애씨드,클로페네신 디아줄리디닐우레아 소르빅애씨드, 벤조테는-3 어소프로팔알코음 트리에탄옵아민, 벤잘코눔클로라이드(C12C14) (0.82) | ·항목 페녹시에탄음 벤질알코을 벤즈익애씨드,클로페네신 디아줄리디닐우레아 소르빅애씨드, 벤조테는-3 어소프로팔알코음 트리에탄옵아민, 벤잘코눔클로라이드(C12C14) (0.82) | *창목: 페낙시에탄올, 변질말코콜, 변조익에씨드, 클로페네신, 디아쯤리디닐우레아, 소르벅에씨드, 벤조페낙-3, 이소프로필말코콜, 트리에탄율아인, 변질코닐클로라이드(C12,C14), |
| 14 | 부틸레이티드하이드록시루엔 프로필렌클라이플 테칠파라벤 에침파라벤,이소프로필파라벤,프로필파라벤 이소부틸따라벤,부틸파라벤,p-하이드목시벤조익에씨드 (0.90) | 부틸레이티드하이드록시루엔 프로필렌클라이플 테칠파라벤 에침파라벤,이소프로필파라벤,프로필파라벤 이소부틸따라벤,부틸파라벤,p-하이드목시벤조익에씨드 (0.90) | 부팀레이드하이드목시품주멘, 프로핑랜글라이콜, 매칭따라벤, 에칠따라벤, 이소프로핀파라벤, 프로핀파라벤, 이소부팀파라벤, 부팀파라벤, p-하이드목시벤조익에씨드 |

### 9.jpg

[baseline 시각화](results/baseline/vis/9.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/9.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/9.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | 역대최대 한정기획 (0.98) | 역대최대 한정기획 (0.98) | ONLY |
| 2 | ONLY (1.00) | ONLY (1.00) | 을리브영 |
| 3 | 더블X더블 (0.95) | 더블X더블 (0.95) | 단독기획 |
| 4 | 올리브영 (1.00) | 올리브영 (1.00) | + |
| 5 | 단독기획 (1.00) | 단독기획 (1.00) | ansing |
| 6 | 블랙 (1.00) | 블랙 (1.00) | oil &amp; |
| 7 | + (0.99) | + (0.99) | blackhead |
| 8 | ansing (1.00) | ansing (1.00) | cleansing |
| 9 |  (0.00) |  (0.00) | PHA |
| 10 | & (0.99) | & (0.99) | oil &amp; |
| 11 | 헤드 (1.00) | 헤드 (1.00) | $  30 \, ml / 1.01 \, fl.oz.  $ |
| 12 | blackhead (0.99) | blackhead (0.99) | blackhead |
| 13 | cleansing (1.00) | cleansing (1.00) | cleansing |
| 14 | PHA (0.88) | PHA (0.88) | oil &amp; |
| 15 | oil & (0.92) | oil & (0.92) | Hanskin |
| 16 | + (1.00) | + (1.00) | blackhead |
| 17 | blackhead (1.00) | blackhead (1.00) | PHA |
| 18 | leansing (0.96) | leansing (0.96) | cleansing |
| 19 | oil& (0.78) | oil& (0.78) | 200 ml / 6.76 fl.oz. |
| 20 | O (0.54) | O (0.54) | PHA |
| 21 | Hanskin (1.00) | Hanskin (1.00) | oil & |
| 22 | blackhead (1.00) | blackhead (1.00) | blackhead |
| 23 | PHA (1.00) | PHA (1.00) | Hanskin |
| 24 | cleansing (1.00) | cleansing (1.00) | Hanskin |
| 25 | 200 ml/6.76 f.0z. (0.87) | 200 ml/6.76 f.0z. (0.87) | 1 + 1 + 1 + 1 + 1 |
| 26 | PHA (0.98) | PHA (0.98) | Hanskin |
| 27 | oil& (0.88) | oil& (0.88) |  |
| 28 | 민감 (1.00) | 민감 (1.00) |  |
| 29 | blackhead (1.00) | blackhead (1.00) |  |
| 30 | PHA (1.00) | PHA (1.00) |  |
| 31 | Hanskin (1.00) | Hanskin (1.00) |  |
| 32 | 피부 (1.00) | 피부 (1.00) |  |
| 33 | 200md/6.76 R.0z. (0.79) | 200md/6.76 R.0z. (0.79) |  |
| 34 | + (1.00) | + (1.00) |  |
| 35 | 저자극 (1.00) | 저자극 (1.00) |  |
| 36 | Hanskin (1.00) | Hanskin (1.00) |  |
| 37 | 11 (0.94) | 11 (0.94) |  |
| 38 | Hanskin (1.00) | Hanskin (1.00) |  |
| 39 | +1+1 (0.96) | +1+1 (0.96) |  |

### 10.jpg

[baseline 시각화](results/baseline/vis/10.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/10.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/10.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | 50ml (0.99) | 50ml (0.99) | 50 ml |
| 2 | 추가 증정 (0.96) | 추가 증정 (0.96) | 추가 증정 |
| 3 | ONLY (1.00) | ONLY (1.00) | ONLY |
| 4 | AM (0.49) | AM (0.49) | 올리브영 |
| 5 | 올리브영 (1.00) | 올리브영 (1.00) | LEMON CHUNG CLEAN |
| 6 | 단독기획 (1.00) | 단독기획 (1.00) | 단독기획 |
| 7 | LEMON CHUNG CLEA (0.92) | LEMON CHUNG CLEA (0.92) | 피부자극 |
| 8 | 피부자극 (1.00) | 피부자극 (1.00) | 0.00 |
| 9 | 0.00 (1.00) | 0.00 (1.00) | 리뷰이벤트 |
| 10 | 리뷰이벤트 (1.00) | 리뷰이벤트 (1.00) | + 3,000원 |
| 11 | 3,000원 (1.00) | 3,000원 (1.00) | 상한빈PICK |
| 12 | 성한빈PICK (0.99) | 성한빈PICK (0.99) | OLIVE YOUNG |
| 13 | OLIVE YOUNG (0.99) | OLIVE YOUNG (0.99) | 1등 팩클렌저 |
| 14 | 1등 (1.00) | 1등 (1.00) | *2026.01.30 09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 |
| 15 | 팩클렌저 (1.00) | 팩클렌저 (1.00) | *2026.06.29 08시, 09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 |
| 16 | *2026.01.30 09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 (0.97) | *2026.01.30 09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 (0.97) |  |
| 17 | *2026.06.29 08시,09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 (0.97) | *2026.06.29 08시,09시 기준 올리브영 온라인몰 클렌징 부문 판매 랭킹 1위 (0.97) |  |

### 11.jpg

[baseline 시각화](results/baseline/vis/11.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/11.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/11.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | Slow (0.99) | Slow (0.99) | Slow |
| 2 | MEDIHEAL (1.00) | MEDIHEAL (1.00) | MEDIHEAL |
| 3 | Aging (1.00) | Aging (1.00) | Aging |
| 4 | PRODUCT KEY FACTS (0.99) | PRODUCT KEY FACTS (0.99) | PRODUCT KEY FACTS |
| 5 | AGCRPTONTME (0.85) | AGCRPTONTME (0.85) | DESCRIPTION TIME |
| 6 | 30mn (0.80) | 30mn (0.80) | HYPER COLLAGEN |
| 7 | HYPER COLLAGEN (0.98) | HYPER COLLAGEN (0.98) | HYPER COLLAGEN |
| 8 | 1100 (1.00) | 1100 (1.00) | 붙이는 콜라겐 엠플 |
| 9 | 붙이는 콜라겐 앰플 (0.95) | 붙이는 콜라겐 앰플 (0.95) | 20 min |
| 10 | 2toUn (0.52) | 2toUn (0.52) | 1100 |
| 11 | Uosone Daree (0.73) | Uosone Daree (0.73) | $  \alpha \beta \gamma \delta \epsilon \zeta \eta \theta \iota \kappa \lambda \mu \nu \xi \pi \rho \sigma \tau \upsilon \phi \chi \psi \omega  $ |
| 12 | LovMeoir Otge (0.56) | LovMeoir Otge (0.56) | 2 hours |
| 13 | 291m (0.67) | 291m (0.67) | Low-Molecular Culling |
| 14 | 500 0 (0.52) | 500 0 (0.52) | Low-Molecular Culling |
| 15 | 0c % (0.68) | 0c % (0.68) | Low-Molecular Culling |
| 16 | #탄력리프팅#모공채움 (0.96) | #탄력리프팅#모공채움 (0.96) | 201 nm |
| 17 | PRODUCT KEY FACTS (0.96) | PRODUCT KEY FACTS (0.96) | Collagen's Purity |
| 18 | MYPER PORN (0.74) | MYPER PORN (0.74) | 300 cm |
| 19 | 10101 (1.00) | 10101 (1.00) | 50.2% |
| 20 | RRA (0.42) | RRA (0.42) | #듣긴프닝 #모공채움 |
| 21 | IDUCT KEY FACTS (0.90) | IDUCT KEY FACTS (0.90) | PRODUCT KEY FACTS |
| 22 | HYPER COLLAGEN (0.99) | HYPER COLLAGEN (0.99) | HYPER PORN |
| 23 | OUCTKEYRACTS (0.89) | OUCTKEYRACTS (0.89) | 10101 |
| 24 | LOW-MOLECULAR LIPOSOME (0.99) | LOW-MOLECULAR LIPOSOME (0.99) | 100% |
| 25 | Becomes transparent in 2 hours (0.92) | Becomes transparent in 2 hours (0.92) | 100% |
| 26 | 이디협 하이퍼 클라견아스크 (0.80) | 이디협 하이퍼 클라견아스크 (0.80) | 100% |
| 27 | Becomes transparent in 2 hours (0.92) | Becomes transparent in 2 hours (0.92) | 100% |
| 28 | 한정기획 (0.99) | 한정기획 (0.99) | HYPER COLLAGEN |
| 29 | 8+1 (1.00) | 8+1 (1.00) | 100% |
| 30 |  (0.00) |  (0.00) | 100% |
| 31 | 추가증정! (0.92) | 추가증정! (0.92) | 100% |
| 32 | 이이 (0.49) | 이이 (0.49) | 100% |
| 33 |  (0.00) |  (0.00) | LOW-MOLECULAR LIPOSOME |
| 34 | 6 (0.47) | 6 (0.47) | HYPER CHINA  LOW-MOLECULAR LIPOSOME |
| 35 | XR SOUTONFONAL (0.77) | XR SOUTONFONAL (0.77) | 100% |
| 36 | OUR (0.98) | OUR (0.98) | Becomes transparent in 2 hours |
| 37 | SOLUTION,FOR ALL (0.92) | SOLUTION,FOR ALL (0.92) | 100% |
| 38 | FOR BEST RESULTS (0.96) | FOR BEST RESULTS (0.96) | 100% |
| 39 | USE UNTIL THE GEL MASK IS CLEAR IN COLCR (0.95) | USE UNTIL THE GEL MASK IS CLEAR IN COLCR (0.95) | 100% |
| 40 | OURSOLUTION, FOR ALL (0.95) | OURSOLUTION, FOR ALL (0.95) | 100% |
| 41 | 8 (1.00) | 8 (1.00) | 100% |
| 42 | 5 (0.98) | 5 (0.98) | 100% |
| 43 | + (0.95) | + (0.95) | 100% |
| 44 | 단독 (1.00) | 단독 (1.00) | 100% |
| 45 | 기획 (1.00) | 기획 (1.00) | 100% |
| 46 | 올리브영 (1.00) | 올리브영 (1.00) | 100% |
| 47 |  |  | 8+1 |
| 48 |  |  | 8+1 |
| 49 |  |  | 추가증정! |
| 50 |  |  | 8+1 |
| 51 |  |  | 8+1 |
| 52 |  |  | 8+1 |
| 53 |  |  | OUR SOLUTION, FOR ALL |
| 54 |  |  | OUR SOLUTION, FOR ALL |
| 55 |  |  | OUR SOLUTION, FOR ALL |
| 56 |  |  | FOR BEST RESULTS. |
| 57 |  |  | USE UNTIL THE GEL MASK IS CLEAR IN COLOR. |
| 58 |  |  | OUR SOLUTION, FOR ALL |
| 59 |  |  | 8+1 |
| 60 |  |  | 올리브엉 단독 기획 |

### 12.jpg

[baseline 시각화](results/baseline/vis/12.jpg) · [det_side_1280 시각화](results/det_side_1280/vis/12.jpg) · [vl_spotting 시각화](results/vl_spotting/vis/12.jpg)

| # | `baseline` | `det_side_1280` | `vl_spotting` |
|---|---|---|---|
| 1 | My (1.00) | My (1.00) | My First Collagen |
| 2 | First (1.00) | First (1.00) | 101 |
| 3 | Collagen (0.98) | Collagen (0.98) | Pick |
| 4 | 원이 (1.00) | 원이 (1.00) | +10 ml |
| 5 | Pick (1.00) | Pick (1.00) | Biodance |
| 6 | +10ml (0.97) | +10ml (0.97) | Biodance |
| 7 | Biodance (1.00) | Biodance (1.00) | PORE PERFECTING |
| 8 | Biodance (1.00) | Biodance (1.00) | PORE PERFECTING |
| 9 | PORE PERFECTING (0.98) | PORE PERFECTING (0.98) | COLLAGEN |
| 10 | COLLAGEN (1.00) | COLLAGEN (1.00) | PEPTIDE CREAM |
| 11 | 콜라겐 (1.00) | 콜라겐 (1.00) | COLLAGEN |
| 12 | 수분 (1.00) | 수분 (1.00) | PEPTIDE CREAM |
| 13 | 크림 (1.00) | 크림 (1.00) | 골라겐 수분 크림 |
| 14 | PEPTIDE CREAM (0.97) | PEPTIDE CREAM (0.97) | NET 0.50 fl.oz. (50 ml) |
| 15 | Pore Perfectinp. (0.92) | Pore Perfectinp. (0.92) | NET 1.69 fl.oz. (50 ml) |
| 16 | mggthing, Finming (0.81) | mggthing, Finming (0.81) |  |
| 17 | NET 1.69 f1.0z. (50 ml) (0.92) | NET 1.69 f1.0z. (50 ml) (0.92) |  |
