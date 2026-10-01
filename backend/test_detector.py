"""Run the trained detector against one untouched dataset test image."""

from pathlib import Path

from app.services.detector import MODEL_PATH, detect_objects


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGE_DIR = PROJECT_ROOT / "dataset" / "images" / "test"


def main() -> None:
    test_images = sorted(TEST_IMAGE_DIR.glob("*"))
    if not test_images:
        raise FileNotFoundError(f"No test images found in {TEST_IMAGE_DIR}")

    image_path = test_images[0]
    detections = detect_objects(image_path)
    print(f"Model: {MODEL_PATH}")
    print(f"Image: {image_path}")
    print(f"Detection count: {len(detections)}")
    for detection in detections:
        print(detection)


if __name__ == "__main__":
    main()