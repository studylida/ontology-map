"""Retired #139 Qwen trial; its old paid approval is not a Kimi authorization.

Historical code and evidence remain in Git history at
96f28c3b49637cb6ff0937935d08d0932e9ae79e. This entry point never reads old
credentials, touches a DB, sends a model request or resumes that trial.
Use kimi_clients with application_execution.run_document and a new explicitly
bounded pilot. See docs/development/kimi.md.
"""


def main() -> int:
    raise SystemExit("LEGACY_TRIAL_RETIRED_USE_KIMI_APPLICATION_EXECUTION")


if __name__ == "__main__":
    main()
