"""iopaint 배치 실행 드라이버 — `.venv-e1`에서 실행된다.

`iopaint run`(batch_processing.batch_inpaint)이 ModelManager를 만들 때
`disable_nsfw`를 넘기지 않는데, PowerPaint의 init_model은 그 키를 필수로 읽어
KeyError로 죽는다. sd15 같은 모델은 .get()으로 읽어서 통과한다.
site-packages를 고치지 않으려고 같은 일을 하는 최소 드라이버를 따로 둔다.

호출 (run.py가 subprocess로 실행)
    python _iopaint_driver.py <model> <device> <img_dir> <mask_dir> <out_dir> [config.json]
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from iopaint.model_manager import ModelManager
from iopaint.schema import InpaintRequest


def main() -> int:
    model, device, img_dir, mask_dir, out_dir = sys.argv[1:6]
    cfg_path = sys.argv[6] if len(sys.argv) > 6 else None

    req = InpaintRequest(**json.loads(Path(cfg_path).read_text(encoding="utf-8"))) if cfg_path else InpaintRequest()
    print(f"config: {req}", flush=True)

    manager = ModelManager(
        name=model,
        device=device,
        disable_nsfw=True,      # 배치 경로가 안 넘겨주는 값. PowerPaint가 필수로 읽는다
        sd_cpu_textencoder=False,
        cpu_offload=False,
        low_mem=False,
        no_half=False,
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    masks = {p.stem: p for p in Path(mask_dir).glob("*.png")}

    for img_p in sorted(Path(img_dir).iterdir()):
        mask_p = masks.get(img_p.stem)
        if mask_p is None:
            print(f"  마스크 없음, 건너뜀: {img_p.name}", flush=True)
            continue

        img = np.array(Image.open(img_p).convert("RGB"))
        mask = np.array(Image.open(mask_p).convert("L"))
        if mask.shape[:2] != img.shape[:2]:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        mask = np.where(mask >= 127, 255, 0).astype(np.uint8)

        res = manager(img, mask, req)  # BGR로 돌아온다
        cv2.imwrite(str(out / f"{img_p.stem}.png"), res)
        print(f"  {img_p.stem} 완료", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
