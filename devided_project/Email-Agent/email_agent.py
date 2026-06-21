"""Email Agent — library module.

Holds the OpenAI tool definitions, Python tool implementations, Gmail
integration (read/draft/mark-read), and the agent loop that drives them.

The send function `send_approved_email` is deliberately NOT exposed to the
LLM — only a human-controlled caller (CLI/UI) invokes it, so the agent
cannot autonomously send mail.
"""

import os
import json
import base64
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText

from openai import OpenAI

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from email_finder import find_email


# ── Configuration ────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

THIS_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = THIS_DIR / "credentials.json"
TOKEN_PATH = THIS_DIR / "token.json"

MODEL = "gpt-4o"


# ── OpenAI client (lazy) ─────────────────────────────────────────────

_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY env var is not set. "
                "Run:  export OPENAI_API_KEY=\"sk-...\""
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ── Gmail authentication (lazy) ──────────────────────────────────────

_gmail_service = None


def get_gmail_service():
    """Authenticated Gmail API client. First call opens a browser for
    OAuth consent and writes token.json; subsequent calls reuse it."""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing OAuth client file at {CREDENTIALS_PATH}.\n"
                    "Get it from Google Cloud Console → APIs & Services → "
                    "Credentials → OAuth client ID → Desktop app, then save "
                    "it here as credentials.json."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def _extract_body(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return _decode(part["body"]["data"])
        for part in payload["parts"]:
            nested = _extract_body(part)
            if nested:
                return nested
    if payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])
    return ""


# ── Pure-Python tools (no external calls) ────────────────────────────

def tool_read_email(raw_email: str) -> dict:
    lines = raw_email.strip().splitlines()
    sender, subject, body_lines = "", "", []
    body_start = False

    for line in lines:
        if line.upper().startswith("FROM:"):
            sender = line[5:].strip()
        elif line.upper().startswith("SUBJECT:"):
            subject = line[8:].strip()
        elif line.strip() == "" and not body_start and (sender or subject):
            body_start = True
        elif body_start:
            body_lines.append(line)

    if not sender and not subject:
        body_lines = lines

    return {
        "sender": sender or "unknown@unknown.com",
        "subject": subject or "(no subject)",
        "body": "\n".join(body_lines).strip() or raw_email.strip(),
        "word_count": len(raw_email.split()),
        "parsed_at": datetime.now().isoformat(),
    }


def tool_classify_email(sender: str, subject: str, body: str) -> dict:
    text = f"{subject} {body}".lower()

    proposal_signals = [
        "proposal", "quote", "pricing", "budget", "cost", "send us",
        "we need", "please provide", "ready to start", "next week",
        "asap", "urgent", "deadline", "scope of work", "deliverables",
    ]
    opp_signals = [
        "interested", "exploring", "tell me more", "call", "meeting",
        "learn more", "information", "brochure", "how do you", "what is",
        "considering", "evaluation", "looking into", "reach out",
    ]

    p_score = sum(1 for s in proposal_signals if s in text)
    o_score = sum(1 for s in opp_signals if s in text)

    classification = "proposal" if p_score > o_score else "opportunity_qualification"

    total = p_score + o_score
    if total == 0:
        confidence = "low"
    elif abs(p_score - o_score) >= 2:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "classification": classification,
        "confidence": confidence,
        "proposal_score": p_score,
        "opportunity_score": o_score,
    }


def tool_extract_signals(body: str) -> dict:
    text = body.lower()
    signals = []

    if any(w in text for w in ["budget", "sar", "usd", "000", "spend"]):
        signals.append("Budget mentioned")
    if any(w in text for w in ["week", "asap", "urgent", "deadline", "launch"]):
        signals.append("Timeline pressure")
    if any(w in text for w in ["ceo", "director", "head of", "manager", "founder"]):
        signals.append("Decision maker involved")
    if any(w in text for w in ["proposal", "quote", "pricing", "cost"]):
        signals.append("Explicit proposal request")
    if any(w in text for w in ["call", "meeting", "schedule", "demo"]):
        signals.append("Meeting request")
    if any(w in text for w in ["competitor", "currently using", "switching"]):
        signals.append("Competitor displacement")
    if any(w in text for w in ["campaign", "launch", "marketing", "ads"]):
        signals.append("Campaign-related inquiry")
    if any(w in text for w in ["interested", "exploring", "evaluation"]):
        signals.append("Early-stage exploration")

    priority = "high" if len(signals) >= 3 else "medium" if len(signals) >= 2 else "low"

    return {
        "signals": signals if signals else ["General inquiry"],
        "priority": priority,
        "signal_count": len(signals),
    }


