# E1. 원문 지우기 — 후보 비교

> 자동 생성 파일. `compare.py` 재실행 시 덮어씀.

## 1. 실행 요약

- 마스크: `d15` — B baseline poly를 글자 높이의 **15%**(최소 3px)만큼 팽창
- 대상: 12장, 총 280개 영역

| variant | 엔진 | 이미지 | 소요(s) | 파라미터 |
|---|---|---|---|---|
| `lama` | iopaint | 12 | 149.04 | model=lama, device=cpu |
| `ns` | opencv | 12 | 1.46 | radius=3 |
| `powerpaint_remove` | iopaint | 2 | 97.4 | model=Sanster/PowerPaint-V1-stable-diffusion-inpainting, device=cuda, config={'powerpaint_task': 'object-remove', 'prompt': '', 'negative_prompt': 'text, letters, watermark, writing, signature', 'sd_steps': 50, 'sd_guidance_scale': 7.5, 'sd_seed': 42} |
| `pp_conservative` | iopaint | 3 | 63.75 | model=Sanster/PowerPaint-V1-stable-diffusion-inpainting, device=cuda, config={'prompt': '', 'negative_prompt': 'text, letters, words, characters, typography, writing, watermark, signature, logo, label, symbols, pattern, texture', 'sd_steps': 20, 'sd_guidance_scale': 1.5, 'sd_match_histograms': True, 'sd_seed': 42, 'powerpaint_task': 'object-remove'} |
| `pp_fullctx` | iopaint | 3 | 63.99 | model=Sanster/PowerPaint-V1-stable-diffusion-inpainting, device=cuda, config={'prompt': '', 'negative_prompt': 'text, letters, words, characters, typography, writing, watermark, signature, logo, label, symbols, pattern, texture', 'sd_steps': 20, 'sd_guidance_scale': 1.5, 'sd_match_histograms': True, 'sd_seed': 42, 'powerpaint_task': 'object-remove', 'hd_strategy': 'Resize'} |
| `sd15` | iopaint | 2 | 627.78 | model=runwayml/stable-diffusion-inpainting, device=cuda |
| `sd15_conservative` | iopaint | 3 | 234.15 | model=runwayml/stable-diffusion-inpainting, device=cuda, config={'prompt': '', 'negative_prompt': 'text, letters, words, characters, typography, writing, watermark, signature, logo, label, symbols, pattern, texture', 'sd_steps': 20, 'sd_guidance_scale': 1.5, 'sd_match_histograms': True, 'sd_seed': 42, 'hd_strategy': 'Resize'} |
| `telea` | opencv | 12 | 1.53 | radius=3 |

## 2. 판정표 (육안 A/B/C — 빈 칸 채울 것)

**등급 기준** (PoC 문서 2.2)

| 등급 | 기준 |
|---|---|
| **A** | 원문 흔적 없음, 배경과 자연스럽게 이어짐 |
| **B** | 자세히 봐야 티가 남 — 번역문을 얹으면 가려질 수준, 검수로 흡수 가능 |
| **C** | 원문이 읽히거나 왜곡·얼룩이 눈에 띔 |

> **Go/No-Go**: 사진·그라데이션 배경 영역의 A+B 비율 70% 이상 → 사진 배경도 MVP 포함.

