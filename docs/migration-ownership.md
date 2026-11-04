# Migration ownership

Current local head: **0006_personal**, parent **0005_faculty**, then **0004_rooms**. One backend owner currently covers both original person work plans. These local migrations are not pushed.

Do not create an independent revision with an existing number or introduce a second Alembic head. The existing conversations/assistant_turns tables are extended in place. Migration 0006 preserves old snapshots, assigns ordered turn sequence values, adds expiring dialogue state, text-free deleted-request receipts and saved references. Current readiness expects 0006.

Room/faculty metadata is registered by `backend/migrations/env.py` importing `app.db.room_models` and `app.db.faculty_models`; personal models remain in `app.db.models`. Check metadata drift, empty-database upgrades, downgrade/re-upgrade and existing-data upgrades when changing the head. `scripts/check_migrations.py` uses a uniquely named disposable database.
