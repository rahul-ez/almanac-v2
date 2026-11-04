# Intent-model engineering checkpoint verification

Verified locally on 4 November 2026. Changes remain local and uncommitted; nothing pushed.

- Full regression suite: **89 passed**, one upstream Starlette/httpx deprecation warning.
- Model-specific tests: **9 passed**, including LF/CRLF reproducibility, grouped duplicate/conversation separation, conflicting-label rejection, train-only vocabulary, JSON/sklearn numerical parity, corrupt/incompatible artifacts, valid startup, missing-model readiness, typed semantic rejection and exact historical replay without new inference.
- Contract check: **67 fixtures** validated; API 0.6.0 adds optional model diagnostics and hybrid readiness.
- Offline prototype trained successfully: model `tfidf-4d99512a8b52`, dataset split 30 train / 24 validation / 24 holdout. Reproducible split and metrics reports saved beside this file.
- Live hybrid mode on localhost:8000: readiness reported hybrid/ok, declared training example produced a model-selected and semantically validated free-event query, persisted snapshot replayed exactly, unsupported question had no executable query. Logged out afterward.
- Restored default baseline mode and passed the complete Phase 5 live room/faculty/event interpretation acceptance again.
- `git diff --check` passed. CI workflow was extended but was not run remotely.

Prototype held-out intent accuracy 54.17%, macro F1 0.4971; keyword intent baseline 100% on the same small synthetic holdout. The trained model remains optional because it does not outperform this baseline. These are not real-student accuracy or end-to-end semantic evaluation claims. Holdout errors were not used to retune the model. Real corpus review/final evaluation and Phase 6 dialogue/history/saves remain outstanding.

Model inference follows an explicit trusted local JSON artifact and locked runtime; no pickle/joblib loading, HTTP training, artifact upload endpoint or silent fallback is implemented. Startup loads once; retraining requires a restart to select the new artifact.
