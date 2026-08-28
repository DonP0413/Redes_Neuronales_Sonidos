"""Prepara seis clases reales de ESC-50 para el entrenamiento de ONDA.

El repositorio fuente debe contener ``audio/`` y ``meta/esc50.csv``. El script
conserva el fold oficial en el manifiesto y copia un ejemplo del fold 5 por
clase para la demostración web (ese fold nunca se usa para entrenar).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


ESC50_TO_ONDA = {
    "car_horn": "claxon",
    "dog": "ladrido",
    "clapping": "aplausos",
    "rain": "lluvia",
    "siren": "sirena",
    "helicopter": "helicoptero",
}


def prepare_dataset(
    source_dir: str | Path,
    output_dir: str | Path = "dataset/esc50",
    demo_dir: str | Path = "static/demo_audio",
) -> Path:
    source = Path(source_dir).resolve()
    output = Path(output_dir).resolve()
    demos = Path(demo_dir).resolve()
    metadata_path = source / "meta" / "esc50.csv"
    audio_dir = source / "audio"

    if not metadata_path.is_file() or not audio_dir.is_dir():
        raise FileNotFoundError(
            "La fuente no parece ser ESC-50: se esperan meta/esc50.csv y audio/."
        )

    output.mkdir(parents=True, exist_ok=True)
    demos.mkdir(parents=True, exist_ok=True)
    for class_name in ESC50_TO_ONDA.values():
        (output / class_name).mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int]] = []
    with metadata_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for source_row in reader:
            onda_class = ESC50_TO_ONDA.get(source_row["category"])
            if not onda_class:
                continue
            filename = source_row["filename"]
            source_audio = audio_dir / filename
            if not source_audio.is_file():
                raise FileNotFoundError(f"Falta el audio declarado por ESC-50: {source_audio}")
            destination = output / onda_class / filename
            shutil.copy2(source_audio, destination)
            rows.append(
                {
                    "path": destination.relative_to(output).as_posix(),
                    "class": onda_class,
                    "source": "ESC-50",
                    "original_category": source_row["category"],
                    "fold": int(source_row["fold"]),
                    "esc50_filename": filename,
                    "freesound_id": source_row["src_file"],
                }
            )

    expected = 40 * len(ESC50_TO_ONDA)
    if len(rows) != expected:
        raise ValueError(f"Se esperaban {expected} audios y se encontraron {len(rows)}.")

    manifest = output / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    demo_metadata: list[dict[str, str | int]] = []
    for onda_class in ESC50_TO_ONDA.values():
        candidates = [
            row for row in rows if row["class"] == onda_class and row["fold"] == 5
        ]
        selected = sorted(candidates, key=lambda row: str(row["esc50_filename"]))[0]
        shutil.copy2(output / str(selected["path"]), demos / f"{onda_class}.wav")
        demo_metadata.append(selected)

    (demos / "attribution.json").write_text(
        json.dumps(demo_metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    license_path = source / "LICENSE"
    if license_path.is_file():
        shutil.copy2(license_path, output / "LICENSE_ESC-50.txt")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", default="dataset/esc50")
    parser.add_argument("--demo-dir", default="static/demo_audio")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = prepare_dataset(args.source_dir, args.output_dir, args.demo_dir)
    print(f"ESC-50 preparado: 240 audios reales. Manifiesto: {manifest}")
    print("Folds 1-3: entrenamiento; fold 4: validación; fold 5: prueba.")


if __name__ == "__main__":
    main()
