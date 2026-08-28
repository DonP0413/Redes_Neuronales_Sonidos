from __future__ import annotations

import io

from app import create_app
from src.constants import DISPLAY_LABELS


class DummyModelService:
    def is_available(self):
        return True

    def info(self):
        return {
            "available": True,
            "classes": ["claxon", "ladrido", "aplausos", "lluvia", "sirena", "helicoptero"],
            "display_labels": DISPLAY_LABELS,
            "selected_optimizer": "adam",
            "parameter_count": 28_000,
            "dataset_kind": "test",
            "warning": None,
        }

    def predict(self, _path):
        return {
            "prediction": "claxon",
            "label": "Claxon",
            "confidence": 0.9,
            "probabilities": [],
            "spectrogram": [[0.0]],
            "latency_ms": 1.0,
            "model": {"optimizer": "adam", "dataset_kind": "test", "warning": None},
        }


def client():
    app = create_app({"TESTING": True}, model_service=DummyModelService())
    return app.test_client()


def test_health_is_ok():
    response = client().get("/health")
    assert response.status_code == 200
    assert response.get_json()["model_available"] is True


def test_home_lists_six_real_classes_and_demo_players():
    html = client().get("/").get_data(as_text=True)
    for label in ("Claxon", "Ladrido", "Aplausos", "Lluvia", "Sirena", "Helicóptero"):
        assert label in html
    assert "Escucha las seis clases" in html
    assert html.count("<audio controls") == 6


def test_predict_requires_audio():
    response = client().post("/api/predict", data={})
    assert response.status_code == 400


def test_predict_rejects_extension():
    response = client().post(
        "/api/predict",
        data={"audio": (io.BytesIO(b"hello"), "audio.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415


def test_predict_returns_result():
    response = client().post(
        "/api/predict",
        data={"audio": (io.BytesIO(b"fake-wave"), "sample.wav")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["prediction"] == "claxon"
    assert payload["filename"] == "sample.wav"
