# Email Agent — AI Sales Pipeline

Connects to a real Gmail inbox. Triages incoming mail with an OpenAI tool-using
agent (classify, extract signals, route to next pipeline agent, draft replies)
and sends outbound campaign emails with a human-in-the-loop approval step.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set your OpenAI key (the previous hard-coded key was removed — rotate it):
   ```
   export OPENAI_API_KEY="sk-..."
   ```

3. Get Gmail OAuth credentials:
   - Go to https://console.cloud.google.com/
   - Create a project, enable the **Gmail API**
   - APIs & Services → Credentials → Create Credentials → **OAuth client ID** → **Desktop app**
   - Download the JSON and save it here as `credentials.json`
   - First run will open a browser for consent and write `token.json` (reused after that)

## Usage

### Inbound triage (LLM-driven)

```
python app.py triage 5
```

The agent calls `fetch_unread_emails`, then for each message: `extract_signals`,
`classify_email`, `route_to_agent`, `mark_as_read`, and `create_draft` if a reply
is appropriate. Drafts land in your Gmail Drafts folder for you to review and
send manually — the LLM never sends.

### Outbound campaign sending (human-in-the-loop)

```
python app.py send-campaign
```

Walks `../campaign_emails.csv` (produced by the Campaign Agent) row-by-row,
prints each draft, and prompts:

```
[s]end  [e]dit then send  [k]skip  [q]uit >
```

`send_approved_email()` is the only function that actually sends — and it's
**deliberately not exposed to the LLM**, so autonomous sending isn't possible.

### Legacy single-email mode

```
python app.py classify path/to/email.txt
```

## Tools exposed to the LLM

| Tool | Purpose |
|------|---------|
| `fetch_unread_emails` | Pull unread Gmail messages |
| `read_email` | Parse FROM/SUBJECT/BODY from a raw email string |
| `extract_signals` | Detect budget, urgency, decision-maker, etc. |
| `classify_email` | `opportunity_qualification` vs `proposal` |
| `route_to_agent` | Hand off to next pipeline agent |
| `create_draft` | Save a Gmail draft (no auto-send) |
| `mark_as_read` | Remove UNREAD label after processing |

`send_approved_email()` is **not** a tool — only the CLI/UI calls it after the
human approves.

## Files

- `email_agent.py` — Agent library: tools, Gmail integration, agent loops
- `app.py` — CLI entry point: `triage` / `send-campaign` / `classify`
- `requirements.txt` — Dependencies
- `credentials.json` — Your OAuth client (gitignored)
- `token.json` — Cached OAuth tokens (gitignored, auto-generated)

## How it fits the pipeline

```
saudi-companies app    →  selects + scores targets   →  selected_companies.json
                                                              │
Campaign_Agent          →  drafts personalized mails  →  campaign_emails.csv
                                                              │
Email-Agent (outbound) →  human approves/edits       →  send via Gmail
Email-Agent (inbound)  →  triage replies             →  Proposal / Opp-Qual agents
```
