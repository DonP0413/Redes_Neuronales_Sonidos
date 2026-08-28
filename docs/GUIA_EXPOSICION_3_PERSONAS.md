# Guía de exposición para Erick, Miguel y Jorge

Duración sugerida: **12 minutos de explicación y 3 de preguntas**. Practiquen
una vez con la app local y otra con la URL de Railway.

## Inicio de la defensa: 45 segundos

Antes de explicar el modelo, abran la sección **“Escucha las seis clases”** y
reproduzcan unos segundos de claxon, ladrido, aplausos, lluvia, sirena y
helicóptero. Pregunten al público qué escucha. Esto establece que son sonidos
reales e identificables.

## Erick — problema, ESC-50 y señal (0:45–4:00)

### Guion sugerido

“Nuestro objetivo fue reconocer seis sonidos ambientales reales desde una
aplicación web: claxon, ladrido, aplausos, lluvia, sirena y helicóptero. Elegimos
estas clases porque una persona puede diferenciarlas al escucharlas.”

“Usamos ESC-50. Seleccionamos 40 audios por clase, 240 en total, y respetamos
sus folds oficiales. Los folds 1 a 3 entrenan, el 4 valida y el 5 prueba. Por
eso la prueba contiene grabaciones que la red nunca utilizó para aprender.”

“Cada audio se convierte a mono, 16 kHz y cinco segundos. Luego calculamos un
Mel-espectrograma de 64 por 320, que representa frecuencia y tiempo de una forma
más útil que la onda cruda.”

Mostrar:

- `dataset/esc50/manifest.csv`;
- un reproductor y el espectrograma de la web;
- la tabla 144/48/48;
- la atribución y licencia CC BY-NC de ESC-50.

Transición: “Con las señales transformadas de manera consistente, Miguel
entrenó y comparó las redes.”

## Miguel — CNN, optimizadores y resultados (4:00–8:00)

### Guion sugerido

“La entrada es 64×320×1. La CNN tiene tres bloques convolucionales de 16, 32 y
64 filtros. Después calcula media y máximo temporal: la media ayuda con sonidos
continuos, como lluvia, y el máximo conserva golpes cortos, como aplausos. La
cabeza termina en Softmax de seis salidas. En total tiene 89.286 parámetros.”

“Las capas convolucionales y la Dense de 64 usan ReLU porque aprende relaciones
no lineales sin saturarse tanto como Sigmoid o Tanh. La salida usa Softmax porque
solo una de las seis clases puede ser la respuesta y necesitamos probabilidades
que sumen 100 %.”

“En el forward pass, el espectrograma atraviesa todas las capas hasta producir
seis probabilidades. La función sparse categorical crossentropy compara esa
salida con la etiqueta correcta. Después, TensorFlow calcula los gradientes con
backpropagation y el optimizador actualiza los 89.286 parámetros. En validación,
prueba y producción solo se ejecuta el forward pass; los pesos no cambian.”

“Comparamos Adam y SGD con Momentum usando exactamente los mismos datos,
arquitectura, batch y seed. El ganador se seleccionó con validación. SGD alcanzó
100 % en validación frente a 97,92 % de Adam y por eso fue publicado.”

“En el test separado, SGD acertó 43 de 48: 89,58 % de accuracy y 89,29 % de F1
macro. Sirena y helicóptero lograron 8 de 8. Aplausos fue la clase más difícil,
con 5 de 8, porque algunas texturas se parecen a lluvia.”

“Las curvas no muestran underfitting dominante porque entrenamiento y
validación alcanzan accuracy alta. Sí existe riesgo moderado de overfitting por
tener solo 40 audios por clase y porque validación llegó a 100 %, mientras test
obtuvo 89,58 %. Lo controlamos con aumento de datos, dropout, reducción del
learning rate y early stopping. Tampoco observamos señales claras de vanishing
gradient: la red es corta, usa ReLU y la loss descendió de forma sostenida.”

Mostrar, en este orden:

1. `results/architecture.png`;
2. `results/optimizer_comparison.png`;
3. `results/optimizer_metrics.csv`;
4. `results/confusion_matrix.png`.

Transición: “Jorge tomó el modelo ganador y lo convirtió en una aplicación
usable y desplegable.”

