
import json
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

DATASET_NAME = "email-triage-security-dataset"

DATA_PATH = (
    Path(__file__).parent
    / "data"
    / "synthetic_emails.json"
)


def main():
    client = Client()

    with DATA_PATH.open(encoding="utf-8") as file:
        emails = json.load(file)

    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(
            dataset_name=DATASET_NAME
        )
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=(
                "Email classification and prompt injection "
                "security evaluation."
            ),
        )

    existing_ids = {
        example.inputs.get("id")
        for example in client.list_examples(
            dataset_id=dataset.id
        )
    }

    uploaded = 0

    for email in emails:
        if email["id"] in existing_ids:
            continue

        client.create_example(
            dataset_id=dataset.id,
            inputs={
                "id": email["id"],
                "sender": "test@example.com",
                "subject": email["subject"],
                "body": email["body"],
            },
            outputs={
                "expected_category": email["expected_category"],
                "is_attack": email["is_attack"],
            },
        )

        uploaded += 1
        print("Uploaded:", email["id"])

    total = len(
        list(client.list_examples(dataset_id=dataset.id))
    )

    print("\nDataset:", DATASET_NAME)
    print("New examples:", uploaded)
    print("Total examples:", total)


if __name__ == "__main__":
    main()
