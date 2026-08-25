"""Definición de la CNN compacta usada en los dos experimentos."""

from __future__ import annotations

from typing import Sequence


def build_cnn(
    input_shape: Sequence[int],
    num_classes: int,
    optimizer_name: str = "adam",
):
    """Construye y compila la misma arquitectura con Adam o SGD+Momentum."""

    import tensorflow as tf

    inputs = tf.keras.Input(shape=tuple(input_shape), name="mel_espectrograma")
    x = tf.keras.layers.RandomTranslation(
        height_factor=0.025,
        width_factor=0.08,
        fill_mode="constant",
        fill_value=0.0,
        name="desplazamiento_entrenamiento",
    )(inputs)
    x = tf.keras.layers.RandomContrast(0.10, name="contraste_entrenamiento")(x)
    x = tf.keras.layers.GaussianNoise(0.02, name="ruido_entrenamiento")(x)

    for index, filters in enumerate((16, 32, 64), start=1):
        x = tf.keras.layers.Conv2D(
            filters,
            kernel_size=3,
            padding="same",
            activation="relu",
            name=f"conv_{index}",
        )(x)
        x = tf.keras.layers.MaxPooling2D(pool_size=2, name=f"pool_{index}")(x)

    # Promedio y máximo temporal conservan la ubicación frecuencial y permiten
    # distinguir texturas continuas (lluvia) de transitorios fuertes (aplausos).
    temporal_frames = int(x.shape[2])
    temporal_mean = tf.keras.layers.AveragePooling2D(
        pool_size=(1, temporal_frames),
        name="promedio_temporal",
    )(x)
    temporal_peak = tf.keras.layers.MaxPooling2D(
        pool_size=(1, temporal_frames),
        name="maximo_temporal",
    )(x)
    temporal_mean = tf.keras.layers.Flatten(name="vector_promedio")(temporal_mean)
    temporal_peak = tf.keras.layers.Flatten(name="vector_maximo")(temporal_peak)
    x = tf.keras.layers.Concatenate(name="estadisticas_temporales")(
        [temporal_mean, temporal_peak]
    )
    x = tf.keras.layers.Dense(64, activation="relu", name="dense_64")(x)
    x = tf.keras.layers.Dropout(0.35, name="dropout")(x)
    outputs = tf.keras.layers.Dense(
        num_classes,
        activation="softmax",
        name="probabilidades",
    )(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="cnn_audio_ligera")

    optimizer_key = optimizer_name.lower()
    if optimizer_key == "adam":
        optimizer = tf.keras.optimizers.Adam(learning_rate=1e-3)
    elif optimizer_key == "sgd":
        optimizer = tf.keras.optimizers.SGD(learning_rate=1e-2, momentum=0.9)
    else:
        raise ValueError(f"Optimizador no soportado: {optimizer_name}")

    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model
