from __future__ import annotations

import csv
import wave

import numpy as np

from src.prepare_esc50 import ESC50_TO_ONDA, prepare_dataset


def _write_wave(path):
    pcm = (np.sin(np.linspace(0, 20, 1600)) * 16000).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(pcm.tobytes())


def test_prepare_esc50_preserves_official_folds(tmp_path):
    source = tmp_path / "ESC-50"
    (source / "audio").mkdir(parents=True)
    (source / "meta").mkdir()
    rows = []
    for category in ESC50_TO_ONDA:
        for fold in range(1, 6):
            for item in range(8):
                filename = f"{fold}-{category}-{item}.wav"
                _write_wave(source / "audio" / filename)
                rows.append(
                    {
                        "filename": filename,
                        "fold": fold,
                        "target": 0,
                        "category": category,
                        "esc10": "False",
                        "src_file": item,
                        "take": "A",
                    }
                )
    with (source / "meta" / "esc50.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest = prepare_dataset(source, tmp_path / "prepared", tmp_path / "demos")
    with manifest.open(newline="", encoding="utf-8") as stream:
        prepared = list(csv.DictReader(stream))

    assert len(prepared) == 240
    assert {int(row["fold"]) for row in prepared} == {1, 2, 3, 4, 5}
    assert len(list((tmp_path / "demos").glob("*.wav"))) == 6
