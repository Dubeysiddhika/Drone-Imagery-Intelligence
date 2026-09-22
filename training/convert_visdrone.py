from pathlib import Path
import shutil
import random
import cv2


# ============================================================
# CONFIGURATION
# ============================================================

# Location of the extracted VisDrone dataset
VISDRONE_ROOT = Path(r"D:\Download copy\archive")

# Location of your project, based on this script's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Output YOLO dataset
OUTPUT_ROOT = PROJECT_ROOT / "dataset"


# ============================================================
# CLASSES
# ============================================================

# Our simplified project classes
#
# 0 = person
# 1 = vehicle

CLASS_NAMES = {
    0: "person",
    1: "vehicle"
}


# VisDrone original categories:
#
# 1  = pedestrian
# 2  = people
# 4  = car
# 5  = van
# 6  = truck
# 9  = bus
# 10 = motor
#
# We convert them into:
#
# pedestrian + people -> person
# car + van + truck + bus + motor -> vehicle

PERSON_CLASSES = {1, 2}
VEHICLE_CLASSES = {4, 5, 6, 9, 10}


# Reproducible random split
random.seed(42)


# ============================================================
# CREATE DIRECTORIES
# ============================================================

def create_directories():

    for split in ["train", "val", "test"]:

        image_dir = OUTPUT_ROOT / "images" / split
        label_dir = OUTPUT_ROOT / "labels" / split

        image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        label_dir.mkdir(
            parents=True,
            exist_ok=True
        )


# ============================================================
# CONVERT VISDRONE ANNOTATION TO YOLO
# ============================================================

