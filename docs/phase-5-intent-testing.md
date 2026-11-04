# Phase 5 — prototype intent training and hybrid runtime

The optional trained path is implemented and testable. Default localhost service remains in `baseline` rule mode because the small synthetic prototype performs worse than the keyword intent baseline on this smoke holdout. This is an engineering checkpoint, not completion of the final NLP study or evidence of student-query quality.

## Reproduce training

With the Phase 5 interpreter setup complete:

```sh
make train-intent
make test contract-check
```

PowerShell without Make:

```powershell
docker compose run --rm api python /workspace/scripts/train_intent.py
docker compose run --rm api pytest -q
docker compose run --rm api python /workspace/scripts/contracts.py
```

Training writes `.local/models/intent.json` and its `.sha256` sidecar. Both stay ignored locally; no model artifact is pushed. Reports and the split manifest are under `reports/phase-5/intent-evaluation.json` and `intent-split.json`. Re-running with the same corpus, runtime and settings reproduces the same artifact. A different corpus requires a new `--reports` directory; the trainer refuses to overwrite a split frozen for a different corpus. Checksums normalize CRLF to LF so a Windows checkout preserves dataset identity.

The command-line script also accepts `--dataset`, `--output` and `--reports`. Training is explicit and offline; application startup and HTTP requests never train a model.

## Run hybrid mode at localhost:8000

On macOS/Linux:

```sh
NLP_MODE=hybrid docker compose up -d --wait api
make acceptance-intent
```

On Windows PowerShell:

```powershell
$env:NLP_MODE = "hybrid"
docker compose up -d --wait api
docker compose exec -T api python /workspace/scripts/acceptance_intent.py
```

Refresh [localhost:8000](http://localhost:8000/), select Readiness, and check `nlp_mode: "hybrid"` plus `checks.nlp: "ok"`. Sign in as a demo student. In Section 6, try **Interpret only** with `Any free events on Friday?`. Its diagnostic response includes `intent_source: "model"`, `model_version`, a confidence value and a validated event query. This is a declared training smoke example used to verify wiring; it is not held-out accuracy evidence. Other valid questions may be rejected by this prototype.

Hybrid classification only chooses an intent. Entity resolution, time normalization, explicit constraints and typed service validation still apply. Low confidence, unsupported predictions, contradictory domains or unknown constraints cannot execute a query. HTTP callers cannot choose the mode, upload a model, change the threshold or supply arbitrary execution objects. Confidence is an uncalibrated classifier probability, not a guarantee of correctness.

Restore default rule mode afterward:

```sh
NLP_MODE=baseline docker compose up -d --wait api
make acceptance PHASE=5
```

PowerShell:

```powershell
$env:NLP_MODE = "baseline"
docker compose up -d --wait api
docker compose exec -T api python /workspace/scripts/acceptance_phase5.py
Remove-Item Env:NLP_MODE
```

Native Windows execution has not been independently verified; these commands use the same Linux Docker runtime. Changing or retraining an artifact requires restarting/recreating the API process to load it. `INTENT_MODEL_PATH` can select another trusted local JSON artifact path.

## Missing/incompatible artifact behavior

A selected hybrid model must load successfully. Missing files, checksum mismatch, invalid numerical dimensions/values or an incompatible scikit-learn version leave liveness working, make readiness return 503 with `nlp: "unavailable"`, and make new interpretation requests return `model_unavailable` (503). There is no silent rule fallback. Already completed request snapshots can replay without running inference again. Restore a compatible artifact and restart, or explicitly select baseline mode.

Artifacts contain only bounded JSON vocabulary, IDF values, coefficients, intercepts and metadata. Runtime loading never deserializes pickle/joblib objects. The checksum detects corruption; trusted filesystem access remains the authority for model changes. Dependencies are locked, and export tests compare JSON runtime probabilities against the fitted sklearn pipeline.

## Actual prototype results

Dataset: 78 agent-authored synthetic questions. Connected paraphrase families, whole conversation groups and normalized exact duplicates stay together; conflicting duplicate labels and insufficient independent class groups are rejected. The original heterogeneous unsupported family remains intact.

| Partition | Questions | Actual fraction |
| --- | ---: | ---: |
| Training | 30 | 38.46% |
| Validation | 24 | 30.77% |
| Holdout | 24 | 30.77% |

There are only three independent groups per supported class, so class coverage in all three partitions requires these proportions. The split is selected using only group membership, sizes and class coverage, never prediction scores. TF-IDF vocabulary and IDF fit on training only. Logistic-regression strength and the rejection threshold are selected using validation only; holdout predictions do not select the model.

On this fixed synthetic holdout, the trained classifier has **54.17% accuracy**, **0.4971 macro F1**. The keyword intent baseline has **100% accuracy** on the same small holdout. These are intent-only measurements; they do not score entity/time extraction or end-to-end answers and do not generalize to real student questions. The model version is `tfidf-4d99512a8b52`, selected C=1.0, confidence threshold=0.35. Per-class scores and confusion counts are in the report. No attempt was made to tune against the observed holdout errors.

A larger independently reviewed corpus, realistic unsupported cases, semantic gold labels, whole dialogues and a separately frozen final evaluation are still needed. Continue next with authoritative dialogue, clarification replies, history/deletion and saves; corpus collection can proceed separately without blocking that backend work.

Implementation references: [sklearn leakage guidance](https://scikit-learn.org/stable/common_pitfalls) and [model persistence guidance](https://scikit-learn.org/stable/model_persistence).
