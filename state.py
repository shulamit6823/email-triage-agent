
"""ה-State: כל המידע שעובר בין הצמתים בגרף.

כל צומת מקבל את ה-State ומחזיר רק את השדות שהוא משנה.
"""

from typing import Literal, TypedDict

Category = Literal["urgent", "routine", "spam"]


class EmailState(TypedDict, total=False):

    # --- קלט חיצוני, לא מהימן ---
    sender: str
    subject: str
    body: str
    thread_id: str
    message_id: str

    # --- עיבוד באמצעות AI ---
    clean_body: str
    category: Category
    draft: str

    # --- בקרות אבטחה ---
    security_flag: bool
    security_reasons: list[str]

    # --- שמירת טיוטה ב-Gmail ---
    gmail_draft_id: str

    # --- החלטת האדם ---
    human_decision: str
    feedback: str
    revisions: int

    # --- תוצאה סופית ---
    final_status: str
