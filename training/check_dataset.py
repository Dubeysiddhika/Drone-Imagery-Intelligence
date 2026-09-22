from pathlib import Path

DATASET = Path("../dataset")

CLASS_COUNT = 3


def check_split(split):
    image_dir = DATASET / "images" / split
    label_dir = DATASET / "labels" / split

    images = list(image_dir.glob("*"))

    print(f"\nChecking {split} dataset...")
    print(f"Images found: {len(images)}")

    errors = 0

    for image in images:
        label = label_dir / f"{image.stem}.txt"

        if not label.exists():
            print(f"Missing label: {image.name}")
            errors += 1
            continue

        with open(label, "r") as file:
            for line_number, line in enumerate(file, start=1):
                values = line.strip().split()

                if len(values) != 5:
                    print(
                        f"Invalid annotation: {label} "
                        f"line {line_number}"
                    )
                    errors += 1
                    continue

                try:
                    class_id = int(values[0])
                    coordinates = list(map(float, values[1:]))

                    if not 0 <= class_id < CLASS_COUNT:
                        print(
                            f"Invalid class ID in {label}: "
                            f"{class_id}"
                        )
                        errors += 1

                    for value in coordinates:
                        if not 0 <= value <= 1:
                            print(
                                f"Invalid coordinate in {label}: "
                                f"{value}"
                            )
                            errors += 1

                except ValueError:
                    print(
                        f"Invalid numbers in {label} "
                        f"line {line_number}"
                    )
                    errors += 1

    if errors == 0:
        print(f"{split}: OK")
    else:
        print(f"{split}: {errors} error(s)")


for split in ["train", "val", "test"]:
    check_split(split)
