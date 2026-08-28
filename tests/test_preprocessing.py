from __future__ import annotations

import wave

import numpy as np
import pytest

from src.constants import AUDIO_CONFIG
from src.preprocessing import AudioValidationError, extract_feature


def write_wave(path, signal, sample_rate=16_000):
    pcm = np.clip(signal * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())


def test_extract_feature_has_expected_shape_and_range(tmp_path):
    sample_rate = 16_000
    time = np.arange(sample_rate) / sample_rate
    signal = 0.6 * np.sin(2 * np.pi * 1_800 * time)
    path = tmp_path / "tone.wav"
    write_wave(path, signal)

    feature = extract_feature(path)

    assert feature.shape == (
        AUDIO_CONFIG["n_mels"],
        AUDIO_CONFIG["target_frames"],
        1,
    )
    assert feature.dtype == np.float32
    assert float(feature.min()) >= 0.0
    assert float(feature.max()) <= 1.0


def test_silence_is_rejected(tmp_path):
    path = tmp_path / "silence.wav"
    write_wave(path, np.zeros(16_000, dtype=np.float32))

    with pytest.raises(AudioValidationError, match="silencio"):
        extract_feature(path)

