"""Launch the client-only SENTRY worker; deliberately does not import ANIMA Core."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"))

from household_worker import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
