# Laya Prompt Classification - Implementation Plan

Date: 2026-10-17
Status: Implemented with opt-in review/application modes. Automatic application remains off pending domain validation.
Setup and operating instructions: [Laya Prompt Classification - Setup.md](./Laya%20Prompt%20Classification%20-%20Setup.md).

## 1. Objective and scope

Automatically classify image/video generation **text prompts** during ingestion and re-ingestion, using the existing XX and XXX flags and filters. Preserve existing prompt parsing, APIs, search behavior, favorites, and manual tagging.

Initial scope is the user's XX/XXX examples below. Offensive, violent, hateful, and self-harm categories can be defined separately later; they have no agreed XX/XXX mapping yet. Generic "policy-violating" classification is excluded. Fine-tuning is not required to begin evaluation.

## 2. Initial label definitions

| Label | Positive examples supplied by the user | Context requirement |
| --- | --- | --- |
| XX | high slit, large V neckline, big bust, curvy, S-curve, curves | The text requests these clothing or human-body attributes. |
| XXX | boob, nipple | Provisional interpretation of the user's second list: requested breast/nipple depiction. |

These are project-specific labels, not universal safety ratings. "Boob" overlaps with XX's "big bust"; the distinction between clothed body shape and requested exposure needs labeled examples before automatic marking is enabled. Do not silently replace the supplied definition with a different moderation standard.

Keep XX and XXX as independent booleans, matching the current application. A prompt requesting both sets of attributes may receive both labels. Do not introduce exclusive-category behavior without an explicit product decision.

Negated instructions, exclusions, unrelated word senses, and quoted discussion need contextual evaluation. For example, "S-curve road" is not a body-shape request, and "no visible nipples" alone should not trigger XXX. A negative clause does not cancel a separate positive request elsewhere.

## 3. Existing flow and integration boundaries

```text
JSON source / custom prompt / Threads export / file watcher
  -> ingest_file -> source parser -> classify_document
  -> load existing metadata and durable label decisions
  -> Laya classification for eligible new, changed, or unprocessed text
  -> merge automatic results with manual overrides
  -> Meilisearch -> existing search, navigation, badges, and buttons
```

- `backend/ingestor.py`: shared ingestion path and Meilisearch settings.
- `backend/classifier.py`: existing image/video intent and keyword classification; keep this deterministic logic intact.
- `backend/parser.py`, `backend/grok_parser.py`, `backend/threads_parser.py`: supply normalized prompt data; inspect their turn shapes before implementing extraction.
- `backend/main.py`: manual XX/XXX PATCH endpoints and custom-prompt creation.
- `frontend/src/components/XxButton.jsx`, `XxxButton.jsx`: retain existing manual controls.
- Search results, tree navigation, and statistics already consume `is_xx` / `is_xxx`; preserve their contracts.

GitNexus MCP identified four direct callers of `ingest_file`: `ingest_all`, `extract_threads`, `create_custom_prompt`, and the watch handler's `_process`. Upstream impact analysis rated both `ingest_file` and `classify_document` CRITICAL because these paths share ingestion. Run fresh impact checks before changing symbols; this rating describes dependency reach, not a demonstrated defect.

## 4. Classification behavior

1. Keep existing parsing and type detection. Classify documents of type `image_prompt`, `video_prompt`, or `both`; skip media records and ordinary conversations initially.
2. Extract generation requests from user prompt turns, retaining needed context. Do not classify assistant refusals as user requests. Verify source coverage so assistant-authored generation prompts are not silently missed; document any extraction limitation before rollout.
3. Define custom Laya questions for XX and XXX using descriptive criteria and the contextual exclusions above. Do not rely on the built-in moderation preset, which does not encode these labels.
4. Use independent yes/no decisions for label membership. Validate the selected release's returned fields before implementing parsing.
5. Aggregate per-turn results: any confidently positive turn may mark the document. Mark negative only when all relevant text has been evaluated sufficiently; otherwise retain a review-needed state.
6. Split long inputs at meaningful boundaries with context overlap. Respect the selected checkpoint's effective token limit, including question overhead. Never interpret silently truncated or omitted text as a negative classification.
7. Fit decision thresholds on held-out labeled examples. Do not hardcode an assumed universal confidence cutoff.

Begin with zero-shot questions. Fine-tune only if measured precision/recall remains insufficient after refining definitions and examples. Existing flags are candidate training labels, not verified ground truth.

## 5. Persistence, caching, and manual overrides

Use a small SQLite metadata store through Python's standard library, outside the watched `source/` folder and on persistent application storage. Meilisearch remains the search projection; it must not be the sole owner of manual decisions or inference history. Use transactions and short-lived connections for concurrent watcher/API access.

Store per document: input hash, model/checkpoint revision, question version, automatic XX/XXX suggestions and scores, analysis status, last successful analysis time, and nullable manual overrides for each label. Record override changes and operational errors without logging full prompt text by default.

