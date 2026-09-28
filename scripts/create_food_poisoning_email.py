#!/usr/bin/env python3
"""Create an unread food poisoning complaint email in devtesting03@gmail.com.

This script uses the connected Gmail OAuth tokens from secrets.json to either:
1. Send an email to devtesting03@gmail.com (which lands in Inbox as unread), OR
2. Insert a message directly into INBOX with label UNREAD via Gmail API.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

SECRETS_PATH = Path("/Users/mac/.config/coworker/secrets.json")

def get_gmail_token() -> str:
    secrets = json.loads(SECRETS_PATH.read_text("utf-8"))
    acc = secrets.get("gmail:account:devtesting03@gmail.com", {})
    token = acc.get("access_token")
    client_id = acc.get("client_id")
    client_secret = acc.get("client_secret")
    refresh_token = acc.get("refresh_token")

    # Check / refresh token if needed
    test_req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(test_req) as resp:
            data = json.loads(resp.read().decode())
            print(f"[OAuth] Token is active for: {data.get('emailAddress')}")
            return token
    except urllib.error.HTTPError as e:
        if e.code == 401 and refresh_token and client_id and client_secret:
            print("[OAuth] Token expired, refreshing via Google OAuth...")
            refresh_data = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }).encode("utf-8")
            refresh_req = urllib.request.Request(
                "https://oauth2.googleapis.com/token",
                data=refresh_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(refresh_req) as ref_resp:
                new_tokens = json.loads(ref_resp.read().decode())
                new_token = new_tokens["access_token"]
                acc["access_token"] = new_token
                secrets["gmail:account:devtesting03@gmail.com"] = acc
                SECRETS_PATH.write_text(json.dumps(secrets, indent=2), "utf-8")
                print("[OAuth] Refreshed access token successfully.")
                return new_token
        raise

def create_food_poisoning_email():
    token = get_gmail_token()

    msg = EmailMessage()
    msg["To"] = "devtesting03@gmail.com"
    msg["From"] = "Dr. Maximilian Weber <dr.weber@example.de>"
    msg["Subject"] = "Urgent Complaint: Severe Food Poisoning after Dining at Restaurant on September 20, 2026"

    body_content = """Dear Management,

I am writing to file an urgent complaint regarding our dining experience at your restaurant yesterday evening, September 20, 2026 at 7:45 PM.

My wife and I dined at your establishment. For our appetizers, we both ordered and consumed the 'Beef Tartare with Truffle Aioli' and 'Fresh Oysters Fine de Claire'. At approximately 11:45 PM (exactly 4.0 hours after consumption), both of us were stricken with acute violent stomach cramps, intractable vomiting, chills, and high fever (39.6°C / 103.3°F).

At 2:15 AM, emergency paramedics were dispatched to our residence and transported us via ambulance to the emergency department of the University Hospital. The attending physician diagnosed severe acute bacterial foodborne gastroenteritis. Both of us remain hospitalized for intravenous fluid resuscitation.

I have preserved our itemized dining receipt totaling $284.50, along with our emergency department admission summary and physician's certification. I demand that you report this serious incident immediately to your Commercial General Liability insurance carrier and forward us the official Incident Claim Form without delay!

Sincerely,
Dr. Maximilian Weber
Phone: +1 555-019-8765
"""
    msg.set_content(body_content)

    raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8").rstrip("=")

    # Method 1: Try insert directly into INBOX as UNREAD
    print("[Gmail API] Inserting message directly into INBOX as UNREAD...")
    insert_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    insert_payload = {
        "raw": raw_b64,
        "labelIds": ["INBOX", "UNREAD"],
    }
    
    insert_req = urllib.request.Request(
        insert_url,
        data=json.dumps(insert_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(insert_req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"[Gmail API SUCCESS] Message created in INBOX!")
            print(f"Message ID: {result.get('id')}")
            print(f"Thread ID: {result.get('threadId')}")
            print(f"Label IDs: {result.get('labelIds')}")
            return result
    except urllib.error.HTTPError as e:
        print(f"[Insert failed: {e.code}] Falling back to messages.send...")
        send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        send_req = urllib.request.Request(
            send_url,
            data=json.dumps({"raw": raw_b64}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(send_req) as resp2:
            result = json.loads(resp2.read().decode("utf-8"))
            print(f"[Gmail Send SUCCESS] Message sent to devtesting03@gmail.com!")
            print(f"Message ID: {result.get('id')}")
            return result

if __name__ == "__main__":
    create_food_poisoning_email()