## Jorge — frontend, API, Railway y demo (8:00–11:20)

### Guion sugerido

“La interfaz permite subir o grabar audio. Flask valida el archivo, aplica el
mismo preprocesamiento y devuelve la etiqueta, confianza, seis probabilidades,
latencia y espectrograma. Así no existe una transformación diferente entre
entrenamiento y producción.”

“Para Railway usamos Docker, Python 3.11, Gunicorn y `/health`. El modelo viaja
con el repositorio; Railway no vuelve a entrenar ni necesita descargar ESC-50.”

### Demostración de 60–75 segundos

1. Reproduzcan un ejemplo para que el público lo identifique.
2. Carguen ese WAV o uno distinto del fold 5.
3. Pulsen **Analizar audio**.
4. Señalen resultado, confianza y las seis barras del panel derecho.
5. Muestren cómo el espectrograma cambia entre lluvia y claxon.

Los seis audios incluidos ya fueron verificados con el modelo. No improvisen
con audio de videos ruidosos durante la demostración principal.

## Cierre grupal (11:20–12:00)

Erick: “Partimos de grabaciones ambientales reales y una separación auditable.”

Miguel: “El test obtuvo 89,58 %, pero reconocemos que 40 audios por clase aún
limitan la generalización.”

Jorge: “Entregamos el ciclo completo: datos, CNN, evaluación, API, frontend y
despliegue.”

## Preguntas probables

**¿Por qué una CNN?** Porque comparte filtros y detecta patrones locales en el
Mel-espectrograma con menos parámetros que una red totalmente conectada.

**¿Qué es el forward pass?** Es el recorrido del Mel-espectrograma por todas las
capas hasta obtener las seis probabilidades de Softmax.

**¿Qué es backpropagation?** Es el cálculo de cómo contribuyó cada peso al error.
TensorFlow obtiene esos gradientes automáticamente y Adam o SGD actualizan los
pesos para reducir la pérdida.

**¿Por qué usan ReLU y Softmax?** ReLU ayuda a entrenar las capas internas sin
saturarse tanto como Sigmoid o Tanh. Softmax convierte la salida final en seis
probabilidades que suman 100 %.

**¿Por qué ESC-50?** Porque contiene grabaciones reales, etiquetas conocidas y
folds oficiales para comparar sin mezclar los mismos audios entre subconjuntos.

**¿Por qué eligieron SGD?** La regla se definió antes: mayor accuracy de
validación y luego menor loss. SGD obtuvo 100 % y loss 0,0883.

**¿Accuracy de 89,58 % significa que siempre funciona?** No. Son 43 aciertos en
48 audios del fold de prueba elegido. Otro ambiente puede producir resultados
diferentes.

**¿Existe underfitting u overfitting?** No se observa underfitting dominante,
porque las curvas alcanzan accuracy alta. Existe riesgo moderado de overfitting
por el tamaño del dataset y la diferencia validación-test; por eso se usaron
aumento de datos, dropout, reducción del learning rate y early stopping.

**¿Hubo vanishing gradient?** No hay señales claras en las curvas y no se midió
el gradiente directamente. La CNN tiene solo tres bloques, usa ReLU y la pérdida
disminuyó, lo que indica que las capas iniciales sí recibieron señal de
aprendizaje.

**¿La confianza es certeza?** No. Es una salida Softmax relativa entre seis
clases y puede ser alta incluso para un sonido desconocido.

**¿Qué ocurre con música o voz?** Como no existe la clase desconocido, el modelo
elegirá la clase más parecida. Un umbral calibrado y ejemplos negativos serían
la siguiente mejora.

**¿Por qué 16 kHz?** Reduce cálculo y conserva frecuencias hasta 8 kHz, suficientes
para los patrones principales de estas clases.

**¿El dataset se sube a Railway?** No. Railway solo necesita código, modelo,
metadata y audios demostrativos. El dataset completo se usa al entrenar.

## Plan B

- Aplicación local iniciada con `scripts/run_local.ps1`.
- Seis WAV de `static/demo_audio/` disponibles sin Internet.
- Capturas de matriz, curvas, `/health` y una predicción.
- Si falla el micrófono, usar carga de archivo; la inferencia es la misma.
