"""Run the isolated controlled BOLA evaluation service.

Initialize private state first with `python -m bola_lab.controller ... init`.
"""

from __future__ import annotations

import sys

from bola_lab.network import NetworkPolicyError, listener_settings_from_environment
from bola_lab.server import StartupError, create_app


if __name__ == "__main__":
    try:
        settings = listener_settings_from_environment()
        application = create_app()
    except (NetworkPolicyError, StartupError):
        print("BOLA lab cannot start with the configured private state or network policy.", file=sys.stderr)
        raise SystemExit(2)
    application.run(host=settings.host, port=settings.port, debug=False)
