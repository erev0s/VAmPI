"""Run the isolated controlled BOLA evaluation service.

Initialize private state first with `python -m bola_lab.controller ... init`.
"""

from __future__ import annotations

import os
import sys

from bola_lab.server import StartupError, create_app


if __name__ == "__main__":
    try:
        application = create_app()
    except StartupError:
        print("BOLA lab cannot start with the configured private state.", file=sys.stderr)
        raise SystemExit(2)
    host = os.environ.get("BOLA_LAB_HOST", "0.0.0.0")
    port = int(os.environ.get("BOLA_LAB_PORT", "5003"))
    application.run(host=host, port=port, debug=False)
