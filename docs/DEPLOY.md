# Deploying Pardarshi

Two pieces:

| Piece | Where | Why |
|---|---|---|
| `frontend/` (Next.js) | **Vercel** (free) | Static pages on a global CDN; `/api/*` is proxied to the backend so there's no CORS setup |
| `backend/` (FastAPI) | **Azure Container Apps** (Azure for Students credit) | Always-on container, scales to zero, built in the cloud from the Dockerfile |

Do the backend first, because the frontend needs its URL.

---

## 1. Backend on Azure Container Apps

You don't need Docker installed: Azure builds the image from `backend/Dockerfile`.

```bash
# one-time
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# deploy (from the repo root)
az containerapp up \
  --name pardarshi-api \
  --resource-group pardarshi-rg \
  --location centralindia \
  --source ./backend \
  --ingress external \
  --target-port 8000 \
  --env-vars ALLOWED_ORIGINS=https://YOUR-APP.vercel.app WEB_CONCURRENCY=1
```

The command prints the app URL, e.g. `https://pardarshi-api.<hash>.centralindia.azurecontainerapps.io`. Check it:

```bash
curl https://pardarshi-api.<hash>.centralindia.azurecontainerapps.io/api/health
```

**Keep it warm for judging:** scale-to-zero means a cold start of a few seconds. During judging week set one replica always on:

```bash
az containerapp update -n pardarshi-api -g pardarshi-rg --min-replicas 1 --max-replicas 1
```

**Add AI (optional).** Store keys as secrets, never as plain env vars:

```bash
az containerapp secret set -n pardarshi-api -g pardarshi-rg --secrets gemini-key=YOUR_KEY
az containerapp update -n pardarshi-api -g pardarshi-rg \
  --set-env-vars GEMINI_API_KEY=secretref:gemini-key GEMINI_MODEL=<current flash model>
```

The same pattern works for `GROQ_API_KEY`. On student credit, **don't** add `AZURE_OPENAI_*`: Azure OpenAI is billed per token against your credit, while Groq and Gemini free-tier keys cost nothing. Providers are tried in order and skipped automatically when they fail.

**Redeploy after code or data changes:** run the same `az containerapp up` command again.

### Alternative: Azure App Service (container)

If you already use App Service: create a Web App for Containers, point it at an image built with `az acr build --registry <acr> --image pardarshi-api:latest ./backend`, set `WEBSITES_PORT=8000`, and add the same environment variables.

---

## 2. Frontend on Vercel

1. Push the repository to GitHub (it must be public for Arthaton).
2. On vercel.com → **Add New Project** → import the repo.
3. **Root Directory:** `frontend`. Framework preset: Next.js (auto-detected).
4. **Environment variables:**
   - `BACKEND_URL` = your Azure URL, e.g. `https://pardarshi-api.<hash>.centralindia.azurecontainerapps.io`
   - `NEXT_PUBLIC_REPO_URL` = your GitHub repo URL (used for "Open source" and "Report a wrong flag")
5. Deploy. Every push to `main` redeploys.

Then put the Vercel URL back into the backend's `ALLOWED_ORIGINS` (only needed if you also set `NEXT_PUBLIC_API_URL` to call the API directly; with the default `/api` proxy it isn't required).

> Uploads go through the `/api` proxy. Vercel's proxied request bodies comfortably fit a CAS PDF (typically under 1 MB). If you ever hit a size limit, set `NEXT_PUBLIC_API_URL` to the Azure URL so the browser uploads directly to the backend.

### Alternative: frontend on Azure too

Azure Static Web Apps or App Service (Node 20+) can run the Next.js app: `npm ci && npm run build && npm run start`, with the same `BACKEND_URL` variable.

---

## 3. Checklist before submitting

- [ ] `https://<vercel-app>/` loads; **Try a sample portfolio** opens the report
- [ ] **See evidence** on Sample Co. opens the drawer; **p. 7 · Open page** shows the highlighted line
- [ ] Chat answers (AI if a key is set, verified findings otherwise)
- [ ] `https://<azure-api>/api/metrics` shows latency and cache stats
- [ ] Hindi toggle and larger-text toggle work on a phone
- [ ] If the API is stopped, the site shows the offline demo with a notice instead of breaking
- [ ] README credits all libraries and AI APIs used (Arthaton rule)

## Cost on student credit: how not to get overcharged

Everything that could cost money, and the setting that caps it:

| What costs money | Cap |
|---|---|
| **AI calls** | Use only free-tier keys: Groq (no card needed) and Gemini from a Google project **with billing turned off**. A key from a billing-enabled project is charged. Leave `AZURE_OPENAI_*` unset. |
| **Abuse of the AI** | Built in: `AI_DAILY_CALLS` (whole site, default 300/day) and `AI_DAILY_CALLS_PER_IP` (default 25/day). Past either cap, chat answers without AI from verified findings. Repeated questions replay a checked answer with no new call. Buy/sell questions never reach a model. |
| **Request floods** | Per-IP limits (`RATE_LIMIT_CHAT` 20/min, `RATE_LIMIT_CAS` 10/min, everything else 60/min). The IP is read from the ingress-added end of `X-Forwarded-For`, so a faked header can't dodge it. |
| **Scaling out** | `--max-replicas 1`. At most `MAX_CONCURRENT_CHATS` (6) chats and `MAX_CONCURRENT_PARSES` (2) statement parses run at once; extra requests get a polite "busy, retry in 5 s" instead of a second replica. |
| **Container size** | Smallest size: `--cpu 0.25 --memory 0.5Gi` (the API idles at about 80 MB). One worker (`WEB_CONCURRENCY=1`). The free grant is 180,000 vCPU-seconds a month, so 0.25 vCPU kept always-on for 8 days is still free; 0.5 vCPU halves that. |
| **Idle time** | `--min-replicas 0` (scale to zero) except on judging days. The Container Apps monthly free grant covers idle-to-light use. |
| **Logs** | `az containerapp up` creates a Log Analytics workspace, billed per GB. Turn it off (below). |

```bash
# size, replicas and logs
az containerapp update -n pardarshi-api -g pardarshi-rg --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 1
$envId = az containerapp show -n pardarshi-api -g pardarshi-rg --query properties.managedEnvironmentId -o tsv   # PowerShell
az containerapp env update --ids $envId --logs-destination none

# optional: tighter AI caps
az containerapp update -n pardarshi-api -g pardarshi-rg --set-env-vars AI_DAILY_CALLS=200 AI_DAILY_CALLS_PER_IP=15
```

**Budget alert (do this once).** Portal → *Cost Management* → *Budgets* → *Add*: scope = your subscription, amount ₹500 (or $5), alerts at 50 % and 90 % to your email. Azure for Students also stops services when the credit runs out instead of charging a card.

**Check usage any time:** `https://<azure-api>/api/metrics` → `budget` shows AI calls today, the daily cap and visitors today.

**After the hackathon:** `az group delete -n pardarshi-rg` removes everything, so nothing keeps billing.

Vercel Hobby (frontend) is free.
