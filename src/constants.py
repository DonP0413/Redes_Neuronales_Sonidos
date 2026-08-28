"""Configuración compartida por entrenamiento, inferencia y la interfaz."""

from __future__ import annotations

CLASS_NAMES = (
    "claxon",
    "ladrido",
    "aplausos",
    "lluvia",
    "sirena",
    "helicoptero",
)

DISPLAY_LABELS = {
    "claxon": "Claxon",
    "ladrido": "Ladrido",
    "aplausos": "Aplausos",
    "lluvia": "Lluvia",
    "sirena": "Sirena",
    "helicoptero": "Helicóptero",
}

AUDIO_CONFIG = {
    "sample_rate": 16_000,
    "duration_seconds": 5.0,
    "n_mels": 64,
    "n_fft": 512,
    "hop_length": 256,
    "fmin": 50,
    "fmax": 7_600,
    "target_frames": 320,
    "top_db": 80.0,
}

SUPPORTED_EXTENSIONS = {"wav", "flac", "ogg", "mp3", "m4a", "webm"}
DEFAULT_MAX_AUDIO_MB = 10
