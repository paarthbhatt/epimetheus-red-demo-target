from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SupportBot", description="Deliberately vulnerable AI support agent demo target")

# INTENTIONALLY VULNERABLE (demo): Hardcoded API key credential in source code
OPENAI_API_KEY = "sk-demo-1234567890abcdef1234567890abcdef"

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
