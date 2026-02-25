
# semanticiq Django MVP (downloadable)

**Studio + Application** MVP that uses **Ontology‑Lite** as metadata to drive forms, rules, and workflows.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # optional; defaults to SQLite
python manage.py migrate
python manage.py seed_mvp --tenant tenantA
python manage.py runserver 0.0.0.0:8000
```

### Studio (Registry) API
- `GET  /api/templates` → list templates
- `POST /api/tenants/{tenantId}/models` → create/clone draft model
- `GET  /api/tenants/{tenantId}/models/{modelId}` → fetch draft JSON
- `PUT  /api/tenants/{tenantId}/models/{modelId}/update` → update draft JSON
- `POST /api/tenants/{tenantId}/models/{modelId}/publish` → publish as active

### Runtime (Application) API
- `POST /api/{tenantId}/workflows/{name}/instances` → start
- `POST /api/{tenantId}/workflows/{name}/instances/{id}/signal` → transition/update
- `GET  /api/{tenantId}/workflows/{name}/instances/{id}/state` → state

> **Note:** The default seed model is `Procurement` MVP with `PurchaseOrder` workflow and a simple Director approval rule.

## Next Steps
- Add `jsonschema` validation before publish.
- Switch to Postgres using `DATABASE_URL` in `.env`.
- Integrate a real Interpreter Agent (NL → structured intent → workflow).
- Add RBAC checks in runtime transitions.
