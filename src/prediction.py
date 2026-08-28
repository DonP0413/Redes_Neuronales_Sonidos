"""Carga perezosa del modelo y servicio seguro de inferencia."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from .preprocessing import extract_feature, make_spectrogram_preview


class ModelUnavailableError(RuntimeError):
    """Los artefactos del modelo no existen o no se pueden cargar."""


class ModelService:
    def __init__(self, model_path: str | Path, metadata_path: str | Path):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self._model = None
        self._metadata: dict[str, Any] | None = None
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()

    def is_available(self) -> bool:
        return self.model_path.is_file() and self.metadata_path.is_file()

    def is_ready(self) -> bool:
        """Confirma que los archivos existen y que Keras puede cargarlos."""

        try:
            self._ensure_loaded()
        except ModelUnavailableError:
            return False
        return True

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._metadata is not None:
            return
        with self._load_lock:
            if self._model is not None and self._metadata is not None:
                return
            if not self.is_available():
                raise ModelUnavailableError(
                    "No se encontró el modelo entrenado. Ejecuta `python -m src.train`."
                )
            try:
                import tensorflow as tf

                metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                model = tf.keras.models.load_model(self.model_path, compile=False)
                if int(model.output_shape[-1]) != len(metadata["class_names"]):
                    raise ValueError("La salida del modelo no coincide con las etiquetas.")
            except Exception as exc:
                raise ModelUnavailableError(f"No se pudo cargar el modelo: {exc}") from exc
            self._metadata = metadata
            self._model = model

    def info(self) -> dict[str, Any]:
        if not self.metadata_path.is_file():
            return {"available": False}
        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"available": False}
        return {
            "available": self.model_path.is_file(),
            "classes": metadata.get("class_names", []),
            "display_labels": metadata.get("display_labels", {}),
            "selected_optimizer": metadata.get("selected_optimizer"),
            "parameter_count": metadata.get("parameter_count"),
            "dataset_kind": metadata.get("dataset", {}).get("kind"),
            "warning": metadata.get("warning"),
        }

    def predict(self, audio_path: str | Path) -> dict[str, Any]:
        self._ensure_loaded()
        assert self._metadata is not None
        assert self._model is not None

        started = time.perf_counter()
        feature = extract_feature(audio_path, self._metadata.get("preprocessing"))
        batch = feature[np.newaxis, ...]
        with self._predict_lock:
            probabilities = np.asarray(self._model.predict(batch, verbose=0)[0], dtype=float)

        class_names = list(self._metadata["class_names"])
        display_labels = self._metadata.get("display_labels", {})
        best_index = int(np.argmax(probabilities))
        ordered = sorted(
            (
                {
                    "class": class_name,
                    "label": display_labels.get(class_name, class_name.title()),
                    "probability": round(float(probabilities[index]), 6),
                }
                for index, class_name in enumerate(class_names)
            ),
            key=lambda item: item["probability"],
            reverse=True,
        )
        return {
            "prediction": class_names[best_index],
            "label": display_labels.get(class_names[best_index], class_names[best_index].title()),
            "confidence": round(float(probabilities[best_index]), 6),
            "probabilities": ordered,
            "spectrogram": make_spectrogram_preview(feature),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "model": {
                "optimizer": self._metadata.get("selected_optimizer"),
                "dataset_kind": self._metadata.get("dataset", {}).get("kind"),
                "warning": self._metadata.get("warning"),
            },
        }
