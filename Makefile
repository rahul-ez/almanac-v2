DC = docker compose
.PHONY: bootstrap migrate seed-demo seed-events seed-rooms seed-faculty provision-demo reset-demo query-demo room-query-demo faculty-query-demo parse-demo dev stop test contract-export contract-check acceptance
bootstrap:
	$(DC) build api
	$(DC) up -d db
migrate:
	$(DC) run --rm api alembic upgrade head
seed-demo:
	$(DC) run --rm api python -m app.db.seed
seed-events:
	$(DC) run --rm api python -m app.db.seed_events
seed-rooms:
	$(DC) run --rm api python -m app.db.seed_rooms
seed-faculty:
	$(DC) run --rm api python -m app.db.seed_faculty
provision-demo:
	$(DC) run --rm api python -m app.db.provision
reset-demo:
	@test "$(CONFIRM)" = "demo-only" || (echo "Use CONFIRM=demo-only to reset only the versioned synthetic rows"; exit 1)
	$(DC) run --rm api python -m app.db.seed --reset --confirm-demo-only
dev:
	$(DC) up -d --wait api
stop:
	$(DC) stop
test:
	$(DC) run --rm api pytest -q
contract-export:
	$(DC) run --rm api python /workspace/scripts/contracts.py --write
contract-check:
	$(DC) run --rm api python /workspace/scripts/contracts.py
acceptance:
	@test "$(PHASE)" = "0" -o "$(PHASE)" = "1" -o "$(PHASE)" = "2" -o "$(PHASE)" = "3" -o "$(PHASE)" = "4" -o "$(PHASE)" = "5" -o "$(PHASE)" = "6" || (echo "Only PHASE=0 through PHASE=6 are implemented"; exit 1)
	$(DC) exec -T api python /workspace/scripts/acceptance_phase$(PHASE).py
query-demo:
	$(DC) run --rm api python /workspace/scripts/query_demo.py
parse-demo:
	$(DC) run --rm api python /workspace/scripts/parse_demo.py

room-query-demo:
	$(DC) run --rm api python /workspace/scripts/query_rooms_demo.py

faculty-query-demo:
	$(DC) run --rm api python /workspace/scripts/query_faculty_demo.py

interpret-demo:
	$(DC) run --rm api python /workspace/scripts/interpret_demo.py

train-intent:
	$(DC) run --rm api python /workspace/scripts/train_intent.py

acceptance-intent:
	$(DC) exec -T api python /workspace/scripts/acceptance_intent.py

acceptance-all:
	$(DC) exec -T api python /workspace/scripts/acceptance_all.py

evaluate:
	$(DC) run --rm api python /workspace/scripts/evaluate_backend.py --check

verify-fresh:
	python3 scripts/verify_fresh.py

local: bootstrap migrate seed-demo provision-demo seed-events seed-rooms seed-faculty dev

integration-test:
	cd frontend && ALMANAC_LIVE_TEST=1 npx vitest run tests/unit/live-http.test.ts
	cd frontend && ALMANAC_LIVE_TEST=1 ALMANAC_APP_ORIGIN=http://127.0.0.1:8000 npx playwright test