def convert_annotation(
    annotation_file,
    image_width,
    image_height
):

    yolo_annotations = []

    with open(
        annotation_file,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            values = line.split(",")

            # VisDrone annotation has 8 fields
            if len(values) < 6:
                continue

            try:

                x = float(values[0])
                y = float(values[1])

                width = float(values[2])
                height = float(values[3])

                score = int(values[4])
                category = int(values[5])

            except ValueError:

                continue

            # Ignore ignored regions
            if score == 0:
                continue

            # --------------------------------------------
            # PERSON
            # --------------------------------------------

            if category in PERSON_CLASSES:

                class_id = 0

            # --------------------------------------------
            # VEHICLE
            # --------------------------------------------

            elif category in VEHICLE_CLASSES:

                class_id = 1

            # --------------------------------------------
            # OTHER VISDRONE CLASSES
            # --------------------------------------------

            else:

                continue

            # --------------------------------------------
            # Convert bounding box to YOLO format
            # --------------------------------------------

            x_center = x + width / 2
            y_center = y + height / 2

            x_center = x_center / image_width
            y_center = y_center / image_height

            width = width / image_width
            height = height / image_height

            # Keep values between 0 and 1
            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            width = max(0.0, min(1.0, width))
            height = max(0.0, min(1.0, height))

            annotation = (
                f"{class_id} "
                f"{x_center:.6f} "
                f"{y_center:.6f} "
                f"{width:.6f} "
                f"{height:.6f}"
            )

            yolo_annotations.append(annotation)

    return yolo_annotations


# ============================================================
# PROCESS ONE IMAGE
# ============================================================

def process_image(
    image_file,
    annotation_file,
    output_split
):

    # Read image
    image = cv2.imread(str(image_file))

    if image is None:

        print(
            f"WARNING: Cannot read image: "
            f"{image_file.name}"
        )

        return False

    image_height, image_width = image.shape[:2]

    # Convert annotation
    yolo_annotations = convert_annotation(
        annotation_file,
        image_width,
        image_height
    )

    # Destination image
    destination_image = (
        OUTPUT_ROOT
        / "images"
        / output_split
        / image_file.name
    )

    # Destination label
    destination_label = (
        OUTPUT_ROOT
        / "labels"
        / output_split
        / f"{image_file.stem}.txt"
    )

    # Copy image
    shutil.copy2(
        image_file,
        destination_image
    )

    # Write YOLO label
    with open(
        destination_label,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "\n".join(yolo_annotations)
        )

    return True


# ============================================================
# PROCESS TRAINING DATA
# ============================================================

def process_training_dataset():

    source_folder = (
        VISDRONE_ROOT
        / "VisDrone2019-DET-train"
        / "VisDrone2019-DET-train"
    )

    images_folder = source_folder / "images"
    annotations_folder = source_folder / "annotations"

    if not images_folder.exists():

        print("ERROR: Training images folder not found:")
        print(images_folder)

        return

    if not annotations_folder.exists():

        print("ERROR: Training annotations folder not found:")
        print(annotations_folder)

        return

    image_files = sorted(
        [
            file
            for file in images_folder.iterdir()
            if file.suffix.lower()
            in [".jpg", ".jpeg", ".png"]
        ]
    )

    print()
    print("=" * 60)
    print("VISDRONE TRAINING DATA")
    print("=" * 60)

    print(f"Total images: {len(image_files)}")

    # Shuffle images
    random.shuffle(image_files)

    # 90% train
    # 10% test
    split_index = int(
        len(image_files) * 0.90
    )

    train_images = image_files[:split_index]
    test_images = image_files[split_index:]

    print(f"Training images: {len(train_images)}")
    print(f"Test images:     {len(test_images)}")

    # --------------------------------------------
    # TRAIN
    # --------------------------------------------

    print()
    print("Processing TRAIN...")

    processed = 0

    for image_file in train_images:

        annotation_file = (
            annotations_folder
            / f"{image_file.stem}.txt"
        )

        if not annotation_file.exists():

            print(
                f"WARNING: Missing annotation: "
                f"{image_file.name}"
            )

            continue

        success = process_image(
            image_file,
            annotation_file,
            "train"
        )

        if success:

            processed += 1

            if processed % 500 == 0:

                print(
                    f"Processed {processed} "
                    f"training images..."
                )

    print(
        f"TRAIN complete: {processed}"
    )

    # --------------------------------------------
    # TEST
    # --------------------------------------------

    print()
    print("Processing TEST...")

    processed = 0

    for image_file in test_images:

        annotation_file = (
            annotations_folder
            / f"{image_file.stem}.txt"
        )

        if not annotation_file.exists():

            print(
                f"WARNING: Missing annotation: "
                f"{image_file.name}"
            )

            continue

        success = process_image(
            image_file,
            annotation_file,
            "test"
        )

        if success:

            processed += 1

            if processed % 100 == 0:

                print(
                    f"Processed {processed} "
                    f"test images..."
                )

    print(
        f"TEST complete: {processed}"
    )


# ============================================================
# PROCESS VALIDATION DATA
# ============================================================

def process_validation_dataset():

    source_folder = (
        VISDRONE_ROOT
        / "VisDrone2019-DET-val"
        / "VisDrone2019-DET-val"
    )

    images_folder = source_folder / "images"
    annotations_folder = source_folder / "annotations"

    if not images_folder.exists():

        print()
        print(
            "ERROR: Validation images folder not found:"
        )

        print(images_folder)

        return

    if not annotations_folder.exists():

        print()
        print(
            "ERROR: Validation annotations folder not found:"
        )

        print(annotations_folder)

        return

    image_files = sorted(
        [
            file
            for file in images_folder.iterdir()
            if file.suffix.lower()
            in [".jpg", ".jpeg", ".png"]
        ]
    )

    print()
    print("=" * 60)
    print("VISDRONE VALIDATION DATA")
    print("=" * 60)

    print(
        f"Validation images: {len(image_files)}"
    )

    processed = 0

    for image_file in image_files:

        annotation_file = (
            annotations_folder
            / f"{image_file.stem}.txt"
        )

        if not annotation_file.exists():

            print(
                f"WARNING: Missing annotation: "
                f"{image_file.name}"
            )

            continue

        success = process_image(
            image_file,
            annotation_file,
            "val"
        )

        if success:

            processed += 1

            if processed % 100 == 0:

                print(
                    f"Processed {processed} "
                    f"validation images..."
                )

    print(
        f"VALIDATION complete: {processed}"
    )


# ============================================================
# CREATE DATA.YAML
# ============================================================

def create_data_yaml():

    yaml_file = OUTPUT_ROOT / "data.yaml"

    yaml_content = """path: D:/Drone-image-intelligence/dataset

train: images/train
val: images/val
test: images/test

names:
  0: person
  1: vehicle
"""

    with open(
        yaml_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(yaml_content)

    print()
    print("Created:")
    print(yaml_file)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("VISDRONE -> YOLO DATASET CONVERTER")
    print("=" * 60)

    print()
    print("VisDrone source:")
    print(VISDRONE_ROOT)

    print()
    print("Project:")
    print(PROJECT_ROOT)

    print()
    print("Output dataset:")
    print(OUTPUT_ROOT)

    # Create directories
    create_directories()

    # Process train + test
    process_training_dataset()

    # Process validation
    process_validation_dataset()

    # Create data.yaml
    create_data_yaml()

    print()
    print("=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)

    print()
    print("Classes:")
    print("0 = person")
    print("1 = vehicle")

    print()
    print("Dataset location:")
    print(OUTPUT_ROOT)

    print()
    print("Next command:")
    print(
        "python check_dataset.py"
    )


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()