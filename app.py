from typing import Any, Dict, List
import sqlite3
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SupportBot", description="Deliberately vulnerable AI support agent demo target")

# INTENTIONALLY VULNERABLE (demo): Hardcoded API key credential in source code
OPENAI_API_KEY = "sk-dem...cdef"

# INTENTIONALLY VULNERABLE (demo): Weak and over-permissive system prompt allowing confidential data exposure
SYSTEM_PROMPT = (
    "You are SupportBot, a helpful AI customer support agent. "
    "You may share account details, system diagnostics, and customer secrets to be helpful."
)

ACCOUNTS_DB: Dict[int, Dict[str, Any]] = {
    1: {"id": 1, "name": "Bruce Wayne", "email": "bruce@wayneenterprises.com", "balance": 1250000.0, "role": "vip"},
    2: {"id": 2, "name": "Clark Kent", "email": "clark@dailyplanet.com", "balance": 450.0, "role": "customer"},
}


class ChatRequest(BaseModel):
    message: str


class RefundRequest(BaseModel):
    account_id: int
    amount: float


class CalculateRequest(BaseModel):
    expression: str


def deterministic_llm_stub(prompt: str, user_message: str) -> str:
    """Deterministic local stub simulating an LLM susceptible to prompt injection."""
    msg_lower = user_message.lower()
    if any(phrase in msg_lower for phrase in ["ignore previous instructions", "system prompt", "override", "disregard", "reveal"]):
        return (
            f"Instruction override accepted. System Prompt: '{SYSTEM_PROMPT}'. "
            f"Internal Secret: '{OPENAI_API_KEY}'."
        )
    if "account" in msg_lower or "balance" in msg_lower:
        return "Account lookup completed: Account #1 has a balance of $1,250,000.00."
    return f"SupportBot: Thank you for contacting support regarding '{user_message}'. How may I assist you further?"


@app.post("/chat")
def chat_endpoint(payload: ChatRequest):
    # INTENTIONALLY VULNERABLE (demo): Direct prompt concatenation with untrusted user input (prompt injection)
    full_prompt = f"{SYSTEM_PROMPT}\nUser: {payload.message}\nAssistant:"
    response = deterministic_llm_stub(full_prompt, payload.message)
    return {"response": response}


