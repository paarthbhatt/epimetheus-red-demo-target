# SupportBot — Deliberately Vulnerable Demo Target

⚠️ **This application is intentionally insecure. Never deploy it. It exists only as a scan target for the Epimetheus Red platform.**

SupportBot is a tiny FastAPI "AI customer-support agent" that contains five planted vulnerabilities, one for each thing the platform's engines should catch:

| # | Vulnerability | Location | Engine that catches it |
|---|---------------|----------|------------------------|
| 1 | Hardcoded API-key credential | `app.py` (`OPENAI_API_KEY`) | Guardiant (secrets) |
| 2 | Over-permissive system prompt (leaks secrets) | `app.py` (`SYSTEM_PROMPT`) | Entropy |
| 3 | Prompt injection via direct concatenation | `POST /chat` | Entropy / Leviathan |
| 4 | Broken object-level authorization (BOLA/IDOR) | `GET /account/{id}` | Guardiant (auth) |
| 5 | Unguarded sensitive tool (refund, no approval) | `POST /refund` | Guardiant (business logic) |
| 6 | Arbitrary code execution via `eval()` | `POST /calculate` | Guardiant (injection) |

## Run (only for scanning / local demo)

```bash
pip install fastapi uvicorn
uvicorn app:app --host 127.0.0.1 --port 9100
```

Then point an Epimetheus Red campaign at this directory (`repo_path`) and endpoint.

## Note on the hardcoded secret

The `OPENAI_API_KEY` in `app.py` is a **fake placeholder** shaped like a real key so secret-scanners flag it. It is not a live credential.
