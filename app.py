"""Aplicación Flask para reconocimiento de seis categorías de audio."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from src.constants import DEFAULT_MAX_AUDIO_MB, SUPPORTED_EXTENSIONS
from src.prediction import ModelService, ModelUnavailableError
from src.preprocessing import AudioValidationError


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def create_app(
    test_config: dict[str, Any] | None = None,
    model_service: Any | None = None,
) -> Flask:
    app = Flask(__name__)
    root = Path(__file__).resolve().parent
    max_audio_mb = int(os.getenv("MAX_AUDIO_MB", str(DEFAULT_MAX_AUDIO_MB)))
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=max_audio_mb * 1024 * 1024,
        MODEL_PATH=os.getenv("MODEL_PATH", str(root / "model" / "audio_classifier.keras")),
        METADATA_PATH=os.getenv("METADATA_PATH", str(root / "model" / "metadata.json")),
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    service = model_service or ModelService(
        app.config["MODEL_PATH"], app.config["METADATA_PATH"]
    )
    app.extensions["audio_model_service"] = service

    @app.get("/")
    def index():
        info = service.info()
        display_labels = info.get("display_labels", {})
        demo_examples = [
            {
                "class": class_name,
                "label": display_labels.get(class_name, class_name.title()),
                "filename": f"demo_audio/{class_name}.wav",
            }
            for class_name in info.get("classes", [])
            if (root / "static" / "demo_audio" / f"{class_name}.wav").is_file()
        ]
        return render_template(
            "index.html",
            allowed_extensions=sorted(SUPPORTED_EXTENSIONS),
            max_audio_mb=max_audio_mb,
            model_info=info,
            demo_examples=demo_examples,
        )

    @app.get("/health")
    def health():
        # En producción no basta con que el archivo exista: Railway solo debe
        # activar el deploy cuando Keras haya podido cargar el modelo.
        ready_check = getattr(service, "is_ready", service.is_available)
        available = bool(ready_check())
        payload = {
            "status": "ok" if available else "model_missing",
            "service": "audio-recognition",
            "model_available": available,
        }
        return jsonify(payload), 200 if available else 503

    @app.get("/api/status")
    def api_status():
        return jsonify(service.info())

    @app.post("/api/predict")
    def predict_audio():
        if "audio" not in request.files:
            return jsonify({"error": "Debes adjuntar un archivo en el campo 'audio'."}), 400

        uploaded = request.files["audio"]
        original_name = secure_filename(uploaded.filename or "")
        if not original_name:
            return jsonify({"error": "Selecciona o graba un audio antes de analizar."}), 400

        extension = _extension(original_name)
        if extension not in SUPPORTED_EXTENSIONS:
            formats = ", ".join(sorted(SUPPORTED_EXTENSIONS)).upper()
            return jsonify({"error": f"Formato no permitido. Usa: {formats}."}), 415

        temp_path: Path | None = None
        try:
            app.logger.info("Analizando archivo de audio: %s", original_name)
            with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temp:
                temp_path = Path(temp.name)
                uploaded.save(temp)
            if temp_path.stat().st_size == 0:
                return jsonify({"error": "El archivo recibido está vacío."}), 400
            result = service.predict(temp_path)
            result["filename"] = original_name
            app.logger.info(
                "Predicción completada: archivo=%s clase=%s confianza=%.4f",
                original_name,
                result["prediction"],
                result["confidence"],
            )
            return jsonify(result)
        except AudioValidationError as exc:
            return jsonify({"error": str(exc)}), 422
        except ModelUnavailableError as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception:
            app.logger.exception("Fallo inesperado durante la inferencia")
            return jsonify({"error": "No fue posible analizar el audio."}), 500
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"error": f"El audio supera el límite de {max_audio_mb} MB."}), 413

    return app


_log_file = os.getenv("LOG_FILE")
_log_handlers = (
    [logging.FileHandler(_log_file, encoding="utf-8")]
    if _log_file
    else [logging.StreamHandler()]
)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=_log_handlers,
)
app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