| 이미지 | variant | 등급 | 비고 | 대조 |
|---|---|---|---|---|
| 1.jpg | `lama` | A |  | [보기](results/compare/1.jpg) |
| 1.jpg | `ns` | C |  | [보기](results/compare/1.jpg) |
| 1.jpg | `powerpaint_remove` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `pp_conservative` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `pp_fullctx` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `sd15` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `sd15_conservative` |   |   | [보기](results/compare/1.jpg) |
| 1.jpg | `telea` | C |  | [보기](results/compare/1.jpg) |
| 2.jpg | `lama` | A |  | [보기](results/compare/2.jpg) |
| 2.jpg | `ns` | C |  | [보기](results/compare/2.jpg) |
| 2.jpg | `powerpaint_remove` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `pp_conservative` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `pp_fullctx` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `sd15` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `sd15_conservative` |   |   | [보기](results/compare/2.jpg) |
| 2.jpg | `telea` | C |  | [보기](results/compare/2.jpg) |
| 3.jpg | `lama` | A |  | [보기](results/compare/3.jpg) |
| 3.jpg | `ns` | C |  | [보기](results/compare/3.jpg) |
| 3.jpg | `powerpaint_remove` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `pp_conservative` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `pp_fullctx` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `sd15` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `sd15_conservative` |   |   | [보기](results/compare/3.jpg) |
| 3.jpg | `telea` | C |  | [보기](results/compare/3.jpg) |
| 4.jpg | `lama` | C |  | [보기](results/compare/4.jpg) |
| 4.jpg | `ns` | C |  | [보기](results/compare/4.jpg) |
| 4.jpg | `powerpaint_remove` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `pp_conservative` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `pp_fullctx` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `sd15` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `sd15_conservative` |   |   | [보기](results/compare/4.jpg) |
| 4.jpg | `telea` | B |  | [보기](results/compare/4.jpg) |
| 5.jpg | `lama` | A |  | [보기](results/compare/5.jpg) |
| 5.jpg | `ns` | B |  | [보기](results/compare/5.jpg) |
| 5.jpg | `powerpaint_remove` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `pp_conservative` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `pp_fullctx` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `sd15` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `sd15_conservative` |   |   | [보기](results/compare/5.jpg) |
| 5.jpg | `telea` | B |  | [보기](results/compare/5.jpg) |
| 6.jpg | `lama` | B |  | [보기](results/compare/6.jpg) |
| 6.jpg | `ns` | C |  | [보기](results/compare/6.jpg) |
| 6.jpg | `powerpaint_remove` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `pp_conservative` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `pp_fullctx` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `sd15` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `sd15_conservative` |   |   | [보기](results/compare/6.jpg) |
| 6.jpg | `telea` | C |  | [보기](results/compare/6.jpg) |
| 7.jpg | `lama` | A |  | [보기](results/compare/7.jpg) |
| 7.jpg | `ns` | C |  | [보기](results/compare/7.jpg) |
| 7.jpg | `powerpaint_remove` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `pp_conservative` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `pp_fullctx` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `sd15` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `sd15_conservative` |   |   | [보기](results/compare/7.jpg) |
| 7.jpg | `telea` | C |  | [보기](results/compare/7.jpg) |
| 8.jpg | `lama` | A |  | [보기](results/compare/8.jpg) |
| 8.jpg | `ns` | A |  | [보기](results/compare/8.jpg) |
| 8.jpg | `powerpaint_remove` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `pp_conservative` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `pp_fullctx` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `sd15` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `sd15_conservative` |   |   | [보기](results/compare/8.jpg) |
| 8.jpg | `telea` | A |  | [보기](results/compare/8.jpg) |
| 9.jpg | `lama` | C |  | [보기](results/compare/9.jpg) |
| 9.jpg | `ns` | C |  | [보기](results/compare/9.jpg) |
| 9.jpg | `powerpaint_remove` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `pp_conservative` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `pp_fullctx` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `sd15` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `sd15_conservative` |   |   | [보기](results/compare/9.jpg) |
| 9.jpg | `telea` | C |  | [보기](results/compare/9.jpg) |
| 10.jpg | `lama` | A |  | [보기](results/compare/10.jpg) |
| 10.jpg | `ns` | C |  | [보기](results/compare/10.jpg) |
| 10.jpg | `powerpaint_remove` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `pp_conservative` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `pp_fullctx` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `sd15` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `sd15_conservative` |   |   | [보기](results/compare/10.jpg) |
| 10.jpg | `telea` | C |  | [보기](results/compare/10.jpg) |
| 11.jpg | `lama` | A |  | [보기](results/compare/11.jpg) |
| 11.jpg | `ns` | C |  | [보기](results/compare/11.jpg) |
| 11.jpg | `powerpaint_remove` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `pp_conservative` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `pp_fullctx` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `sd15` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `sd15_conservative` |   |   | [보기](results/compare/11.jpg) |
| 11.jpg | `telea` | C |  | [보기](results/compare/11.jpg) |
| 12.jpg | `lama` | B |  | [보기](results/compare/12.jpg) |
| 12.jpg | `ns` | C |  | [보기](results/compare/12.jpg) |
| 12.jpg | `powerpaint_remove` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `pp_conservative` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `pp_fullctx` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `sd15` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `sd15_conservative` |   |   | [보기](results/compare/12.jpg) |
| 12.jpg | `telea` | C |  | [보기](results/compare/12.jpg) |

**집계** — 위 판정표에서 자동 계산됨. 직접 채우지 말 것

| variant | A | B | C | A+B 비율 | 70% 통과 |
|---|---|---|---|---|---|
| `lama` | 8 | 2 | 2 | 10/12 (83%) | O |
| `ns` *(제외)* | 1 | 1 | 10 | 2/12 (17%) | X |
| `powerpaint_remove` | 0 | 0 | 0 | 판정 0/12 | 판정 미완 |
| `pp_conservative` | 0 | 0 | 0 | 판정 0/12 | 판정 미완 |
| `pp_fullctx` | 0 | 0 | 0 | 판정 0/12 | 판정 미완 |
| `sd15` | 0 | 0 | 0 | 판정 0/12 | 판정 미완 |
| `sd15_conservative` | 0 | 0 | 0 | 판정 0/12 | 판정 미완 |
| `telea` *(제외)* | 1 | 2 | 9 | 3/12 (25%) | X |

**제외 variant**

| variant | 사유 |
|---|---|
| `ns` | LaMa 대비 열위 — 판정 완료 후 제외 (2026-08-20) |
| `telea` | LaMa 대비 열위 — 판정 완료 후 제외 (2026-08-20) |

> ⚠️ 위 표는 **이미지 단위**다. 문서 2.2가 확정한 E1 판정 단위는 **영역 단위**이므로,
> 이 비율을 문서의 Go/No-Go 70%와 같은 값으로 취급하지 말 것. 판단 참고치로만 쓴다.
