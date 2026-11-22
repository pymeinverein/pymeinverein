"""Mock server for testing code that uses pymeinverein without the real service."""

from .server import MockServer
from .state import (
    DEMO_CLUB_ID,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    REGULAR_CLUB_ID,
    MockState,
    MockUser,
)

__all__ = [
    "DEMO_CLUB_ID",
    "DEMO_EMAIL",
    "DEMO_PASSWORD",
    "REGULAR_CLUB_ID",
    "MockServer",
    "MockState",
    "MockUser",
]