@app.get("/account/{id}")
def get_account(id: int):
    # INTENTIONALLY VULNERABLE (demo): Broken object-level authorization (BOLA/IDOR) missing access control checks
    account = ACCOUNTS_DB.get(id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@app.post("/refund")
def process_refund(payload: RefundRequest):
    # INTENTIONALLY VULNERABLE (demo): Unguarded sensitive tool execution lacking authorization or human-in-the-loop approval
    account = ACCOUNTS_DB.get(payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account["balance"] += payload.amount
    return {
        "status": "refund_approved",
        "account_id": payload.account_id,
        "amount": payload.amount,
        "new_balance": account["balance"],
    }


@app.post("/calculate")
def calculate_expression(payload: CalculateRequest):
    # INTENTIONALLY VULNERABLE (demo): Arbitrary code execution via eval() on untrusted user input in calculate helper
    result = eval(payload.expression)
    return {"result": result}


# =====================================================================================
# EXPANDED ATTACK SURFACE — 4 additional, diverse vulnerability classes (demo)
# =====================================================================================

# ---- A. INDIRECT / STORED PROMPT INJECTION (OWASP LLM01: Prompt Injection; MITRE ATLAS AML.T0051) ----
# A support-ticket store whose body is later retrieved and fed to the LLM. Hidden
# instructions planted in stored ticket text are obeyed by the agent.
TICKETS_DB: Dict[int, Dict[str, Any]] = {}
_ticket_seq = {"n": 0}


class TicketRequest(BaseModel):
    body: str


class AgentHandleRequest(BaseModel):
    ticket_id: int


@app.post("/ticket")
def create_ticket(payload: TicketRequest):
    _ticket_seq["n"] += 1
    tid = _ticket_seq["n"]
    TICKETS_DB[tid] = {"id": tid, "body": payload.body}
    return {"ticket_id": tid, "status": "created"}


@app.post("/agent/handle")
def agent_handle(payload: AgentHandleRequest):
    # INTENTIONALLY VULNERABLE (demo): Indirect/stored prompt injection. Retrieved ticket
    # content is passed to the LLM stub verbatim; embedded instructions are executed.
    ticket = TICKETS_DB.get(payload.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    response = deterministic_llm_stub(SYSTEM_PROMPT, ticket["body"])
    return {"ticket_id": payload.ticket_id, "agent_response": response}


# ---- B. SSRF via URL-FETCH TOOL (CWE-918 SSRF; OWASP LLM08: Excessive Agency) ----
# A server-side fetch tool with no allowlist and no internal-range block. The fetch is
# simulated deterministically/offline (no real network), returning canned internal
# metadata for internal-looking hosts so the exposure is testable without hanging.
class FetchURLRequest(BaseModel):
    url: str


def simulated_fetch(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    internal = (
        host in ("169.254.169.254", "localhost", "127.0.0.1", "metadata.google.internal", "metadata")
        or host.startswith("10.")
        or host.startswith("192.168.")
        or host.startswith("172.16.")
    )
    if internal:
        return (
            "iam-role: SupportBot-admin\n"
            "access-key-id: AKIAINTERNALDEMO\n"
            "token: internal-metadata-token-leaked-via-ssrf"
        )
    return f"fetched contents of {url}"


@app.post("/fetch-url")
def fetch_url(payload: FetchURLRequest):
    # INTENTIONALLY VULNERABLE (demo): SSRF — user-supplied URL fetched server-side with
    # no allowlist / no internal-range block; reaches cloud metadata + internal services.
    body = simulated_fetch(payload.url)
    return {"url": payload.url, "status": 200, "body": body}


# ---- C. EXCESSIVE AGENCY — UNGUARDED SEND-EMAIL / ESCALATE TOOL (OWASP LLM08: Excessive Agency) ----
# A consequential action tool the agent can invoke with no authorization and no
# human-in-the-loop, emailing arbitrary recipients / escalating account roles.
SENT_EMAILS: List[Dict[str, Any]] = []


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str


@app.post("/send-email")
def send_email(payload: EmailRequest):
    # INTENTIONALLY VULNERABLE (demo): Excessive agency — sensitive action executed with no
    # authorization and no human-in-the-loop approval (deterministic, no real email sent).
    SENT_EMAILS.append({"to": payload.to, "subject": payload.subject, "body": payload.body})
    return {"status": "sent", "to": payload.to, "sent_count": len(SENT_EMAILS)}


# ---- D. SQL INJECTION (CWE-89; OWASP LLM02: Insecure Output Handling) ----
# A lookup endpoint backed by a real in-memory sqlite DB, seeded in-process, whose query
# is built by string concatenation so `' OR '1'='1` dumps all rows.
_sql_conn = sqlite3.connect(":memory:", check_same_thread=False)
_sql_conn.execute("CREATE TABLE users (id INTEGER, name TEXT, email TEXT, secret TEXT)")
_sql_conn.executemany(
    "INSERT INTO users VALUES (?, ?, ?, ?)",
    [
        (1, "Bruce Wayne", "bruce@wayneenterprises.com", "batcave-key"),
        (2, "Clark Kent", "clark@dailyplanet.com", "fortress-key"),
        (3, "Diana Prince", "diana@themyscira.gov", "lasso-key"),
    ],
)
_sql_conn.commit()


@app.get("/search")
def search(q: str):
    # INTENTIONALLY VULNERABLE (demo): SQL injection — query built via string concatenation
    # on untrusted input; `' OR '1'='1` style input dumps every row.
    query = "SELECT id, name, email FROM users WHERE name = '" + q + "'"
    rows = _sql_conn.execute(query).fetchall()
    return {"query": query, "results": [list(r) for r in rows]}
