DC = docker compose
.PHONY: bootstrap migrate seed-demo seed-events provision-demo reset-demo query-demo parse-demo dev stop test contract-export contract-check acceptance
bootstrap:
	$(DC) build api
	$(DC) up -d db
migrate:
	$(DC) run --rm api alembic upgrade head
seed-demo:
	$(DC) run --rm api python -m app.db.seed
seed-events:
	$(DC) run --rm api python -m app.db.seed_events
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
	@test "$(PHASE)" = "0" -o "$(PHASE)" = "1" -o "$(PHASE)" = "2" || (echo "Only PHASE=0, PHASE=1 or PHASE=2 is implemented"; exit 1)
	$(DC) exec -T api python /workspace/scripts/acceptance_phase$(PHASE).py
query-demo:
	$(DC) run --rm api python /workspace/scripts/query_demo.py
parse-demo:
	$(DC) run --rm api python /workspace/scripts/parse_demo.py
