# Laya Prompt Classification - Setup

## What is implemented

Image/video prompt text is analyzed during the shared ingestion path, including re-ingestion, file watching, custom creation, and Threads extraction. Existing XX/XXX filters and endpoints remain available. The two labels are independent.

- XX questions use the supplied clothing/body-shape examples.
- XXX currently asks about visible nipples or exposed breasts. This provisional interpretation distinguishes clothed bust shape from exposure; verify it against your own examples.
- Assistant responses are excluded. User turns are combined in order, and Laya scans long text using overlapping token windows.
- Manual positive and negative decisions survive re-ingestion and index rebuilds in `backend/data/labels.sqlite3`.
- Unchanged successful analyses are cached by text, questions, model revision, package version, and threshold. Errors/uncertain results are retried on subsequent ingestion.

## Installation

From the repository root in PowerShell:

```powershell
rtk proxy .venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-laya.txt
rtk proxy npm --prefix frontend install
```

The implementation session installed Laya 0.4.9 into the project virtual environment. The installed PyTorch build is CPU-only; inference speed is hardware-dependent. Select an appropriate PyTorch GPU build separately if needed. The first enabled analysis downloads the pinned checkpoint; later calls reuse the model/cache.

## Start in review mode

Copy settings from `backend/.env.laya.example` into the existing `backend/.env`, keeping existing credentials and settings:

```dotenv
LAYA_MODE=review
LAYA_MODEL=convaiinnovations/laya-multilingual
LAYA_MODEL_REVISION=e4e9ddf21a7b1903b7acffd8814ad4307bf63a67
LAYA_LABEL_THRESHOLD=
```

Restart the backend. Its normal startup ingestion will analyze eligible prompts; the existing re-ingest action also runs analysis. Review mode records suggestions but does not apply them to flags. Without an explicit setting, `LAYA_MODE` defaults to `off`; this implementation did not modify your environment file or automatically label your collection.

The conversation view shows status, raw scores, suggestions, and manual overrides. Scores are model outputs, not verified accuracy percentages. "Use automatic" clears a manual override; future automatic results can then apply. Clearing an override does not enable apply mode or accept a review suggestion.

The backend terminal logs `[Laya] Loading`, `Model ready`, `Analyzing`, and `Result` messages. Each result includes the document ID, inference/cache source, mode, status, XX/XXX suggestions, scores, and effective flags after manual overrides. These are backend logs, not browser-console messages. Configuration failures report the required setting; raw prompt text is not logged.

There is no separate classifier-results JSON file. Results are JSON metadata in the `metadata` column of the SQLite `labels` table, by default in `backend/data/labels.sqlite3` (or `LABEL_DB_PATH`). The conversation detail API returns them under `label_analysis`. Label questions are defined in `QUESTIONS` in `backend/laya_classifier.py`. The evaluation CLI writes a standalone JSON report only when called with `--output`.

## Enable automatic application after evaluation

Set `LAYA_MODE=apply` and supply a validated `LAYA_LABEL_THRESHOLD` greater than 0.5 and at most 1, then restart/re-ingest. A score at or above the threshold marks a label; a score at or below one minus the threshold clears it. Scores between those bounds need review and preserve the previously applied value. Each manual override takes precedence.

Missing/invalid thresholds, model failures, truncated inputs, and malformed probabilities never become successful negative decisions. Prompt content remains ingestible when model inference fails. Saved overrides whose search projection fails show pending sync and can be retried or recovered through re-ingestion.

Legacy true flags migrate as manual positives. Historical false values cannot distinguish a default from a deliberate unmarking; review the initial suggestions before enabling automatic backfill.

## Evaluate your labels

Prepare a JSON list with `prompt`, `is_xx`, and `is_xxx` fields. The included synthetic fixture illustrates the format; its labels are provisional examples, not a user-approved training dataset.

```powershell
rtk proxy .venv\Scripts\python.exe backend/evaluate_laya.py backend/test_data/laya_labels.json --output scratch/laya-evaluation.json
```

The evaluator defaults to the pinned multilingual checkpoint; `LAYA_MODEL` and `LAYA_MODEL_REVISION` can select a different checkpoint. It uses raw 0.5 decisions, reports per-label precision/recall, and omits prompt text from its report. It does not write application labels. Use a separate held-out set to choose a deployment threshold; fine-tune only if the measured results require it. No fine-tuning was performed during implementation.

## Verification and limitations

```powershell
rtk proxy .venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
rtk proxy .venv\Scripts\python.exe -m pytest backend/test_laya.py backend/test_label_integration.py -q
rtk proxy npm --prefix frontend run build
```

Integration checks cover manual true/false decisions, reset, clean-index restoration, failure preservation, retry caching, malformed/truncated results, a concurrent override, and ingestion beyond 1,000 documents. A separate smoke test exercised real Laya inference and a temporary local Meilisearch index without altering the main collection. Browser checks cover keyboard activation, failure recovery, override reset, responsive widths, and touch targets.

Keep the SQLite file on persistent storage and include it in backups. `LABEL_DB_PATH` can override its location. Manual history cannot be recovered if both that store and its backup are lost. Stable source IDs are required; content-derived IDs can change when exports change. Projection locking currently supports one API process; coordinate across processes before using multiple workers.

Classification quality is not yet sufficient to recommend unattended labeling. On the final 12-case synthetic pilot, XX precision was 75% and recall was 85.7%; XXX precision was 60% and recall was 100%. These fixtures were also used to refine the questions, so the figures are development checks, not held-out validation. Review mode is the recommended starting point for your own collection. The built-in labels do not yet cover violence, hate, self-harm, or other unspecified mappings.
