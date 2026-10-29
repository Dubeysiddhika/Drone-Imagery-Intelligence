from pathlib import Path

import yaml
from ultralytics import YOLO, settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"
DATASET_DIR = PROJECT_ROOT / "dataset_visdrone10_yolo"
DATASET_PATH = DATASET_DIR / "data.yaml"
MODEL_PATH = PROJECT_ROOT / "training" / "yolo11n.pt"

# Ensure Ultralytics resolves project-local output and dataset paths in this repo.
settings["runs_dir"] = str(RUNS_DIR)
settings["datasets_dir"] = str(PROJECT_ROOT)


def load_dataset_config():
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Ten-class VisDrone dataset YAML not found: {DATASET_PATH}")
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Base model checkpoint not found: {MODEL_PATH}")

    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    names = data.get("names", {})
    if isinstance(names, dict):
        class_names = [str(names[index]) for index in sorted(int(index) for index in names)]
    else:
        class_names = [str(name) for name in names]

    if len(class_names) != 10:
        raise ValueError(
            f"Expected exactly 10 dataset classes in {DATASET_PATH}, found {len(class_names)}."
        )

    data["path"] = str(DATASET_DIR)
    return data, class_names


def main():
    dataset_config, class_names = load_dataset_config()
    model = YOLO(str(MODEL_PATH))
    print(f"Using base model: {MODEL_PATH}")
    print(f"Using dataset YAML: {DATASET_PATH}")
    print(f"Using classes: {class_names}")
    print(f"Ultralytics runs_dir: {settings['runs_dir']}")
    print(f"Ultralytics datasets_dir: {settings['datasets_dir']}")
    model.train(
        data=str(DATASET_PATH),
        epochs=50,
        imgsz=640,
        batch=8,
        workers=4,
        project=str(RUNS_DIR),
        name="drone_visdrone10",
    )
    print("Training completed.")
    print("Best model should be saved inside:")
    print(str(RUNS_DIR / "drone_visdrone10" / "weights" / "best.pt"))


if __name__ == "__main__":
    main()