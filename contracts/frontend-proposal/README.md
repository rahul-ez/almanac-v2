# Existing frontend mock proposal

These are the original frontend mock schemas and 15 fixtures preserved during the backend merge. They describe mock mode and are not the implemented API contract. `npm run contracts:export` and `npm run contracts:check` in frontend operate here, preventing them from overwriting backend schemas/fixtures.

The current implemented API is `../openapi.json`; its schemas/fixtures are verified by `make contract-check`. Frontend live transport, payload/schema differences and joint workflows still need integration and testing. No mock/live equivalence is claimed by this merge.
