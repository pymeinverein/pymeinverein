"""Run the mock server from the command line: ``python -m pymeinverein.testing``."""

from __future__ import annotations

import argparse
import asyncio

from .server import MockServer
from .state import DEMO_EMAIL, DEMO_PASSWORD


async def _serve(host: str, port: int) -> None:
    async with MockServer(host=host, port=port) as server:
        print(f"pymeinverein mock server listening on {server.url}")
        print(f"  api_url   = {server.api_url}")
        print(f"  login_url = {server.login_url}")
        print(f"  login     = {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print("Press Ctrl+C to stop.")
        await asyncio.Event().wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(_serve(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
