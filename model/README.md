# Artefactos del modelo

El entrenamiento genera aquí:

- `audio_classifier.keras`: modelo elegido mediante accuracy de validación.
- `metadata.json`: clases, preprocesamiento, parámetros y métricas.
- `experiments/adam.keras` y `experiments/sgd.keras`: checkpoints comparados.

El archivo `audio_classifier.keras` y `metadata.json` deben estar presentes en
el repositorio que se despliegue en Railway.

