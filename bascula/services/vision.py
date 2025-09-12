from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore


try:
    from tflite_runtime.interpreter import Interpreter  # type: ignore
except Exception:  # pragma: no cover
    try:
        from tensorflow.lite.python.interpreter import Interpreter  # type: ignore
    except Exception:
        Interpreter = None  # type: ignore


class VisionService:
    """Tiny wrapper around a TFLite classifier model.

    Expects a classification model with a single input tensor (H,W,C) and a
    single output vector of class scores. Labels file is a text file with one
    label per line.
    """

    def __init__(
        self,
        model_path: str,
        labels_path: str,
        confidence_threshold: float = 0.85,
    ) -> None:
        if Interpreter is None:
            raise RuntimeError("TFLite Interpreter no disponible")
        if Image is None:
            raise RuntimeError("PIL (Pillow) no disponible")

        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]

        # Load labels
        with open(labels_path, "r", encoding="utf-8", errors="ignore") as f:
            self.labels = [line.strip() for line in f if line.strip()]

        self.threshold = float(confidence_threshold)

    def _prepare_input(self, img: Image.Image) -> np.ndarray:
        # Expect input shape like (1, H, W, C)
        _, ih, iw, _ = self.input_details["shape"]
        x = img.resize((int(iw), int(ih)))
        arr = np.asarray(x)
        if arr.ndim == 2:  # grayscale -> add channels
            arr = np.stack([arr] * 3, axis=-1)
        dtype = self.input_details.get("dtype")
        if dtype == np.uint8:
            arr = arr.astype(np.uint8)
        else:
            arr = arr.astype(np.float32) / 255.0
        arr = np.expand_dims(arr, 0)
        return arr

    def _postprocess(self, y: np.ndarray) -> np.ndarray:
        # Flatten and convert to probabilities using softmax
        z = y.astype(np.float32)
        if z.ndim > 1:
            z = z.reshape(-1)
        # Softmax
        z = z - np.max(z)
        e = np.exp(z)
        probs = e / np.maximum(1e-8, np.sum(e))
        return probs

    def classify_image(self, pil_image: Image.Image) -> Optional[Tuple[str, float]]:
        if pil_image is None:
            return None
        try:
            inp = self._prepare_input(pil_image)
            self.interpreter.set_tensor(self.input_details["index"], inp)
            self.interpreter.invoke()
            out = self.interpreter.get_tensor(self.output_details["index"])  # type: ignore
            probs = self._postprocess(out[0] if out.ndim >= 2 else out)
            idx = int(np.argmax(probs))
            conf = float(probs[idx])
            if conf >= self.threshold and 0 <= idx < len(self.labels):
                return (self.labels[idx], conf)
            return None
        except Exception:
            return None

