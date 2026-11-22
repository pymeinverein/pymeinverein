#!/usr/bin/env python3
"""Send one raw request to the real MeinVerein API and show the answer.

A development tool for exploring endpoints before they are implemented::

    export MEINVEREIN_EMAIL=... MEINVEREIN_PASSWORD=...
    uv run python scripts/probe.py GET '/protected/club/{club}/list/all'
    uv run python scripts/probe.py POST '/protected/club/{club}/list/create' \
        --json '{"name": "pymeinverein-test", "type": 0, "sourceListId": null}'

``{club}`` is replaced by the id of the account's demo club. The tool refuses
to run if the account has no demo club, and it refuses paths that name another
club, so experiments cannot touch real data.

By default only the *shape* of the answer is printed (keys, one list element,
shortened strings); ``--full`` prints everything. To avoid a login per call,
set ``MEINVEREIN_TOKEN`` to a session token (``--print-token`` shows one).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from typing import Any

from pymeinverein import MeinVereinClient


def shape(value: Any, depth: int = 0, max_depth: int = 6) -> Any:
    """Shorten a JSON value so its structure fits on a screen."""
    if isinstance(value, dict):
        if depth >= max_depth:
            return f"{{{len(value)} keys}}"
        return {
            key: shape(item, depth + 1, max_depth)
            for key, item in value.items()
            if key != "_links"
        }
    if isinstance(value, list):
        if not value:
            return []
        return [shape(value[0], depth + 1, max_depth), f"... {len(value)} items"]
    if isinstance(value, str) and len(value) > 80:
        return value[:80] + "..."
    return value


async def run(args: argparse.Namespace) -> int:
    # MEINVEREIN_TOKEN is read by the client itself and skips the login.
    async with MeinVereinClient() as mv:
        clubs = await mv.clubs.list()
        demo = [club for club in clubs if club.is_demo]
        if len(demo) != 1:
            print("The account needs exactly one demo club.", file=sys.stderr)
            return 2
        if args.print_token:
            print(mv.token)
            return 0
        path = args.path.replace("{club}", str(demo[0].id))
        for club in clubs:
            if not club.is_demo and re.search(rf"(?<!\d){club.id}(?!\d)", path):
                print(f"Refusing to touch club {club.name!r}.", file=sys.stderr)
                return 2

        body = json.loads(args.json) if args.json is not None else None
        if body is None and args.method in ("POST", "PUT", "PATCH"):
            body = {}
        headers = {"Authorization": f"Bearer {mv.token}", "Accept": "application/json"}
        if args.api_version:
            headers["x-api-version"] = args.api_version
        transport = mv._transport
        session = transport._session_provider()
        async with session.request(
            args.method, transport.url(path), json=body, headers=headers
        ) as response:
            text = await response.text()
            print(
                f"{args.method} {path} -> {response.status} "
                f"{response.content_type} ({len(text)} bytes)"
            )
        try:
            payload = json.loads(text)
        except ValueError:
            print(text[: args.limit])
            return 0
        shown = payload if args.full else shape(payload)
        indent = 1 if args.full else None
        print(json.dumps(shown, ensure_ascii=False, indent=indent)[: args.limit])
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    parser.add_argument("path", nargs="?", default="/protected/accounts")
    parser.add_argument("--json", help="request body as JSON text")
    parser.add_argument("--api-version", help="value of the x-api-version header")
    parser.add_argument("--full", action="store_true", help="print the whole answer")
    parser.add_argument("--limit", type=int, default=4000, help="max characters")
    parser.add_argument("--print-token", action="store_true", help="print a token")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
