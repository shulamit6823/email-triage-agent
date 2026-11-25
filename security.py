import re


SAFE_FALLBACK_DRAFT = (
    "שלום, תודה על פנייתך. "
    "הצוות שלנו יבדוק את הנושא ויחזור אליך בהקדם."
)


def sanitize_email(body: str) -> str:
    # הסרת תווי בקרה
    body = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", body)

    # מניעת סגירה מזויפת של תגיות המייל
    body = re.sub(
        r"</?email\s*>",
        "[EMAIL_TAG]",
        body,
        flags=re.IGNORECASE
    )

    # הגבלת אורך הקלט
    return body[:12000].strip()


def validate_draft(draft: str, sender: str) -> list[str]:
    reasons = []

    if not draft.strip():
        reasons.append("Empty draft")

    if len(draft) > 2000:
        reasons.append("Draft is too long")

    if re.search(r"https?://|www\.", draft, re.IGNORECASE):
        reasons.append("Unauthorized link")

    if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", draft):
        reasons.append("Unauthorized email address")

    if re.search(r"\+?\d(?:[\s().-]*\d){8,}", draft):
        reasons.append("Unauthorized phone number")

    return reasons