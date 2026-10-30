# VisDrone ten-class training handoff

## Status and evidence

This is the separate `visdrone10_yolo11n` YOLO11n detection run. It does not
replace or modify the two-class `person`/`vehicle` baseline.

The saved run in `runs/visdrone10_yolo11n/` contains `weights/last.pt`,
`weights/best.pt`, `results.csv`, `args.yaml`, and the saved
`resume_training.log`. Both checkpoint files were
15,906,853 bytes with SHA-256
`d20eb4bd0124f63b33c510d082cf39c77556b972511f22f5affc37dca35fc6f0` at audit
time. They contain the same bytes. The checkpoints are stored through Git LFS;
the exact hashes, sizes, and dataset file hashes are recorded in
[`visdrone10_dataset_manifest.json`](./visdrone10_dataset_manifest.json).

`results.csv` contains seven completed epoch records (epochs 1–7). The
checkpoint records zero-based epoch index 6, ten class names, optimizer state,
and scaler state; its saved target is 100 epochs. The saved training therefore
has 7 completed epochs and 93 planned epochs remaining. A later
`resume_training.log` shows progress into epoch 8 but ends mid-epoch; that
partial epoch is not represented in the stable checkpoint or completed
`results.csv` row and must not be counted as completed. The checkpoint was
saved by Ultralytics 8.4.155. No `results.png` was present.

Verified settings from the saved checkpoint and `args.yaml`:

| Setting | Saved value |
|---|---|
| Image size | 640 |
| Batch size | 2 |
| Device | CPU |
| Optimizer | `auto` |
| Initial/final LR factor | `lr0=0.01`, `lrf=0.01` |
| Momentum / weight decay | `0.937` / `0.0005` |
| Warmup | 3 epochs |
| Workers | 0 |
| Patience | 100 |
| Seed / deterministic | 42 / true |
| Ultralytics | 8.4.155 |

The trained class IDs and names, in order, are:

| YOLO ID | VisDrone category | Name |
|---:|---:|---|
| 0 | 1 | pedestrian |
| 1 | 2 | people |
| 2 | 3 | bicycle |
| 3 | 4 | car |
| 4 | 5 | van |
| 5 | 6 | truck |
| 6 | 7 | tricycle |
| 7 | 8 | awning-tricycle |
| 8 | 9 | bus |
| 9 | 10 | motor |

This mapping is checked against the saved checkpoint and the dedicated
[`configs/visdrone10.yaml`](../configs/visdrone10.yaml). Do not use
[`dataset/data.yaml`](../dataset/data.yaml) or
[`training/data.yaml`](../training/data.yaml); both describe the separate
two-class baseline.

## Dataset and transfer

The run used the VisDrone2019-DET training and validation release. The converted
YOLO dataset was at `dataset_visdrone10_yolo/`: 6,471 train images/labels and
548 validation images/labels, 14,038 checksummed image/label files. The
conversion report recorded 343,204 train boxes and 38,759 validation boxes.
The SHA-256 manifest covers each of those files and records the expected
directory layout and class mapping.

The raw source, repaired staging tree, and converted images/labels are local
data, not GitHub contents. At audit time they occupied approximately 3.27 GB,
1.64 GB, and 1.66 GB respectively. Obtain the converted
`dataset_visdrone10_yolo/` tree from the team's approved large-file transfer
storage, preserving its directory structure, and place it at the repository
root. No shared transfer location is configured by this repository, so a
teammate must arrange that transfer before resuming. Do not put the images or
raw VisDrone archives into ordinary Git or Git LFS.

