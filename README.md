# Campus Companion

An NLP-first campus information assistant. The frontend is implemented in `frontend/`; the backend/NLP workstream remains Person B's responsibility.

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Select **Use student demo** or **Use admin demo**, then **Sign in**. Both demo accounts use `CampusDemo!26`. Demo records and histories are fictional, stored in this browser, and use a fixed campus clock of **4 November 2026, 10:00 AM Asia/Kolkata**.

The application defaults to explicit mock mode. It has student login/profile, assistant cards and clarification, follow-ups, private demo conversations with deletion, saved records, and forms for all nine admin resources. Production identity, authorization, persistence, eligibility, availability, and NLP must come from Person B's backend.

- [Frontend setup and verification](frontend/README.md)
- [Backend integration handoff](docs/frontend-handoff.md)
- [Frontend design decisions](docs/frontend-design.md)
- [Demo walkthrough](docs/frontend-demo.md)
- [Evaluation contribution and limitations](reports/frontend-evaluation.md)
- [Shared build plan](docs/build-plan.md)

The generated [OpenAPI proposal](contracts/openapi.json) and [fixtures](contracts/fixtures/) make the frontend's assumptions reviewable before live integration. They need Person B's review; this repository has no backend implementation yet.
