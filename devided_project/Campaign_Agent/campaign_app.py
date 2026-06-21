import os
import sys

from campaign_agent import CampaignAgent

SELECTED_COMPANIES_PATH = (
    "/Users/abdulrhman/Library/CloudStorage/OneDrive-UniversityofPrinceMugrin/"
    "Personal/Development/Agentic_bootcamp_SDA/devided_project/selected_companies.json"
)


def main():
    if not os.path.exists(SELECTED_COMPANIES_PATH):
        print(
            "No selected_companies.json found. "
            "Open the Filter Agent, pick targets, click 'Confirm Targets', then run this again."
        )
        print(f"Expected file: {SELECTED_COMPANIES_PATH}")
        sys.exit(1)

    agent = CampaignAgent()

    output = agent.run(
        input_file=SELECTED_COMPANIES_PATH,
        limit=None,
        source="selected",
    )

    print(f"Generated emails for {output['total_companies']} target companies.")
    print(f"Output: {output['output_file']}")


if __name__ == "__main__":
    main()
