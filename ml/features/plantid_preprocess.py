"""
Client-reference image preprocessing for the exported plant-ID model.

This is the contract every client implements (apps/web/src/utils/plantid.ts,
android .../feature/identify/PlantIdModel.kt):

  1. crop the centred square (side = min(width, height)) out of the photo,
  2. bilinear-resize it to input_size x input_size,
  3. RGB, scaled to [0, 1], laid out as float32 NCHW.

Mean/std normalisation and L2-normalising the output are baked into the
ONNX graph, so clients never need per-backbone constants. Prototypes and the
calibration in plantid_<version>.json are computed from embeddings produced
through THIS function, which is why client parity tests compare against it.
"""
import numpy as np
from PIL import Image


def center_square(width: int, height: int) -> tuple[int, int, int]:
    """(left, top, side) of the centred square crop."""
    side = min(width, height)
    return (width - side) // 2, (height - side) // 2, side


def preprocess(img: Image.Image, size: int) -> np.ndarray:
    """PIL image -> (3, size, size) float32 in [0, 1]."""
    img = img.convert('RGB')
    left, top, side = center_square(*img.size)
    img = img.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0


def load_and_preprocess(path, size: int) -> np.ndarray | None:
    """File -> preprocessed array, or None if it can't be decoded."""
    from PIL import ImageOps
    Image.MAX_IMAGE_PIXELS = None   # some Wikimedia originals are huge
    try:
        img = Image.open(path)
        img.draft('RGB', (size * 2, size * 2))   # fast JPEG decode; still >= 2x target
        # Browsers (createImageBitmap) and Android apply EXIF rotation; so must we.
        return preprocess(ImageOps.exif_transpose(img), size)
    except Exception:
        return None
