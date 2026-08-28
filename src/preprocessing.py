"""Preprocesamiento reproducible de audio a Mel-espectrograma.

La misma función ``extract_feature`` se usa durante el entrenamiento y en la
API web. Esto evita la divergencia más común en proyectos de ML: entrenar con
una representación y predecir con otra.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import librosa
import numpy as np

from .constants import AUDIO_CONFIG


class AudioValidationError(ValueError):
    """El archivo existe, pero no contiene audio utilizable."""


def _resolved_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    resolved = dict(AUDIO_CONFIG)
    if config:
        resolved.update(config)
    resolved["sample_rate"] = int(resolved["sample_rate"])
    resolved["n_mels"] = int(resolved["n_mels"])
    resolved["n_fft"] = int(resolved["n_fft"])
    resolved["hop_length"] = int(resolved["hop_length"])
    resolved["target_frames"] = int(resolved["target_frames"])
    resolved["duration_seconds"] = float(resolved["duration_seconds"])
    return resolved


def load_and_standardize_audio(
    audio_path: str | Path,
    config: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Carga, convierte a mono, recorta silencio y fija duración exacta."""

    cfg = _resolved_config(config)
    path = Path(audio_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise AudioValidationError("El archivo de audio está vacío o no existe.")

    try:
        signal, _ = librosa.load(path, sr=cfg["sample_rate"], mono=True)
    except Exception as exc:  # El backend de audio varía según el formato.
        raise AudioValidationError(
            "No se pudo decodificar el audio. Prueba con WAV, FLAC, OGG o MP3."
        ) from exc

    signal = np.asarray(signal, dtype=np.float32)
    if signal.size == 0 or not np.isfinite(signal).all():
        raise AudioValidationError("El audio no contiene muestras válidas.")

    raw_rms = float(np.sqrt(np.mean(np.square(signal), dtype=np.float64)))
    if raw_rms < 1e-5:
        raise AudioValidationError("El audio está en silencio o su volumen es demasiado bajo.")

    trimmed, _ = librosa.effects.trim(signal, top_db=35)
    if trimmed.size:
        signal = trimmed

    peak = float(np.max(np.abs(signal)))
    if peak > 0:
        signal = signal / peak

    target_samples = int(cfg["sample_rate"] * cfg["duration_seconds"])
    if signal.size > target_samples:
        start = (signal.size - target_samples) // 2
        signal = signal[start : start + target_samples]
    elif signal.size < target_samples:
        missing = target_samples - signal.size
        left = missing // 2
        right = missing - left
        signal = np.pad(signal, (left, right), mode="constant")

    return signal.astype(np.float32, copy=False)


def signal_to_mel_feature(
    signal: np.ndarray,
    config: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Convierte una señal normalizada en un tensor ``mels x tiempo x 1``."""

    cfg = _resolved_config(config)
    mel_power = librosa.feature.melspectrogram(
        y=signal,
        sr=cfg["sample_rate"],
        n_fft=cfg["n_fft"],
        hop_length=cfg["hop_length"],
        n_mels=cfg["n_mels"],
        fmin=float(cfg["fmin"]),
        fmax=float(cfg["fmax"]),
        power=2.0,
    )
    mel_db = librosa.power_to_db(
        mel_power,
        ref=np.max,
        top_db=float(cfg["top_db"]),
    )

    # power_to_db produce valores en [-top_db, 0]. Este escalado estable evita
    # depender de estadísticas globales y se reproduce igual en producción.
    feature = np.clip(
        (mel_db + float(cfg["top_db"])) / float(cfg["top_db"]),
        0.0,
        1.0,
    )

    frames = cfg["target_frames"]
    if feature.shape[1] > frames:
        start = (feature.shape[1] - frames) // 2
        feature = feature[:, start : start + frames]
    elif feature.shape[1] < frames:
        missing = frames - feature.shape[1]
        feature = np.pad(feature, ((0, 0), (0, missing)), mode="constant")

    return feature[..., np.newaxis].astype(np.float32)


def extract_feature(
    audio_path: str | Path,
    config: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Pipeline público: archivo de audio -> tensor listo para la CNN."""

    signal = load_and_standardize_audio(audio_path, config)
    return signal_to_mel_feature(signal, config)


def make_spectrogram_preview(feature: np.ndarray, width: int = 64) -> list[list[float]]:
    """Reduce el tensor para dibujarlo eficientemente en un ``canvas`` web."""

    matrix = np.squeeze(feature, axis=-1)
    if matrix.shape[1] > width:
        indices = np.linspace(0, matrix.shape[1] - 1, width).astype(int)
        matrix = matrix[:, indices]
    return np.round(matrix, 4).tolist()

