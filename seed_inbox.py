"""מכניס מיילי בדיקה סינתטיים לתיבה שלך (בלי לשלוח), כדי שיהיה על מה להריץ.

  python seed_inbox.py                        # ברירת מחדל: 4 מיילים לדוגמה
  python seed_inbox.py email-05 email-27      # מיילים לפי מזהה
"""
import json
import os
import sys

from dotenv import load_dotenv

from gmail_client import GmailClient

load_dotenv()
DEFAULT_IDS = ["email-01", "email-02", "email-21", "email-30"]  # רגיל, דחוף, שתי מתקפות

test_sender = os.getenv("TEST_SENDER", "").strip().lower()
if not test_sender:
    sys.exit("הגדירי TEST_SENDER ב-.env")

gmail = GmailClient()
if test_sender not in gmail.allowed:
    sys.exit("TEST_SENDER חייב להיות ברשימת ALLOWED_SENDERS")

emails = {e["id"]: e for e in json.load(open("data/synthetic_emails.json", encoding="utf-8"))}
for eid in (sys.argv[1:] or DEFAULT_IDS):
    e = emails[eid]
    gmail.insert_test_email(test_sender, e["subject"], e["body"])
    print("הוכנס:", eid, "-", e["subject"])
