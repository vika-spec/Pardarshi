# Pardarshi frontend

Next.js 16 (App Router, TypeScript), "bahi-khata" ledger design.

```bash
npm install
npm run dev        # http://localhost:3000 ; /api/* is proxied to BACKEND_URL (default http://127.0.0.1:8000)
npm run build && npm run start
```

Environment variables (see `.env.example`):

- `BACKEND_URL`: where the FastAPI backend runs (used by the `/api` rewrite)
- `NEXT_PUBLIC_API_URL`: optional; call the backend directly from the browser instead of via the rewrite
- `NEXT_PUBLIC_REPO_URL`: your GitHub repo (footer links)

`public/demo/` is an offline copy of the sample report (from `backend/pipelines/export_demo.py`). If the API is unreachable, the site falls back to it and shows a notice.
