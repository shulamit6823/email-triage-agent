
"""סוכן אוטומטי לקריאת מיילים ויצירת טיוטות מאובטחות."""

import time

from gmail_client import GmailClient
from graph import build_graph

CHECK_INTERVAL = 30


def process_email(gmail, graph, mail):

    print("\n" + "=" * 60)
    print(f"מאת: {mail['sender']}")
    print(f"נושא: {mail['subject']}")

    config = {
        "configurable": {
            "thread_id": mail["id"]
        }
    }

    snapshot = graph.get_state(config)

    if snapshot.values:
        result = snapshot.values

        if not snapshot.next:
            gmail.mark_processed(mail["id"])
            return

    else:
        result = graph.invoke(
            {
                "sender": mail["sender"],
                "subject": mail["subject"],
                "body": mail["body"],
                "thread_id": mail["thread_id"],
                "message_id": mail["message_id"],
                "revisions": 0
            },
            config
        )

    category = result.get("category", "")

    print("סיווג:", category)

    if category == "spam":
        gmail.mark_processed(mail["id"])
        print("ספאם - לא נוצרה טיוטה")
        return

    draft = result.get("draft", "")

    if not draft.strip():
        raise ValueError("לא התקבלה טיוטה תקינה")

    if result.get("security_flag"):
        print("זוהתה בעיית אבטחה")
        print(result.get("security_reasons", []))

    existing_draft_id = result.get("gmail_draft_id")

    if existing_draft_id:
        print("כבר קיימת טיוטה")
        gmail.mark_processed(mail["id"])
        return

    draft_id = gmail.create_draft_checked(
        to=mail["sender"],
        subject=mail["subject"],
        body=draft,
        thread_id=mail["thread_id"],
        message_id=mail["message_id"]
    )

    graph.update_state(
        config,
        {"gmail_draft_id": draft_id},
        as_node="security_check"
    )

    gmail.mark_processed(mail["id"])

    print("הטיוטה נשמרה ב-Gmail")
    print("מזהה טיוטה:", draft_id)
    print("ממתינה לאישור אנושי")


def main():

    gmail = GmailClient()

    graph = build_graph(
        secure=True,
        send_fn=None
    )

    print("=" * 60)
    print("Email Triage Agent")
    print("חשבון:", gmail.me)
    print("מצב: יצירת טיוטות אוטומטית בלבד")
    print("בדיקת הודעות כל", CHECK_INTERVAL, "שניות")
    print("לעצירת הסוכן לחץ Ctrl+C")
    print("=" * 60)

    try:
        while True:

            try:
                mails = gmail.fetch_unprocessed()

                for mail in mails:
                    try:
                        process_email(gmail, graph, mail)

                    except Exception as error:
                        print("שגיאה בטיפול בהודעה:", error)

                if not mails:
                    print("אין הודעות חדשות לטיפול")

            except Exception as error:
                print("שגיאה בחיבור או בקריאה:", error)

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nהסוכן נעצר")


if __name__ == "__main__":
    main()
