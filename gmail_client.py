
"""חיבור ל-Gmail: קריאה, יצירת טיוטות, שליחה ותיוג."""

import base64
import os
import re
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LABEL_NAME = "agent-processed"
AGENT_HEADER = "X-Triage-Agent"


def _get_service():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

    with open("token.json", "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------- עזרים לפירוק הודעה ----------

def _header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(
        data + "=" * (-len(data) % 4)
    ).decode("utf-8", errors="replace")


def _find_part(payload: dict, mime: str) -> str:
    if (
        payload.get("mimeType") == mime
        and payload.get("body", {}).get("data")
    ):
        return _decode(payload["body"]["data"])

    for part in payload.get("parts", []) or []:
        found = _find_part(part, mime)

        if found:
            return found

    return ""


def extract_text(payload: dict) -> str:
    text = _find_part(payload, "text/plain")

    if text:
        return text

    html = _find_part(payload, "text/html")

    html = re.sub(
        r"<!--.*?-->", "", html, flags=re.DOTALL
    )

    html = re.sub(
        r"<(script|style).*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    return re.sub(r"<[^>]+>", " ", html)


def _raw(msg: EmailMessage) -> str:
    return base64.urlsafe_b64encode(
        msg.as_bytes()
    ).decode()


class GmailClient:

    def __init__(self):
        self.service = _get_service()

        self.me = (
            self.service.users()
            .getProfile(userId="me")
            .execute()["emailAddress"]
            .lower()
        )

        self.allowed = {
            a.strip().lower()
            for a in os.getenv(
                "ALLOWED_SENDERS", ""
            ).split(",")
            if a.strip()
        }

        if not self.allowed:
            raise SystemExit(
                "חובה להגדיר ALLOWED_SENDERS ב-.env"
            )

        self.max_emails = int(
            os.getenv("MAX_EMAILS", "10")
        )

        self.max_sends = int(
            os.getenv("MAX_SENDS", "10")
        )

        self.sent_count = 0
        self.label_id = self._ensure_label()

    # ---------- תוויות ----------

    def _ensure_label(self) -> str:
        labels = (
            self.service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )

        for lb in labels:
            if lb["name"] == LABEL_NAME:
                return lb["id"]

        created = (
            self.service.users()
            .labels()
            .create(
                userId="me",
                body={"name": LABEL_NAME}
            )
            .execute()
        )

        return created["id"]

    def mark_processed(self, gmail_id: str) -> None:
        self.service.users().messages().modify(
            userId="me",
            id=gmail_id,
            body={"addLabelIds": [self.label_id]}
        ).execute()

    # ---------- קריאת מיילים ----------

    def fetch_unprocessed(self) -> list[dict]:

        senders = " OR ".join(sorted(self.allowed))

        query = (
            f"in:inbox -label:{LABEL_NAME} "
            f"newer_than:7d from:({senders})"
        )

        resp = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=self.max_emails
            )
            .execute()
        )

        mails = []

        for ref in resp.get("messages", []):

            msg = (
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="full"
                )
                .execute()
            )

            p = msg["payload"]

            addr = parseaddr(
                _header(p, "From")
            )[1].lower()

            if addr not in self.allowed:
                continue

            if _header(p, AGENT_HEADER):
                continue

            auto = _header(
                p, "Auto-Submitted"
            ).lower()

            if auto and auto != "no":
                continue

            mails.append({
                "id": msg["id"],
                "thread_id": msg["threadId"],
                "message_id": _header(
                    p, "Message-ID"
                ),
                "sender": addr,
                "subject": (
                    _header(p, "Subject")
                    or "(ללא נושא)"
                ),
                "body": extract_text(p),
            })

        return mails

    # ---------- בניית הודעה עם בקרות אבטחה ----------

    def _build_reply(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        message_id: str | None = None
    ) -> dict:

        to_addr = parseaddr(to)[1].lower()

        if to_addr not in self.allowed:
            raise PermissionError(
                f"הנמען {to_addr} אינו מורשה"
            )

        header_values = (
            to + subject + (message_id or "")
        )

        if any(c in header_values for c in "\r\n"):
            raise ValueError(
                "חשד להזרקת כותרות"
            )

        if not body.strip():
            raise ValueError(
                "גוף ההודעה ריק"
            )

        msg = EmailMessage()

        msg["To"] = to_addr

        msg["Subject"] = (
            subject
            if subject.lower().startswith("re:")
            else f"Re: {subject}"
        )

        if message_id:
            msg["In-Reply-To"] = message_id
            msg["References"] = message_id

        msg[AGENT_HEADER] = "1"

        msg.set_content(body)

        payload = {"raw": _raw(msg)}

        if thread_id:
            payload["threadId"] = thread_id

        return payload

    # ---------- יצירת טיוטה ----------

    def create_draft_checked(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        message_id: str | None = None
    ) -> str:

        payload = self._build_reply(
            to,
            subject,
            body,
            thread_id,
            message_id
        )

        draft = (
            self.service.users()
            .drafts()
            .create(
                userId="me",
                body={"message": payload}
            )
            .execute()
        )

        return draft["id"]

    # ---------- עדכון טיוטה ----------

    def update_draft_checked(
        self,
        draft_id: str,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        message_id: str | None = None
    ) -> str:

        payload = self._build_reply(
            to,
            subject,
            body,
            thread_id,
            message_id
        )

        draft = (
            self.service.users()
            .drafts()
            .update(
                userId="me",
                id=draft_id,
                body={"message": payload}
            )
            .execute()
        )

        return draft["id"]

    # ---------- קריאת טיוטה ----------

    def get_draft(self, draft_id: str) -> dict:

        return (
            self.service.users()
            .drafts()
            .get(
                userId="me",
                id=draft_id,
                format="full"
            )
            .execute()
        )

    # ---------- שליחת טיוטה לאחר אישור ----------

    def send_draft_checked(
        self,
        draft_id: str,
        expected_sender: str,
        approved: bool = False
    ) -> str:

        if approved is not True:
            raise PermissionError(
                "נדרש אישור אנושי מפורש"
            )

        if self.sent_count >= self.max_sends:
            raise RuntimeError(
                "הגעת למכסת השליחות"
            )

        draft = self.get_draft(draft_id)

        payload = draft["message"]["payload"]

        to_header = _header(payload, "To")

        recipient = parseaddr(
            to_header
        )[1].lower()

        if recipient not in self.allowed:
            raise PermissionError(
                "הנמען אינו מורשה"
            )

        if recipient != expected_sender.strip().lower():
            raise PermissionError(
                "הנמען אינו השולח המקורי"
            )

        if _header(payload, "Cc") or _header(payload, "Bcc"):
            raise PermissionError(
                "אסור להוסיף נמענים נוספים"
            )

        if to_header.strip().lower() != recipient:
            raise PermissionError(
                "כותרת הנמען אינה תקינה"
            )

        body = extract_text(payload)

        from security import validate_draft

        reasons = validate_draft(
            body, expected_sender
        )

        if reasons:
            raise PermissionError(
                "הטיוטה לא עברה בדיקת אבטחה: "
                + ", ".join(reasons)
            )

        self.service.users().drafts().send(
            userId="me",
            body={"id": draft_id}
        ).execute()

        self.sent_count += 1

        return "sent_after_human_approval"

    # ---------- שליחה ישירה: תאימות לקוד הקיים ----------

    def send_reply_checked(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        message_id: str | None = None
    ) -> str:

        if self.sent_count >= self.max_sends:
            raise RuntimeError(
                "הגעת למכסת השליחות"
            )

        payload = self._build_reply(
            to,
            subject,
            body,
            thread_id,
            message_id
        )

        self.service.users().messages().send(
            userId="me",
            body=payload
        ).execute()

        self.sent_count += 1

        return "sent_after_human_approval"

    # ---------- הכנסת הודעות בדיקה ----------

    def insert_test_email(
        self,
        from_addr: str,
        subject: str,
        body: str
    ) -> None:

        msg = EmailMessage()

        msg["From"] = from_addr
        msg["To"] = self.me
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        msg.set_content(body)

        self.service.users().messages().insert(
            userId="me",
            body={
                "raw": _raw(msg),
                "labelIds": ["INBOX", "UNREAD"]
            }
        ).execute()
