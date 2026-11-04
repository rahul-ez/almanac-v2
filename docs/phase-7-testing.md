# Phase 7 — reproducible evaluation and packaged-backend rehearsal

The engineering evaluation and fresh-install verification are runnable. This completes the local backend implementation checkpoints; real student-data evaluation, product frontend integration and an actual deployment remain separate work. Default service stays at localhost:8000 in baseline rule mode.

## Reproduce the evaluation

```sh
make train-intent
make evaluate
```

Or on Windows PowerShell without Make:

```powershell
docker compose run --rm api python /workspace/scripts/train_intent.py
docker compose run --rm api python /workspace/scripts/evaluate_backend.py --check
```

The evaluator creates a uniquely named `almanac_eval_…` PostgreSQL database, applies migrations, loads frozen synthetic records, uses the fixed clock **2026-11-04 10:00 Asia/Kolkata**, then drops only that evaluation database in cleanup. It requires the local Docker PostgreSQL role's database-creation permission. It never seeds or scores your edited demo database. No model fitting/tuning happens in evaluation; the explicit training command remains separate.

Results are saved to `reports/phase-7/semantic-evaluation.json`. The report includes corpus/record/requirements/model/source checksums, runtime hardware information, per-case expected/actual meanings, spans, result IDs/intervals and error categories. Input checksum drift is an error; gold is not regenerated from predictions. Model and corpus limitations remain visible.

## What is measured

| Measurement | Explicit denominator |
| --- | --- |
| Intent precision/recall/F1 and confusion | Questions with a supported-domain or unsupported intent gold label; the intent-ambiguous `free` case is excluded |
| Entity exact span-and-type precision/recall/F1 | 16 completely annotated executable-meaning cases, containing 40 gold spans; uncertain-input cases are not scored as completely annotated entities |
| Filter normalization | 47 explicitly specified gold slots; full default/null behavior is additionally checked by exact meaning |
| Exact structured meaning | All 16 questions expected to produce an executable meaning; extra filters count as errors |
| Answer correctness | All 24 cases: response status, complete result IDs/kinds and exact intervals, plus the requested clarification field |
| Uncertain-input detection | Precision/recall of requesting clarification or rejecting unsupported input |
| Semantic dialogue transitions | Three cases with explicit prior meaning; full pending-ID/session/concurrency/privacy behavior is covered by regression tests and real HTTP acceptance |
| Warm latency | 72 interpreter-plus-retrieval measurements per mode (24 cases × three warmed repeats); excludes HTTP/authentication and startup |

Both modes run the same production interpretation pipeline and typed PostgreSQL services. The model is never tuned from this suite's errors. It is a known, author-written synthetic regression suite, not independent held-out student evaluation. Its language families may resemble the prototype corpus and must not be used to claim real-query generalization.

Recorded local results after the span fix:

| Metric | Rule baseline | Prototype hybrid |
| --- | ---: | ---: |
| Correct answers | 24/24 | 8/24 |
| Exact meanings | 16/16 | 3/16 |
| Correct normalization slots | 47/47 | 11/47 |
| Exact span/type entity F1 | 1.000 | 0.261 |
| Intent macro F1 | 1.000 | 0.354 |
| Answers incorrectly returned for a gold non-answer | 0 | 0 |

Hybrid mainly rejects valid questions, explaining both its poor recall and lower median latency. Do not describe rejection-heavy timing as a speed improvement. The previous 54.17% prototype intent holdout score measures a different task/corpus; it is not interchangeable with this end-to-end score. See the JSON for actual measured timings and runtime details.

The engineering gate requires all rule-mode answers/meanings/gold spans to match and both modes to produce zero false answers on gold non-answer cases. This is a regression gate, not a frozen final-study accuracy target. The initial run found a time span swallowing adjacent masked capacity text; the code and focused test were corrected against unchanged gold. Such regression-driven development is explicitly distinct from evaluation on an untouched final test set.

## Verify a genuinely fresh packaged backend

From the host with Python 3 and Docker Desktop/Compose:

```sh
make verify-fresh
```

PowerShell:

```powershell
py -3 scripts/verify_fresh.py
```

This host script uses only Python's standard library and Docker. It builds a uniquely tagged image from this checkout, starts a uniquely named Compose project, creates empty PostgreSQL/local-secret volumes, and publishes **no host ports**. It has **no host source bind mount**. Existing localhost:8000, its containers, credentials and database are not used or stopped.

The rehearsal applies migrations, seeds/provisions twice, validates contracts, trains the synthetic prototype, evaluates frozen semantics/retrieval, runs pytest, and exercises HTTP Phases 0–6 plus hybrid mode. The same compiled image serves the requests; no development source mount can hide a packaging omission. The fresh API's start-to-ready duration is recorded separately from model-load and warm-query timings. Cleanup removes only the uniquely named verification containers/volumes and attempts to remove its unique image tag.

Evidence goes to `reports/phase-7/fresh-install.json`, including image identity, stage outcomes/times, test count, evaluation summaries and cleanup status. This is a demo/test packaging rehearsal, not a production deployment. Docker Desktop on native Windows has not been independently exercised here.

## Run all current-localhost HTTP phases

```sh
make acceptance-all
```

Or:

```powershell
docker compose exec -T api python /workspace/scripts/acceptance_all.py
```

The orchestrator waits for login/CSRF budgets between phases rather than disabling, increasing or clearing rate limits. Individual phases remain available through `make acceptance PHASE=N`. Live scripts use generated demo accounts, restore profiles and clean only records they create. They must not be aimed at a real-data production deployment.

CI now runs the shared phase orchestrator, training, semantic gate, regressions and hybrid smoke checks. That workflow has been prepared locally; no remote workflow run is claimed. The complete packaged-image rehearsal is a separate explicit command.

## Remaining release work

Read `backend-release-handoff.md` for architecture, supported configuration, backup/restore and the integration gate. Real student-data collection/review and a separately frozen final evaluation still need human participation. Actual frontend requests/rendering and hosting/TLS configuration must be verified on their chosen target before calling the complete application released.
