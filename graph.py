"""הגרף: מחבר את הצמתים עם קשתות (Edges).

הזרימה:
START -> sanitize -> classify --(spam)--> handle_spam -> END
                         |
                         +--(urgent/routine)--> draft -> security_check -> human_review
                                                   ^                            |
                                                   |--------(revise)------------+--(approve)--> finalize -> END
                                                                                +--(reject)---> rejected -> END
"""
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from nodes import MAX_REVISIONS, make_nodes
from state import EmailState


def route_after_classify(state: EmailState) -> str:
    """ענף מותנה #1: ספאם לא מקבל תשובה בכלל."""
    return "spam" if state["category"] == "spam" else "draft"


def route_after_review(state: EmailState) -> str:
    """ענף מותנה #2 + לולאה: 'revise' חוזר לכתיבה מחדש, עד מגבלה."""
    decision = state.get("human_decision", "reject")
    if decision == "approve":
        return "approve"
    if decision == "revise" and state.get("revisions", 0) <= MAX_REVISIONS:
        return "revise"
    return "reject"


def build_graph(secure: bool = True, send_fn=None):
    n = make_nodes(secure, send_fn)
    g = StateGraph(EmailState)

    for name in ("sanitize", "classify", "draft", "security_check",
                 "human_review", "finalize", "handle_spam", "rejected"):
        g.add_node(name, n[name])

    g.add_edge(START, "sanitize")
    g.add_edge("sanitize", "classify")
    g.add_conditional_edges("classify", route_after_classify,
                            {"spam": "handle_spam", "draft": "draft"})
    g.add_edge("draft", "security_check")
    g.add_edge("security_check", "human_review")
    g.add_conditional_edges("human_review", route_after_review,
                            {"approve": "finalize", "revise": "draft", "reject": "rejected"})
    g.add_edge("handle_spam", END)
    g.add_edge("finalize", END)
    g.add_edge("rejected", END)

    conn = sqlite3.connect(
        "agent_state.db",
        check_same_thread=False
    )

    checkpointer = SqliteSaver(conn)

    return g.compile(checkpointer=checkpointer)