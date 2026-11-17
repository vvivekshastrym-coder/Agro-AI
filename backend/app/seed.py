"""Legacy synthetic-data cleanup command, intentionally disabled.

The historical implementation deleted whole business tables without being
able to distinguish real rows from demo rows. Preserve the module path for
operators and tests, but fail closed rather than risk destroying records.
"""
import os
import sys


def purge_fictional_seed_data() -> None:
    raise RuntimeError(
        "Automatic demo-data deletion is disabled because records are not reliably classified. "
        "Use a reviewed cleanup against an isolated database and explicit test record IDs."
    )


if __name__ == "__main__":
    environment = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if environment in {"production", "prod"}:
        sys.exit("Refusing to run demo-data cleanup in a production environment.")
    if environment not in {"development", "dev", "test", "testing"} or os.getenv("ALLOW_DEMO_SEED") != "1":
        sys.exit("Refusing to seed or clean outside an explicitly isolated demo/test environment.")
    sys.exit("Legacy cleanup is disabled because existing rows cannot be safely identified as synthetic.")
