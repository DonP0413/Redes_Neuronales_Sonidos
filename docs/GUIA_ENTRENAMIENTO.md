# Guía de dataset y entrenamiento

## Dataset

Se usan seis categorías de ESC-50, con 40 grabaciones reales por clase:

| Clase de la app | Categoría ESC-50 | Muestras |
|---|---|---:|
| Claxon | `car_horn` | 40 |
| Ladrido | `dog` | 40 |
| Aplausos | `clapping` | 40 |
| Lluvia | `rain` | 40 |
| Sirena | `siren` | 40 |
| Helicóptero | `helicopter` | 40 |

Total: 240 WAV reales de cinco segundos. No se mezclan señales sintéticas.

## Preparación reproducible

```powershell
git clone --depth 1 https://github.com/karolpiczak/ESC-50.git C:\tmp\ESC-50
.venv\Scripts\python.exe -m src.prepare_esc50 --source-dir C:\tmp\ESC-50
```

El script crea `dataset/esc50/manifest.csv` con el nombre original, la etiqueta
y el fold. También copia un ejemplo del fold 5 por clase a
`static/demo_audio/`; esos ejemplos están excluidos del entrenamiento.

## División experimental

Se respetan los folds proporcionados por ESC-50:

- entrenamiento: folds 1, 2 y 3 — 144 audios (60 %);
- validación: fold 4 — 48 audios (20 %);
- prueba: fold 5 — 48 audios (20 %).

Cada subconjunto contiene ocho audios por clase y por fold. La asignación final
puede auditarse en `results/dataset_split.csv`.

## Preprocesamiento

1. Conversión a mono y resampling a 16.000 Hz.
2. Rechazo de audio vacío o silencioso.
3. Recorte de silencio lateral y normalización por pico.
4. Recorte o zero-padding a cinco segundos.
5. Mel-espectrograma: 64 bandas, FFT 512 y hop 256.
6. Conversión a decibelios, rango de 80 dB y escala `[0,1]`.
7. Tensor final `64 × 320 × 1`.

Durante el entrenamiento se aplican pequeñas variaciones de posición, contraste
y ruido. Estas transformaciones se desactivan automáticamente en inferencia.

## Ejecutar el entrenamiento

```powershell
.venv\Scripts\python.exe -m src.train --dataset-dir dataset\esc50 --epochs 70 --batch-size 16 --patience 12 --seed 2026
```

Se entrenan dos copias de la misma CNN:

- Adam, learning rate 0,001;
- SGD, learning rate 0,01 y momentum 0,9.

Cada experimento permite hasta 70 épocas, usa batch 16, semilla 2026,
`ReduceLROnPlateau` con factor 0,5 y `EarlyStopping` con paciencia 12. Adam
alcanzó su mejor validación en la época 60 y SGD + Momentum en la 62.

La selección utiliza mayor accuracy de validación y luego menor loss de
validación. El test no interviene en la elección.

## Resultado incluido

| Optimizador | Mejor val. accuracy | Mejor val. loss | Test accuracy | Test F1 macro |
|---|---:|---:|---:|---:|
| Adam | 97,92 % | 0,0992 | 87,50 % | 87,17 % |
| SGD + Momentum | 100 % | 0,0883 | 89,58 % | 89,29 % |

Fue seleccionado SGD. La prueba contiene 43 aciertos de 48. Sirena y
helicóptero obtuvieron 8/8; aplausos fue la clase con menor recall, 5/8.

## Artefactos generados

- `model/audio_classifier.keras`: modelo seleccionado.
- `model/metadata.json`: clases, preprocesamiento, métricas y procedencia.
- `results/confusion_matrix.png`: errores por clase.
- `results/optimizer_comparison.png`: curvas Adam/SGD.
- `results/classification_report.*`: precision, recall y F1.
- `results/test_predictions.csv`: las 48 predicciones de prueba.

## Licencia

ESC-50 se distribuye bajo CC BY-NC. El dataset y sus ejemplos deben usarse en
este proyecto con fines académicos no comerciales y manteniendo la atribución.