Alternatively, obtain the official VisDrone2019-DET train and validation
archives from the [VisDrone dataset repository](https://github.com/VisDrone/VisDrone-Dataset)
under its terms, extract them without editing the original annotations to
`dataset_visdrone10_source/`, and recreate the staged and YOLO trees using the
tracked scripts:

```powershell
python -m pip install -r .\requirements-visdrone10.txt
python .\scripts\verify_visdrone_source.py --source .\dataset_visdrone10_source
python .\scripts\stage_visdrone_source.py --source .\dataset_visdrone10_source --output .\dataset_visdrone10
python .\scripts\verify_visdrone_source.py --source .\dataset_visdrone10
python .\scripts\convert_visdrone10_yolo.py --source .\dataset_visdrone10 --output .\dataset_visdrone10_yolo
```

The stage and conversion scripts refuse to overwrite existing output trees.
The conversion preserves the documented category mapping, ignores categories
0 and 11, and excludes the three known zero-area rows from generated labels.
See [`visdrone10-dataset.md`](./visdrone10-dataset.md) for source verification,
repair, and conversion details. The local repair/conversion reports were
verified and included as portable snapshots:
[`visdrone10_conversion_report.json`](./visdrone10_conversion_report.json) and
[`visdrone10_repair_report.json`](./visdrone10_repair_report.json). Their
relative paths, along with the run history, saved arguments, class YAML, and
resume scripts, are also SHA-256 recorded in the committed manifest.

## Fetch the handoff branch and LFS weights

For a new clone:

```powershell
git clone --branch handoff/visdrone10-training-resume --single-branch https://github.com/Dubeysiddhika/Drone-Imagery-Intelligence.git
Set-Location .\Drone-Imagery-Intelligence
git lfs pull
```

For an existing clone:

```powershell
git fetch origin handoff/visdrone10-training-resume
git switch --track -c handoff/visdrone10-training-resume origin/handoff/visdrone10-training-resume
git lfs pull origin handoff/visdrone10-training-resume
```

Then transfer the converted dataset to the repository-root
`dataset_visdrone10_yolo/` path, or recreate it using the commands above.
Git/LFS supplies the checkpoint and metadata; it does not supply the dataset.

## Install and verify

Use Python 3.14.3 or another Python version supported by the pinned packages.
The captured environment was Python 3.14.3, Ultralytics 8.4.155,
PyTorch 2.14.0+cpu, torchvision 0.29.0+cpu, PyYAML 6.0.3, and Pillow 12.3.0.
Create and activate a virtual environment, then install:

```powershell
py -3.14 -m venv .venv-visdrone10
.\.venv-visdrone10\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-visdrone10.txt
```

After transferring or recreating the converted dataset, verify both checkpoint
hashes, checkpoint resume state and classes, all required handoff files, the
ten-class YAML, directory counts, and every dataset image/label SHA-256:

```powershell
python .\scripts\verify_visdrone10_handoff.py
```

The verifier must finish successfully before training. It intentionally reports
an error if LFS supplied a pointer instead of the checkpoint or if even one
dataset file differs from the saved run's manifest.

To regenerate the manifest after intentionally changing a checkpoint, dataset,
or handoff metadata, use:

```powershell
python .\scripts\create_visdrone10_dataset_manifest.py --overwrite
```

Review and commit the regenerated manifest with the changed files.

## Resume the existing run

Run this from the repository root after verification:

```powershell
python .\scripts\resume_visdrone10.py
```

The resume script checks the checkpoint's optimizer state and ten-class names,
checks the train/validation image directories, sets portable repository-local
Ultralytics paths, and calls the installed Ultralytics resume API with the
existing `last.pt`, the handoff YAML, and the original run directory as its
explicit save destination. It writes a temporary runtime YAML with the
repository-local dataset path resolved to an absolute path, avoiding
Ultralytics' user-specific default dataset directory. Ultralytics restores the saved
optimizer, scaler, epoch, and training arguments (including the 100-epoch
target); the explicit YAML argument replaces the original machine-specific
dataset path. Do not use `scripts/train_visdrone10.py` for this: that script is
for a fresh run and deliberately refuses an existing run directory.

To confirm continuation, the console must say it is resuming from the specified
`last.pt` and report a start epoch later than the checkpoint's saved epoch.
While training proceeds, `results.csv` should grow beyond its seven completed
records, and the checkpoint's saved epoch should advance. For example, before
launching training, record the completed-row count:

```powershell
$before = (Import-Csv .\runs\visdrone10_yolo11n\results.csv).Count
python .\scripts\resume_visdrone10.py
```

After training exits successfully:

```powershell
$after = (Import-Csv .\runs\visdrone10_yolo11n\results.csv).Count
if ($after -le $before) { throw "No new completed training epochs were recorded." }
```

The saved run is incomplete; resuming can take a long time, especially on CPU.
Do not delete or replace `last.pt`, `best.pt`, `results.csv`, or `args.yaml`
before the resume. If another interruption occurs, rerun the same resume
command against the newly saved `last.pt`.

## Evaluate after training

Use the project evaluation script with the ten-class checkpoint, dedicated
ten-class YAML, and validation split (the converted dataset has no independent
test split):

```powershell
python .\training\evaluate.py `
  --model .\runs\visdrone10_yolo11n\weights\best.pt `
  --data .\configs\visdrone10.yaml `
  --split val `
  --imgsz 640 `
  --batch 2
```

Keep these native ten-class validation results separate from the two-class
baseline metrics. The historical epoch metrics in `results.csv` are not a
completed-run evaluation.
