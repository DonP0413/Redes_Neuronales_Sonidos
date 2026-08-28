"""Prueba rápida con el modelo real y un audio demo de cada clase."""

from __future__ import annotations

from pathlib import Path

from app import app
from src.constants import CLASS_NAMES


def main() -> None:
    client = app.test_client()
    home = client.get("/")
    print(f"home: {home.status_code}, {len(home.data)} bytes")
    health = client.get("/health")
    print(f"health: {health.status_code}, {health.get_json()}")

    failures = 0
    for class_name in CLASS_NAMES:
        path = Path("static") / "demo_audio" / f"{class_name}.wav"
        with path.open("rb") as stream:
            response = client.post(
                "/api/predict",
                data={"audio": (stream, f"{class_name}.wav")},
                content_type="multipart/form-data",
            )
        payload = response.get_json()
        prediction = payload.get("prediction")
        confidence = float(payload.get("confidence", 0))
        print(
            f"{class_name:8s}: HTTP {response.status_code}, "
            f"predicción={prediction}, confianza={confidence:.4f}"
        )
        failures += int(response.status_code != 200 or prediction != class_name)

    if home.status_code != 200 or health.status_code != 200 or failures:
        raise SystemExit(f"Smoke test fallido: {failures} predicciones incorrectas.")
    print("Smoke test completado correctamente.")


if __name__ == "__main__":
    main()
