"""Entrena y compara Adam contra SGD para la CNN de reconocimiento de audio."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

from .constants import AUDIO_CONFIG, CLASS_NAMES, DISPLAY_LABELS, SUPPORTED_EXTENSIONS
from .modeling import build_cnn
from .preprocessing import AudioValidationError, extract_feature


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:
        # Algunas operaciones/plataformas no admiten determinismo total.
        pass


def discover_dataset(dataset_dir: Path) -> tuple[list[Path], np.ndarray, dict[str, int]]:
    paths: list[Path] = []
    labels: list[int] = []
    counts: dict[str, int] = {}

    for label, class_name in enumerate(CLASS_NAMES):
        class_dir = dataset_dir / class_name
        if not class_dir.is_dir():
            raise FileNotFoundError(
                f"Falta la carpeta obligatoria del dataset: {class_dir}"
            )
        class_paths = sorted(
            path
            for path in class_dir.rglob("*")
            if path.is_file() and path.suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS
        )
        if len(class_paths) < 10:
            raise ValueError(
                f"La clase '{class_name}' solo tiene {len(class_paths)} audios; "
                "se requieren al menos 10 y se recomiendan 50 o más."
            )
        counts[class_name] = len(class_paths)
        paths.extend(class_paths)
        labels.extend([label] * len(class_paths))

    return paths, np.asarray(labels, dtype=np.int64), counts


def load_features(paths: list[Path]) -> np.ndarray:
    features: list[np.ndarray] = []
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        try:
            features.append(extract_feature(path))
        except AudioValidationError as exc:
            raise AudioValidationError(f"Error en {path}: {exc}") from exc
        if index == 1 or index % 25 == 0 or index == total:
            print(f"Preprocesando audios: {index}/{total}")
    return np.stack(features).astype(np.float32)


def make_splits(
    paths: list[Path],
    labels: np.ndarray,
    seed: int,
    dataset_dir: Path | None = None,
) -> tuple[dict[str, np.ndarray], str, dict[str, int]]:
    if dataset_dir is not None:
        manifest_path = dataset_dir / "manifest.csv"
        if manifest_path.is_file():
            with manifest_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            fold_by_path = {
                str(row.get("path", "")).replace("\\", "/"): int(row["fold"])
                for row in rows
                if row.get("fold") and row.get("source", "").upper() == "ESC-50"
            }
            if len(fold_by_path) == len(paths):
                folds = np.asarray(
                    [fold_by_path[path.relative_to(dataset_dir).as_posix()] for path in paths],
                    dtype=np.int64,
                )
                splits = {
                    "train": np.flatnonzero(np.isin(folds, (1, 2, 3))),
                    "validation": np.flatnonzero(folds == 4),
                    "test": np.flatnonzero(folds == 5),
                }
                for split_name, split_indices in splits.items():
                    if set(labels[split_indices]) != set(range(len(CLASS_NAMES))):
                        raise ValueError(
                            f"El split oficial '{split_name}' no contiene todas las clases."
                        )
                return (
                    splits,
                    "ESC-50 official folds: train=1-3, validation=4, test=5",
                    fold_by_path,
                )

    indices = np.arange(len(paths))
    train_val, test = train_test_split(
        indices,
        test_size=0.20,
        random_state=seed,
        stratify=labels,
    )
    train, val = train_test_split(
        train_val,
        test_size=0.25,
        random_state=seed,
        stratify=labels[train_val],
    )
    return (
        {"train": train, "validation": val, "test": test},
        "stratified random 60/20/20",
        {},
    )


def save_split_manifest(
    output_path: Path,
    paths: list[Path],
    labels: np.ndarray,
    splits: dict[str, np.ndarray],
    dataset_dir: Path,
    source_folds: dict[str, int] | None = None,
) -> None:
    split_by_index = {
        int(index): split_name
        for split_name, indices in splits.items()
        for index in indices
    }
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("path", "class", "split", "source_fold")
        )
        writer.writeheader()
        for index, path in enumerate(paths):
            try:
                relative = path.relative_to(dataset_dir)
            except ValueError:
                relative = path
            relative_posix = relative.as_posix()
            writer.writerow(
                {
                    "path": relative_posix,
                    "class": CLASS_NAMES[int(labels[index])],
                    "split": split_by_index[index],
                    "source_fold": (source_folds or {}).get(relative_posix, ""),
                }
            )


def _callbacks(checkpoint_path: Path, patience: int):
    import tensorflow as tf

    return [
        tf.keras.callbacks.ModelCheckpoint(
            checkpoint_path,
            monitor="val_loss",
            save_best_only=True,
            verbose=0,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=max(2, patience // 2),
            min_lr=1e-6,
            verbose=1,
        ),
    ]


def _history_to_json(history: dict[str, list[Any]]) -> dict[str, list[float]]:
    return {key: [float(value) for value in values] for key, values in history.items()}


def train_experiment(
    optimizer_name: str,
    X: np.ndarray,
    y: np.ndarray,
    splits: dict[str, np.ndarray],
    experiments_dir: Path,
    epochs: int,
    batch_size: int,
    patience: int,
    class_weights: dict[int, float],
) -> dict[str, Any]:
    import tensorflow as tf

    print(f"\n=== Experimento: {optimizer_name.upper()} ===")
    tf.keras.backend.clear_session()
    model = build_cnn(X.shape[1:], len(CLASS_NAMES), optimizer_name)
    checkpoint = experiments_dir / f"{optimizer_name}.keras"
    history_obj = model.fit(
        X[splits["train"]],
        y[splits["train"]],
        validation_data=(X[splits["validation"]], y[splits["validation"]]),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=_callbacks(checkpoint, patience),
        class_weight=class_weights,
        verbose=2,
    )

    best_model = tf.keras.models.load_model(checkpoint)
    test_loss, test_accuracy = best_model.evaluate(
        X[splits["test"]], y[splits["test"]], verbose=0
    )
    probabilities = best_model.predict(X[splits["test"]], verbose=0)
    predictions = np.argmax(probabilities, axis=1)
    truth = y[splits["test"]]
    history = _history_to_json(history_obj.history)

    metrics = {
        "optimizer": optimizer_name,
        "epochs_executed": len(history["loss"]),
        "best_epoch": int(np.argmin(history["val_loss"])) + 1,
        "best_validation_accuracy": float(np.max(history["val_accuracy"])),
        "best_validation_loss": float(np.min(history["val_loss"])),
        "test_accuracy": float(test_accuracy),
        "test_loss": float(test_loss),
        "test_precision_macro": float(
            precision_score(truth, predictions, average="macro", zero_division=0)
        ),
        "test_recall_macro": float(
            recall_score(truth, predictions, average="macro", zero_division=0)
        ),
        "test_f1_macro": float(
            f1_score(truth, predictions, average="macro", zero_division=0)
        ),
    }
    (experiments_dir / f"history_{optimizer_name}.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    return {
        "metrics": metrics,
        "history": history,
        "checkpoint": checkpoint,
        "probabilities": probabilities,
        "predictions": predictions,
        "truth": truth,
        "parameter_count": int(best_model.count_params()),
    }


def plot_optimizer_comparison(experiments: list[dict[str, Any]], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    colors = {"adam": "#00b8d9", "sgd": "#7c5cff"}
    for experiment in experiments:
        name = experiment["metrics"]["optimizer"]
        history = experiment["history"]
        epochs = np.arange(1, len(history["loss"]) + 1)
        color = colors.get(name, None)
        axes[0].plot(epochs, history["accuracy"], color=color, label=f"{name.upper()} train")
        axes[0].plot(
            epochs,
            history["val_accuracy"],
            color=color,
            linestyle="--",
            label=f"{name.upper()} val",
        )
        axes[1].plot(epochs, history["loss"], color=color, label=f"{name.upper()} train")
        axes[1].plot(
            epochs,
            history["val_loss"],
            color=color,
            linestyle="--",
            label=f"{name.upper()} val",
        )

    axes[0].set(title="Accuracy por época", xlabel="Época", ylabel="Accuracy", ylim=(0, 1.03))
    axes[1].set(title="Loss por época", xlabel="Época", ylabel="Loss")
    for axis in axes:
        axis.grid(alpha=0.22)
        axis.legend(fontsize=8)
    fig.suptitle("Comparación controlada: Adam vs. SGD", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_confusion(
    truth: np.ndarray,
    predictions: np.ndarray,
    output: Path,
) -> np.ndarray:
    matrix = confusion_matrix(truth, predictions, labels=np.arange(len(CLASS_NAMES)))
    labels = [DISPLAY_LABELS[name] for name in CLASS_NAMES]
    display = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=labels)
    fig, axis = plt.subplots(figsize=(6.5, 5.8))
    display.plot(ax=axis, cmap="BuPu", colorbar=False, values_format="d")
    axis.set_title("Matriz de confusión - modelo seleccionado", fontweight="bold")
    axis.set_xlabel("Clase predicha")
    axis.set_ylabel("Clase real")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return matrix


def plot_architecture(input_shape: tuple[int, ...], output: Path) -> None:
    layers = [
        (f"Entrada\n{input_shape[0]}×{input_shape[1]}×1", "#dff8ff"),
        ("Conv 16\nReLU + Pool", "#bcecf5"),
        ("Conv 32\nReLU + Pool", "#9bdce9"),
        ("Conv 64\nReLU + Pool", "#80c7dc"),
        ("Estadísticas temporales\nMedia + máximo", "#a99cf4"),
        (f"Softmax\n{len(CLASS_NAMES)} clases", "#7c5cff"),
    ]
    fig, axis = plt.subplots(figsize=(13, 3.1))
    axis.set_xlim(0, len(layers) * 2.1)
    axis.set_ylim(0, 2.8)
    axis.axis("off")
    for index, (label, color) in enumerate(layers):
        x = index * 2.1 + 0.15
        text_color = "white" if index == len(layers) - 1 else "#13213c"
        axis.add_patch(
            plt.Rectangle((x, 0.8), 1.65, 1.15, facecolor=color, edgecolor="#1a4560", lw=1.2)
        )
        axis.text(x + 0.825, 1.375, label, ha="center", va="center", fontsize=9, color=text_color)
        if index < len(layers) - 1:
            axis.annotate("", xy=(x + 2.05, 1.375), xytext=(x + 1.67, 1.375), arrowprops={"arrowstyle": "->", "color": "#53657a"})
    axis.set_title("Arquitectura CNN compacta", fontsize=15, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight", transparent=False)
    plt.close(fig)


def write_model_summary(model_path: Path, output_path: Path) -> int:
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path, compile=False)
    buffer = io.StringIO()
    model.summary(print_fn=lambda line: buffer.write(line + "\n"))
    output_path.write_text(buffer.getvalue(), encoding="utf-8")
    return int(model.count_params())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default="dataset")
    parser.add_argument("--model-dir", default="model")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--optimizers",
        nargs="+",
        default=["adam", "sgd"],
        choices=("adam", "sgd"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise SystemExit("--epochs y --batch-size deben ser positivos.")

    dataset_dir = Path(args.dataset_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    results_dir = Path(args.results_dir).resolve()
    experiments_dir = model_dir / "experiments"
    model_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    experiments_dir.mkdir(parents=True, exist_ok=True)

    set_reproducible_seed(args.seed)
    paths, y, counts = discover_dataset(dataset_dir)
    splits, split_strategy, source_folds = make_splits(paths, y, args.seed, dataset_dir)
    save_split_manifest(
        results_dir / "dataset_split.csv",
        paths,
        y,
        splits,
        dataset_dir,
        source_folds,
    )
    X = load_features(paths)

    classes = np.unique(y[splits["train"]])
    weights = compute_class_weight("balanced", classes=classes, y=y[splits["train"]])
    class_weights = {int(label): float(weight) for label, weight in zip(classes, weights)}

    experiments: list[dict[str, Any]] = []
    for optimizer_name in dict.fromkeys(args.optimizers):
        experiments.append(
            train_experiment(
                optimizer_name,
                X,
                y,
                splits,
                experiments_dir,
                args.epochs,
                args.batch_size,
                args.patience,
                class_weights,
            )
        )

    # La selección se decide exclusivamente con validación; test queda para la
    # evaluación final y no controla qué modelo se publica.
    selected = max(
        experiments,
        key=lambda exp: (
            exp["metrics"]["best_validation_accuracy"],
            -exp["metrics"]["best_validation_loss"],
        ),
    )
    final_model_path = model_dir / "audio_classifier.keras"
    shutil.copy2(selected["checkpoint"], final_model_path)

    parameter_count = write_model_summary(final_model_path, results_dir / "model_summary.txt")
    plot_optimizer_comparison(experiments, results_dir / "optimizer_comparison.png")
    matrix = plot_confusion(
        selected["truth"], selected["predictions"], results_dir / "confusion_matrix.png"
    )
    plot_architecture(tuple(X.shape[1:]), results_dir / "architecture.png")

    report_dict = classification_report(
        selected["truth"],
        selected["predictions"],
        labels=np.arange(len(CLASS_NAMES)),
        target_names=list(CLASS_NAMES),
        output_dict=True,
        zero_division=0,
    )
    report_text = classification_report(
        selected["truth"],
        selected["predictions"],
        labels=np.arange(len(CLASS_NAMES)),
        target_names=list(CLASS_NAMES),
        zero_division=0,
    )
    (results_dir / "classification_report.txt").write_text(report_text, encoding="utf-8")
    (results_dir / "classification_report.json").write_text(
        json.dumps(report_dict, indent=2), encoding="utf-8"
    )

    test_indices = splits["test"]
    with (results_dir / "test_predictions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("path", "true_class", "predicted_class", "confidence", "correct"),
        )
        writer.writeheader()
        for local_index, dataset_index in enumerate(test_indices):
            predicted = int(selected["predictions"][local_index])
            truth = int(selected["truth"][local_index])
            writer.writerow(
                {
                    "path": paths[int(dataset_index)].relative_to(dataset_dir).as_posix(),
                    "true_class": CLASS_NAMES[truth],
                    "predicted_class": CLASS_NAMES[predicted],
                    "confidence": f"{float(np.max(selected['probabilities'][local_index])):.6f}",
                    "correct": predicted == truth,
                }
            )

    metrics_rows = [experiment["metrics"] for experiment in experiments]
    with (results_dir / "optimizer_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics_rows[0]))
        writer.writeheader()
        writer.writerows(metrics_rows)

    metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_file": final_model_path.name,
        "selected_optimizer": selected["metrics"]["optimizer"],
        "selection_rule": "highest validation accuracy, then lowest validation loss",
        "parameter_count": parameter_count,
        "input_shape": list(X.shape[1:]),
        "class_names": list(CLASS_NAMES),
        "display_labels": DISPLAY_LABELS,
        "preprocessing": AUDIO_CONFIG,
        "dataset": {
            "kind": "real_recordings",
            "source": "ESC-50" if source_folds else "custom",
            "total_samples": len(paths),
            "samples_per_class": counts,
            "split_sizes": {name: int(len(indices)) for name, indices in splits.items()},
            "seed": args.seed,
            "split_strategy": split_strategy,
        },
        "experiments": metrics_rows,
        "selected_test_metrics": selected["metrics"],
        "confusion_matrix": matrix.tolist(),
        "warning": None,
    }
    (model_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (results_dir / "metrics_summary.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== ENTRENAMIENTO COMPLETADO ===")
    print(f"Modelo seleccionado: {selected['metrics']['optimizer'].upper()}")
    print(f"Accuracy de test: {selected['metrics']['test_accuracy']:.4f}")
    print(f"Parámetros entrenables y no entrenables: {parameter_count:,}")
    print(f"Modelo: {final_model_path}")
    print(f"Resultados: {results_dir}")
if __name__ == "__main__":
    main()