- Effective value per flag: explicit manual override if present; otherwise the last successful automatic result; otherwise the preserved legacy value or false for a new document.
- Manual `true` and manual `false` both override future automated results. Keep the existing PATCH payloads and responses; update durable metadata as part of each manual action.
- Migration: preserve existing true flags as manual positives. Legacy false flags cannot distinguish defaults from deliberate negatives; leave them unreviewed and show proposed changes during the first backfill rather than auto-overwriting them.
- Cache successful decisions by evaluated text hash, checkpoint revision, and question version. Unchanged inputs reuse results; explicit manual overrides survive changed text and remain visible as manual decisions.
- Failed or uncertain evaluations remain retryable. Keep the last successful result and flag it stale when text changes; never report a failed analysis as a successful negative.
- On deletion, remove the corresponding metadata. Stable document IDs are required; changed source IDs need explicit migration rather than guessed matches.

Fix the existing preservation loop in `ingest_file`: it calculates ID batches but repeatedly fetches the first 1,000 documents without filtering or pagination. Read the correct existing records before merging flags, favorites, and tags. A clean index rebuild must restore label decisions from durable metadata.

## 6. Runtime and failure handling

- Load one configured, pinned Laya checkpoint once per inference process and reuse it. Choose English versus multilingual based on actual prompt languages and evaluation results.
- Add Laya to backend dependencies only during implementation; verify Python/PyTorch compatibility and hardware memory requirements first. Do not install it as part of this documentation task.
- Start with bounded batches in the existing ingestion worker. Custom-prompt creation currently invokes ingestion from an async route; move blocking ingestion/inference off the event loop while retaining its response contract.
- Serialize or bound concurrent model access from startup ingestion, manual re-ingestion, custom creation, Threads extraction, and watcher callbacks. Avoid holding metadata transactions during inference.
- Keep ingestion usable when Laya is unavailable: index prompt content, preserve effective labels, record an error/pending status, and retry classification later.
- Persist manual decisions before publishing their search projection. Treat Meilisearch updates as asynchronous tasks; verify completion before claiming a completed label update, and retain a retry path for failed projections.
- Configure enablement, checkpoint revision, question version, and persistent metadata path. Keep automatic application disabled until the pilot passes; avoid adding a separate queue service initially.

## 7. UI and API compatibility

Keep the existing XX/XXX endpoints and search parameters. Expose additive analysis metadata in conversation details: automatic suggestions, manual overrides, status, and stale/error indicators. Show concise reasons derived from configured criteria; do not invent model-generated explanations.

Use the existing controls for overrides and add a clear action to resume automatic classification when an override exists. That action needs explicit semantics for clearing the override, separate from setting a flag false. Provide visible save errors and keyboard-accessible status feedback.

If frontend API/global state is added, use RTK Query and typed hooks as required by project instructions. Redux Toolkit is absent from the current frontend package list, so account for dependency approval and store setup; avoid a whole-application state rewrite for this feature.

## 8. Incremental delivery

1. Review a small labeled set to resolve XX/XXX overlap and establish negation rules.
2. Fix preservation beyond 1,000 documents; add durable overrides and migrate legacy positives without changing labels.
3. Implement the isolated Laya module and run a dry backfill that stores suggestions without applying flags.
4. Review false positives/negatives, choose thresholds, then enable automatic application during re-ingestion for eligible unreviewed/new/changed prompts.
5. Add UI analysis feedback and override reset; verify existing filters and manual controls.
6. Fine-tune only if the evaluated zero-shot implementation falls short.

## 9. Acceptance checks

- Fixtures cover every supplied example, mixed XX/XXX requests, negation, unrelated curves, long inputs, and supported languages.
- Precision and recall are measured separately for XX and XXX on held-out examples; acceptable targets are agreed before automatic application.
- New prompts are classified; unchanged prompts reuse cached results; changed prompts are re-evaluated without losing manual overrides.
- Manual true/false overrides and labels survive restart, re-ingestion, more than 1,000 indexed documents, and a clean index rebuild.
- Model failures, malformed output, low confidence, and incomplete text coverage do not clear labels or become successful negatives.
- Concurrent ingestion/manual updates do not lose overrides; failed Meilisearch tasks remain visible and retryable.
- Regression checks cover custom creation, Threads extraction, watcher ingestion, favorites/tags, search filters, tree navigation, and statistics.
- Any UI changes receive responsive, keyboard, contrast, icon-spacing, and loading/error-state checks before delivery.
- Run GitNexus `detect_changes` before implementation commits; refresh architectural graphs if significant components are added or moved.

## 10. References and limitations

- Laya project: https://github.com/NandhaKishorM/laya
- Preset definitions: https://github.com/NandhaKishorM/laya/blob/main/laya/presets.py
- Confidence guidance: https://github.com/NandhaKishorM/laya#automated-confidence-gating

Implementation uses the existing ingestion worker, a pinned multilingual checkpoint, Laya's built-in overlapping token windows over concatenated user turns, and a SQLite label store. Assistant-authored prompt text is excluded initially to avoid classifying refusals; review source coverage before expanding extraction.

Laya has been installed and exercised on synthetic examples and a temporary local Meilisearch index. These checks establish integration behavior, not accuracy on the user's collection. Definitions, deployment thresholds, and domain accuracy still need validation. The current application uses a single API process; cross-process projection coordination is required before deploying multiple workers.
