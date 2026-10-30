# VisDrone ten-class model comparison

**Status: incomplete — a resumable ten-class checkpoint is available, but training has not completed.**
Inspection date: 2026-10-30

## Checkpoint and dataset verification

| Model | Checkpoint | Classes | Training evidence |
|---|---|---|---|
| Existing baseline | `runs/drone_person_vehicle/weights/best.pt` | `person`, `vehicle` | Checkpoint metadata records epoch 17 (the 18th completed epoch) of a 50-epoch configuration. |
| Ten-class model | `runs/visdrone10_yolo11n/weights/last.pt` and `best.pt` | `pedestrian`, `people`, `bicycle`, `car`, `van`, `truck`, `tricycle`, `awning-tricycle`, `bus`, `motor` | Checkpoint epoch index 6 and `results.csv` confirm seven completed epochs of 100; optimizer state is present for resume. The log reaches a partial epoch 8, which is not a completed checkpoint. |

The baseline checkpoint metadata and `dataset/data.yaml` agree on its two classes. Its recorded training configuration uses `imgsz=640`; the baseline YAML defines `images/train`, `images/val`, and `images/test`. The baseline validation tree currently contains 548 images and 548 labels.

The ten-class checkpoint names match the dedicated `configs/visdrone10.yaml` and the converted dataset's class mapping. The converted YAML defines train and validation paths (no separate test split). Its validation tree contains 548 images and 548 labels, with instances of all ten classes. The baseline and ten-class validation directories have the same 548 image filenames.

The existing baseline is a valid two-class model, but the ten-class training run has not completed. Therefore **no completed-model evaluation or paired model comparison is reported here**. In particular, epoch-level training validation results are not presented as completed-model results.

## Available metrics (kept separate)

The baseline run's `results.csv` records the following validation metrics at epoch 18, which corresponds to the saved checkpoint's epoch index 17:

| Model / task | Precision | Recall | mAP@0.5 | mAP@0.5:0.95 | Basis |
|---|---:|---:|---:|---:|---|
| Two-class baseline (`person`, `vehicle`) | 0.63156 | 0.44119 | 0.48010 | 0.25045 | Recorded in `runs/drone_person_vehicle/results.csv`; not a re-run in a shared evaluation session. |
| Ten-class VisDrone model | Not reported | Not reported | Not reported | Not reported | No completed-run metrics available. |

These are not comparable scores: the baseline predicts two merged categories, while the ten-class task predicts ten distinct categories. The numbers also come from the baseline's recorded training-time validation, not a paired evaluation conducted under a common protocol.

## Class-definition differences and expected behavior

The baseline conversion in `training/convert_visdrone.py` maps VisDrone `pedestrian` and `people` to `person`, and maps `car`, `van`, `truck`, `bus`, and `motor` to `vehicle`. It does not include `bicycle`, `tricycle`, or `awning-tricycle` in either baseline class. The ten-class dataset retains these categories separately.

Consequently, a baseline prediction of `vehicle` cannot distinguish a car from a van, bus, truck, or motor; the ten-class model is designed to make those distinctions, as well as distinguish `pedestrian` from `people` and recognize bicycle/tricycle categories. Such finer distinctions can also introduce confusions between similar classes. These are differences in task definition, not evidence that either model performs better; no ten-class class-wise metrics or prediction examples are available from a completed checkpoint.

## Comparison protocol after ten-class training is complete

1. Evaluate each model on its own declared validation labels and publish separate native-task reports, including per-class metrics where supported.
2. For a meaningful shared two-class view, use the common 548 validation image filenames and construct labels from the ten-class annotations: `pedestrian` + `people` → `person`; `car` + `van` + `truck` + `bus` + `motor` → `vehicle`. Handle ignored regions consistently. Exclude bicycle, tricycle, and awning-tricycle objects from the two-class ground truth as the baseline training conversion does.
3. Map ten-class predictions to the common taxonomy by taking the highest confidence among source classes for each merged class, and exclude detections from classes outside the shared taxonomy. Apply the same image size, confidence/IoU settings, and matching implementation to both models; document the mapping and ignored-object policy with the resulting metrics. Keep these common-subset results separate from each model's native-task metrics.
4. Benchmark inference on the same machine and software environment, using the same 640-pixel input size and batch size (preferably batch 1 for per-image latency). Use identical preprocessing/NMS settings, warm up both models, repeat the same validation images, and report latency distribution plus peak process memory. Measure model loading separately. Do not compare historical training times as inference performance.

The currently inspected local runtime is Python 3.14.3, Ultralytics 8.4.155, PyTorch 2.14.0 CPU-only. No paired latency or resource measurements were made because ten-class training is not complete.

## Limitations and next steps

- The project documents train and validation splits, not an independent test split. Validation results must not be described as generalization to unseen test data.
- The same validation filenames do not make native metrics interchangeable: the class taxonomies and label coverage differ.
- Baseline validation scores are historical run records; exact hardware and runtime parity with a future ten-class evaluation has not been established.
- Resume the saved `last.pt` using the handoff instructions, then verify the completed run's `weights/best.pt` class names and completion metadata before running the native and common-subset evaluations and paired inference benchmark above.
- Neither model weights nor dataset files were modified for this report.
