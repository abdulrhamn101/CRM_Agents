"""Email Agent CLI — human-in-the-loop driver.

Commands:
  python app.py triage [n]            # Fetch up to n unread Gmail messages, triage with the agent
  python app.py classify <path.eml>   # Triage one raw email file (legacy single-message mode)
  python app.py enrich-emails         # Walk campaign_emails.csv and fill in missing `email` cells
  python app.py send-campaign         # Walk campaign_emails.csv, approve/edit each, then send

Env vars:
  OPENAI_API_KEY                       Required for triage/classify
  EMAIL_AGENT_TEST_RECIPIENT           If set, send-campaign routes every send to this address
                                       (overrides each row's `email`). Useful for end-to-end testing.
"""

import os
import sys
import csv
from pathlib import Path

from email_agent import (
    run_inbox_triage,
    run_email_agent,
    send_approved_email,
)
from email_finder import find_email


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN_CSV = PROJECT_ROOT / "campaign_emails.csv"


def _stream(events) -> None:
    for kind, data in events:
        if kind == "log":
            print(data)
        elif kind == "tool_call":
            keys = list(data["input"].keys())
            print(f"  → {data['name']}({', '.join(keys)})")
        elif kind == "tool_result":
            result = data["result"]
            if isinstance(result, dict):
                preview = {k: result[k] for k in list(result)[:3]}
                print(f"    ← {data['name']}: {preview}")
            else:
                print(f"    ← {data['name']}: {result}")


def cmd_triage(max_results: int) -> None:
    _stream(run_inbox_triage(max_results=max_results))


def cmd_classify(path: str) -> None:
    raw = Path(path).read_text(encoding="utf-8")
    _stream(run_email_agent(raw))


def _read_multiline(prompt: str) -> str:
    print(prompt + "  (end with a line containing only END)")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def cmd_enrich_emails() -> None:
    """Walk campaign_emails.csv and fill in missing `email` cells using email_finder."""
    if not CAMPAIGN_CSV.exists():
        print(f"No campaign file at {CAMPAIGN_CSV}. Run the Campaign Agent first.")
        return

    with CAMPAIGN_CSV.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    updated = 0
    for i, row in enumerate(rows, 1):
        existing = (row.get("email") or "").strip()
        if existing and existing.lower() not in ("n/a", "na", "none", "-"):
            continue

        company = row.get("company_name", "?")
        website = row.get("website", "").strip()
        print(f"[{i}/{len(rows)}] {company} ({website or 'no website'})...", end=" ", flush=True)

        try:
            result = find_email(company, website=website or None, city=row.get("city"))
            if result.get("email"):
                row["email"] = result["email"]
                updated += 1
                print(f"→ {result['email']}  [{result['source']} / {result['confidence']}]")
            else:
                print(f"not found ({result.get('source')})")
        except Exception as e:
            print(f"error: {e}")

    with CAMPAIGN_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Updated {updated}/{len(rows)} rows in {CAMPAIGN_CSV.name}.")


def cmd_send_campaign() -> None:
    if not CAMPAIGN_CSV.exists():
        print(f"No campaign file at {CAMPAIGN_CSV}. Run the Campaign Agent first.")
        return

    with CAMPAIGN_CSV.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    test_recipient = os.environ.get("EMAIL_AGENT_TEST_RECIPIENT", "").strip()
    if test_recipient:
        print(f"⚠️  TEST MODE — all sends will go to {test_recipient}\n")

    print(f"Loaded {len(rows)} draft email(s) from {CAMPAIGN_CSV.name}\n")

    sent_count = 0
    for i, row in enumerate(rows, 1):
        original_to = (row.get("email") or row.get("recipient_email") or "").strip()
        to = test_recipient or original_to
        company = row.get("company_name", "?")

        if not to:
            print(f"[{i}/{len(rows)}] {company} — no recipient email, skipping. "
                  f"(Tip: run `python app.py enrich-emails` or set EMAIL_AGENT_TEST_RECIPIENT.)")
            continue

        subject = row.get("email_subject", "")
        body = row.get("email_body", "")

        print("─" * 64)
        print(f"[{i}/{len(rows)}] {company}")
        if test_recipient and original_to and original_to != to:
            print(f"To:      {to}  (test override, real address: {original_to})")
        else:
            print(f"To:      {to}")
        print(f"Subject: {subject}")
        print()
        print(body)
        print("─" * 64)

        choice = input("[s]end  [e]dit then send  [k]skip  [q]uit > ").strip().lower()
        if choice == "q":
            break
        if choice == "k":
            continue
        if choice == "e":
            new_subj = input(f"New subject (blank = keep current):\n> ").strip()
            if new_subj:
                subject = new_subj
            new_body = _read_multiline("New body:")
            if new_body.strip():
                body = new_body

        try:
            result = send_approved_email(to=to, subject=subject, body=body)
            print(f"✓ Sent. Message ID: {result['message_id']}\n")
            sent_count += 1
        except Exception as e:
            print(f"✗ Send failed: {e}\n")

    print(f"Done. Sent {sent_count} email(s).")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "triage":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        cmd_triage(n)
    elif cmd == "classify":
        if len(sys.argv) < 3:
            print("Usage: python app.py classify <path>")
            return
        cmd_classify(sys.argv[2])
    elif cmd == "enrich-emails":
        cmd_enrich_emails()
    elif cmd == "send-campaign":
        cmd_send_campaign()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