def tool_route_to_agent(classification: str, priority: str, signals: list) -> dict:
    if classification == "proposal":
        agent = "Proposal Agent"
        action = "Generate a detailed proposal with scope, timeline, and pricing"
    else:
        agent = "Opportunity Qualification Agent"
        action = "Qualify the lead: assess budget, authority, need, and timeline (BANT)"

    return {
        "routed_to": agent,
        "action": action,
        "priority": priority,
        "signals_passed": signals,
        "routed_at": datetime.now().isoformat(),
        "status": "success",
    }


# ── Gmail-backed tools ───────────────────────────────────────────────

def tool_fetch_unread_emails(max_results: int = 5) -> dict:
    service = get_gmail_service()
    listing = service.users().messages().list(
        userId="me", q="is:unread", maxResults=max_results
    ).execute()

    refs = listing.get("messages", [])
    emails = []
    for ref in refs:
        msg = service.users().messages().get(
            userId="me", id=ref["id"], format="full"
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        body = _extract_body(msg["payload"])
        emails.append({
            "id": ref["id"],
            "thread_id": msg.get("threadId"),
            "from": headers.get("from", ""),
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", "")[:200],
            "body": body[:4000],
        })

    return {"count": len(emails), "emails": emails}


def tool_create_draft(to: str, subject: str, body: str) -> dict:
    """Save a Gmail draft. The agent uses this for any reply it composes;
    a human reviews and sends from Gmail (or via send_approved_email)."""
    service = get_gmail_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()

    return {
        "status": "draft_created",
        "draft_id": draft.get("id"),
        "to": to,
        "subject": subject,
        "created_at": datetime.now().isoformat(),
    }


def tool_mark_as_read(email_id: str) -> dict:
    service = get_gmail_service()
    service.users().messages().modify(
        userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
    return {"status": "marked_read", "email_id": email_id}


def tool_find_contact_email(company_name: str, website: str = "", city: str = "") -> dict:
    """Find a contact email for a company by scraping its website."""
    return find_email(company_name, website=website or None, city=city or None)


# ── Auth status / sign-in / sign-out (called from UI, not LLM) ───────

def is_signed_in() -> bool:
    """True if a usable cached token exists. Never triggers consent flow."""
    if not TOKEN_PATH.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception:
        return False
    if not creds:
        return False
    if creds.valid:
        return True
    return bool(creds.expired and creds.refresh_token)


def get_authenticated_email() -> str | None:
    """If signed in, return the Gmail address. Otherwise None.
    May refresh the token silently but never opens a browser."""
    if not is_signed_in():
        return None
    try:
        service = get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None


def sign_in_gmail() -> dict:
    """Run the OAuth consent flow (opens a browser). Returns
    {status, email, messages_total}. Raises FileNotFoundError if
    credentials.json is missing."""
    global _gmail_service
    _gmail_service = None
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    return {
        "status": "connected",
        "email": profile.get("emailAddress"),
        "messages_total": profile.get("messagesTotal"),
    }


def sign_out_gmail() -> dict:
    """Disconnect by deleting the cached token. Next Gmail call re-auths."""
    global _gmail_service
    _gmail_service = None
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    return {"status": "disconnected"}


# ── Human-in-the-loop send (NOT an LLM tool) ─────────────────────────

def send_approved_email(to: str, subject: str, body: str,
                        thread_id: str | None = None) -> dict:
    """Actually send an email. Only the CLI/UI calls this — after the
    human has approved (and optionally edited) the draft."""
    service = get_gmail_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    sent = service.users().messages().send(userId="me", body=payload).execute()

    return {
        "status": "sent",
        "message_id": sent.get("id"),
        "thread_id": sent.get("threadId"),
        "to": to,
        "subject": subject,
        "sent_at": datetime.now().isoformat(),
    }


# ── OpenAI tool schema ───────────────────────────────────────────────

TOOLS = [
    {"type": "function", "function": {
        "name": "read_email",
        "description": "Parse FROM/SUBJECT/BODY out of a raw email string. "
                       "Only needed for raw email text — not for results from fetch_unread_emails.",
        "parameters": {
            "type": "object",
            "properties": {"raw_email": {"type": "string"}},
            "required": ["raw_email"],
        },
    }},
    {"type": "function", "function": {
        "name": "classify_email",
        "description": "Classify an email as 'opportunity_qualification' or 'proposal'.",
        "parameters": {
            "type": "object",
            "properties": {
                "sender": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["sender", "subject", "body"],
        },
    }},
    {"type": "function", "function": {
        "name": "extract_signals",
        "description": "Extract sales signals (budget, urgency, decision-maker, etc.) from the body.",
        "parameters": {
            "type": "object",
            "properties": {"body": {"type": "string"}},
            "required": ["body"],
        },
    }},
    {"type": "function", "function": {
        "name": "route_to_agent",
        "description": "Route a classified email to the next pipeline agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "classification": {"type": "string",
                                   "enum": ["opportunity_qualification", "proposal"]},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "signals": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["classification", "priority", "signals"],
        },
    }},
    {"type": "function", "function": {
        "name": "fetch_unread_emails",
        "description": "Fetch unread Gmail messages. Call once at the start of an inbox-triage run.",
        "parameters": {
            "type": "object",
            "properties": {"max_results": {"type": "integer",
                                           "description": "Max emails (default 5)"}},
        },
    }},
    {"type": "function", "function": {
        "name": "create_draft",
        "description": "Save a Gmail draft of a reply. Use this for ANY reply you compose — "
                       "a human will review and send. Never attempt to send directly.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    }},
    {"type": "function", "function": {
        "name": "mark_as_read",
        "description": "Mark a processed email as read.",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "find_contact_email",
        "description": "Find a contact email for a company by scraping its website "
                       "(common contact pages) and falling back to info@<domain>. "
                       "Use this when a recipient address is missing.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "website": {"type": "string", "description": "Company website (with or without https://)"},
                "city": {"type": "string"},
            },
            "required": ["company_name"],
        },
    }},
]


TOOL_FUNCS = {
    "read_email": tool_read_email,
    "classify_email": tool_classify_email,
    "extract_signals": tool_extract_signals,
    "route_to_agent": tool_route_to_agent,
    "fetch_unread_emails": tool_fetch_unread_emails,
    "create_draft": tool_create_draft,
    "mark_as_read": tool_mark_as_read,
    "find_contact_email": tool_find_contact_email,
}


def run_tool(name: str, inp: dict) -> str:
    func = TOOL_FUNCS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return json.dumps(func(**inp))
    except Exception as e:
        return json.dumps({"error": str(e), "tool": name})


# ── Agent loops ──────────────────────────────────────────────────────

SYSTEM_PROMPT_TRIAGE = """You are an Email Agent in an AI sales pipeline with access to a real Gmail inbox.

Inbox-triage protocol:
1. Call fetch_unread_emails to load unread messages.
2. For EACH email returned:
   a. Call extract_signals on the body.
   b. Call classify_email with the from/subject/body.
   c. Call route_to_agent with classification, priority, and signals.
   d. Call mark_as_read with the email id.
3. If a personalized reply makes sense (proposal request, meeting interest, qualification questions),
   call create_draft with a short, professional response. NEVER attempt to send — a human reviews drafts.
4. After all emails are processed, write a brief summary of what you triaged.

Be systematic. Process one email fully before moving to the next.
"""

SYSTEM_PROMPT_SINGLE = """You are an Email Agent in an AI sales pipeline.

For the single email below:
1. Call read_email to parse it.
2. Call extract_signals on the body.
3. Call classify_email.
4. Call route_to_agent.

Use all four tools in order, then write a brief final summary.
"""


def _run_agent(system_prompt: str, user_prompt: str):
    client = _get_openai()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    yield ("log", "Email Agent started")
    yield ("log", "─" * 48)

    while True:
        response = client.chat.completions.create(
            model=MODEL, tools=TOOLS, messages=messages
        )
        message = response.choices[0].message

        if message.content:
            yield ("log", message.content)

        if not message.tool_calls:
            yield ("log", "─" * 48)
            yield ("log", "✓ Agent finished")
            break

        messages.append(message)

        for tc in message.tool_calls:
            name = tc.function.name
            inp = json.loads(tc.function.arguments)

            yield ("tool_call", {"name": name, "input": inp})
            raw_result = run_tool(name, inp)
            yield ("tool_result", {"name": name, "result": json.loads(raw_result)})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": raw_result,
            })


def run_email_agent(raw_email: str):
    """Triage one raw email string (legacy single-email mode)."""
    yield from _run_agent(
        SYSTEM_PROMPT_SINGLE,
        f"Analyze and route this email:\n\n{raw_email}",
    )


def run_inbox_triage(max_results: int = 5):
    """Pull unread Gmail, triage each, draft replies, mark read."""
    yield from _run_agent(
        SYSTEM_PROMPT_TRIAGE,
        f"Triage up to {max_results} unread emails from the Gmail inbox.",
    )
