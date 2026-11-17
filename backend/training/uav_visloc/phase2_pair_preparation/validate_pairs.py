from __future__ import annotations

import csv
from pathlib import Path

OUTPUT_DIR = Path(r"E:\Drone-image-intelligence\backend\training\uav_visloc\phase2_pair_preparation")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    positive = read_csv(OUTPUT_DIR / "positive_pairs.csv")
    negative = read_csv(OUTPUT_DIR / "negative_pairs.csv")
    uncertain = read_csv(OUTPUT_DIR / "uncertain_pairs.csv")

    positive_count = len(positive)
    negative_count = len(negative)
    uncertain_count = len(uncertain)

    assert all(row["pair_type"] == "candidate_positive" for row in positive)
    assert all(row["pair_type"] == "candidate_negative" for row in negative)
    assert all(row["pair_type"] == "uncertain" for row in uncertain)

    # We intentionally keep uncertain pairs separate from the confirmed positive set.
    confirmed_total = positive_count + negative_count
    print(f"Confirmed pairs: {confirmed_total}")
    print(f"Positive pairs: {positive_count}")
    print(f"Negative pairs: {negative_count}")
    print(f"Uncertain pairs: {uncertain_count}")
    print("Uncertain pairs excluded from confirmed training set: True")


if __name__ == "__main__":
    main()
