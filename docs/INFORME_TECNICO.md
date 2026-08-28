# Sistema web de reconocimiento de audio con redes neuronales

**Materia:** Sistemas Embebidos y Redes Neuronales  
**Período:** 2026_2  
**Docente:** Ing. Sergio Granizo, MSc.  
**Integrantes:** Erick, Miguel y Jorge  
**Fecha de defensa:** 3 y 4 de septiembre de 2026

## Resumen

Se desarrolló una aplicación web que clasifica seis sonidos ambientales:
claxon, ladrido, aplausos, lluvia, sirena y helicóptero. El sistema utiliza 240
grabaciones reales del dataset ESC-50, las convierte en Mel-espectrogramas y las
procesa con una CNN. Se comparan Adam y SGD con Momentum bajo condiciones
controladas. El modelo seleccionado se integra en Flask y una interfaz que
permite escuchar ejemplos, cargar o grabar audio y visualizar probabilidades.

## 1. Objetivos

- Construir un dataset balanceado, real y auditable.
- Aplicar el mismo preprocesamiento en entrenamiento e inferencia.
- Diseñar una CNN ligera para seis clases.
- comparar Adam y SGD manteniendo constantes las demás variables;
- medir accuracy, precision, recall, F1 y matriz de confusión;
- integrar el modelo en una aplicación web desplegable en Railway.

## 2. Dataset y partición

ESC-50 contiene grabaciones ambientales etiquetadas y una división oficial de
cinco folds. Se seleccionaron seis categorías, 40 muestras por categoría y 240
audios en total. El mapeo está en `src/prepare_esc50.py`.

| Uso | Folds | Audios | Porcentaje | Audios por clase |
|---|---|---:|---:|---:|
| Entrenamiento | 1–3 | 144 | 60 % | 24 |
| Validación | 4 | 48 | 20 % | 8 |
| Prueba | 5 | 48 | 20 % | 8 |

El archivo `dataset/esc50/manifest.csv` conserva etiqueta, fold, nombre y
referencia de Freesound. `results/dataset_split.csv` registra la asignación que
recibió cada audio.

## 3. Procesamiento de señal

Cada archivo se convierte a mono y 16 kHz. Se rechazan silencio y archivos
inválidos, se recortan silencios laterales, se normaliza por pico y se ajusta a
cinco segundos. Después se calcula un Mel-espectrograma con 64 bandas, FFT 512,
hop 256 y rango de 80 dB. La entrada final es `64 × 320 × 1` en `[0,1]`.

Durante entrenamiento se aplican desplazamiento leve, contraste y ruido. Estas
transformaciones aumentan la variedad sin modificar los archivos originales y
no se aplican durante validación, prueba o producción.

## 4. Arquitectura CNN

La red contiene tres bloques `Conv2D + ReLU + MaxPooling2D`, con 16, 32 y 64
filtros. Dos ramas calculan promedio y máximo sobre el tiempo. El promedio
resume texturas continuas y el máximo preserva eventos transitorios; sus
vectores se concatenan. La cabeza usa Dense 64, dropout 0,35 y Softmax de seis
salidas. El modelo tiene **89.286 parámetros**.

El resumen exacto está en `results/model_summary.txt` y el diagrama en
`results/architecture.png`.

## 5. Diseño experimental

| Experimento | Optimizador | Learning rate | Configuración común |
|---|---|---:|---|
| A | Adam | 0,001 | misma CNN, datos, batch y seed |
| B | SGD + Momentum 0,9 | 0,01 | misma CNN, datos, batch y seed |

Ambos tienen un máximo de 70 épocas, batch 16, `ReduceLROnPlateau` con factor
0,5 y `EarlyStopping` con paciencia de 12 épocas. Adam alcanzó su mejor punto
en la época 60 y SGD + Momentum en la 62. El ganador se elige por mayor
accuracy de validación y, ante empate, menor loss. El conjunto de prueba no
participa en esta decisión.

## 6. Resultados

| Optimizador | Mejor época | Accuracy val. | Loss val. | Accuracy test | F1 macro test |
|---|---:|---:|---:|---:|---:|
| Adam | 60 | 97,92 % | 0,0992 | 87,50 % | 87,17 % |
| SGD + Momentum | 62 | 100 % | 0,0883 | 89,58 % | 89,29 % |

SGD fue seleccionado. En test acertó 43 de 48 audios. Sirena y helicóptero
alcanzaron 8/8; claxon y lluvia tuvieron recall 8/8; ladrido logró 6/8 y
aplausos 5/8. La principal dificultad es separar aplausos de otras texturas de
ruido, especialmente lluvia.

Estos resultados corresponden a grabaciones reales no usadas en entrenamiento.
No significan que el modelo reconocerá cualquier grabación de Internet: ESC-50
es pequeño y la aplicación siempre fuerza una de sus seis etiquetas.

## 7. Aplicación web

Flask expone `/api/predict`, `/api/status` y `/health`. La web incluye seis
reproductores del fold 5 para que el público conozca las clases, carga de
archivo, grabación de micrófono, waveform, clase principal, confianza, las seis
probabilidades y Mel-espectrograma. El temporal del servidor se elimina después
de cada petición.

El modelo se carga una vez por proceso. Para Railway se utiliza Docker, Python
3.11 y Gunicorn con un worker para controlar el consumo de TensorFlow.

## 8. Limitaciones y mejoras

- Solo hay 40 grabaciones por clase.
- No existe clase “desconocido”; Softmax siempre elige una de seis.
- La confianza no equivale a certeza calibrada.
- Ruido intenso o sonidos superpuestos pueden degradar el resultado.
- ESC-50 es CC BY-NC, por lo que este uso debe mantenerse académico y no
  comercial.

Como mejoras se proponen más grabaciones, validación cruzada completa,
calibración de confianza, clase desconocida y cuantización para dispositivos
embebidos.

## 9. Reproducibilidad

La preparación y el entrenamiento están documentados en `README.md` y
`docs/GUIA_ENTRENAMIENTO.md`. Se fija seed 2026 y cada corrida genera modelo,
metadatos, curvas, matriz, reporte y predicciones individuales.
