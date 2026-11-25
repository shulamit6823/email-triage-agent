
from uuid import uuid4
from langgraph.types import Command
from graph import build_graph

graph = build_graph(secure=True, send_fn=None)

config = {
    "configurable": {
        "thread_id": str(uuid4())
    }
}

result = graph.invoke(
    {
        "sender": "test@example.com",
        "subject": "בקשת מידע",
        "body": "אשמח לקבל מידע על שעות הפעילות.",
        "revisions": 0
    },
    config
)

snapshot = graph.get_state(config)

print("\nCategory:", result.get("category"))
print("\nDraft:", result.get("draft"))
print("\nNext node:", snapshot.next)

if not any(task.interrupts for task in snapshot.tasks):
    raise RuntimeError("No human review interrupt found")

print("\nWaiting for human approval")

while True:
    action = input("approve / revise / reject: ").strip().lower()

    if action not in ("approve", "revise", "reject"):
        print("Invalid action")
        continue

    feedback = ""

    if action == "revise":
        feedback = input("Revision instructions: ")

    result = graph.invoke(
        Command(
            resume={
                "action": action,
                "feedback": feedback
            }
        ),
        config
    )

    snapshot = graph.get_state(config)

    print("\nDraft:", result.get("draft"))
    print("Final status:", result.get("final_status"))

    if not snapshot.next:
        print("\nWorkflow completed")
        break
