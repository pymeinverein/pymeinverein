"""In-memory data of the mock server.

The state is plain Python data so tests can inspect and change it directly,
for example ``server.state.users["demo@example.org"].password = "other"``.
All sample data is invented; it only mirrors the *shape* of real API answers.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from . import seed

DEMO_EMAIL = "demo@example.org"
DEMO_PASSWORD = "mock-password"
DEMO_CLUB_ID = 1002
REGULAR_CLUB_ID = 1001

type Json = dict[str, Any]


def now_iso() -> str:
    """Current time in the format the API uses (``2026-11-09T20:31:36.636Z``)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class MockUser:
    """A Buhl account that can log in to the mock server."""

    id: int
    email: str
    password: str
    first_name: str = "Demo"
    last_name: str = "User"
    #: When set, the login asks for this two-factor code.
    two_factor_code: str | None = None
    #: When > 0 the login answers "wrong-password-wait" with this wait time.
    locked_ms: int = 0

    def to_api(self) -> Json:
        return {
            "id": self.id,
            "email": self.email,
            "approved": True,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "gender": None,
            "pictureExists": False,
            "lastLogin": "2026-01-05T09:00:00.000Z",
            "createdAt": "2026-01-05T09:00:00.000Z",
            "updatedAt": "2026-01-05T09:00:00.000Z",
        }


def _club(club_id: int, name: str, *, is_demo: bool, owner: MockUser) -> Json:
    return {
        "id": club_id,
        # The demo club of the real service has no category either.
        "categoryId": None if is_demo else 15,
        "creator": {
            "userId": owner.id,
            "firstName": owner.first_name,
            "lastName": owner.last_name,
            "email": owner.email,
        },
        "name": name,
        "name2": "",
        "headOffice": "",
        "number": None,
        "registered": False,
        "isDemo": is_demo,
        # Like on the real service, demo clubs may not send e-mail.
        "sendEmailEnabled": not is_demo,
        "email": None,
        "phone": None,
        "website": None,
        "memberCount": 0,
        "clubOwnerId": owner.id,
        "createdAt": "2026-01-05T09:00:00.000Z",
        "updatedAt": "2026-01-05T09:00:00.000Z",
    }


@dataclass
class MockState:
    """Everything the mock server knows."""

    users: dict[str, MockUser] = field(default_factory=dict)
    #: Clubs by id (API shaped dicts).
    clubs: dict[int, Json] = field(default_factory=dict)
    selected_club_id: int | None = None
    #: One-time login tickets -> e-mail.
    tickets: dict[str, str] = field(default_factory=dict)
    #: Pending two-factor tickets -> e-mail.
    two_factor_tickets: dict[str, str] = field(default_factory=dict)
    #: Valid session tokens -> e-mail.
    tokens: dict[str, str] = field(default_factory=dict)
    #: Members by club id and member id, shaped like the detail answer.
    members: dict[int, dict[int, Json]] = field(default_factory=dict)
    #: Permission role ids by member id.
    member_roles: dict[int, list[int]] = field(default_factory=dict)
    #: Lists by club id and list id. Keys starting with "_" are internal.
    lists: dict[int, dict[int, Json]] = field(default_factory=dict)
    #: Levels of the department structure by club id.
    areas: dict[int, list[Json]] = field(default_factory=dict)
    #: Departments and functions by club id (flat, linked by ``parentId``).
    sub_areas: dict[int, list[Json]] = field(default_factory=dict)
    #: Custom field definitions by club id.
    individual_fields: dict[int, list[Json]] = field(default_factory=dict)
    #: Permission roles by club id.
    roles: dict[int, list[Json]] = field(default_factory=dict)
    #: Permission states by role id and permission key.
    role_permissions: dict[int, dict[str, int]] = field(default_factory=dict)
    #: Salutations, titles and contribution rates by club id.
    master: dict[int, Json] = field(default_factory=dict)
    #: Calendar events by club id and event id.
    events: dict[int, dict[int, Json]] = field(default_factory=dict)
    #: Calendar categories by club id.
    event_categories: dict[int, list[Json]] = field(default_factory=dict)
    #: Cash boxes and bank accounts by club id.
    bank_accounts: dict[int, list[Json]] = field(default_factory=dict)
    #: Bookings by club id and booking id.
    bookings: dict[int, dict[int, Json]] = field(default_factory=dict)
    #: Invoices, expenses and so on by club id.
    transactions: dict[int, list[Json]] = field(default_factory=dict)
    #: Folders and files by club id and entry id (a UUID).
    documents: dict[int, dict[str, Json]] = field(default_factory=dict)
    #: File contents by document id.
    document_files: dict[str, bytes] = field(default_factory=dict)
    #: Mailing drafts and templates by club id and id.
    dispatches: dict[int, dict[int, Json]] = field(default_factory=dict)
    #: Sent mailing items by club id (nothing is e-mailed).
    sent_items: dict[int, list[Json]] = field(default_factory=dict)
    #: Prepared report runs by process id.
    report_runs: dict[str, Json] = field(default_factory=dict)
    #: Club logos by club id.
    logos: dict[int, bytes] = field(default_factory=dict)
    #: Member ids that have a picture.
    pictures: dict[int, bytes] = field(default_factory=dict)
    #: Invitation e-mails the mock "sent", as ``(member id, e-mail address)``.
    sent_invitations: list[tuple[int, str]] = field(default_factory=list)
    #: Request paths the simulated firewall rejects with an HTML page.
    rejected_paths: set[str] = field(default_factory=set)
    #: Every API request the server received, as ``(method, path)``.
    requests: list[tuple[str, str]] = field(default_factory=list)
    #: The ``x-api-version`` header of each of those requests (``None`` if absent).
    api_versions: list[str | None] = field(default_factory=list)
    _next_id: int = 500_000

    @classmethod
    def demo(cls) -> MockState:
        """Return a state with one user and two clubs (a regular and a demo club)."""
        state = cls()
        user = MockUser(id=4711, email=DEMO_EMAIL, password=DEMO_PASSWORD)
        state.users[user.email] = user
        state.clubs[REGULAR_CLUB_ID] = _club(
            REGULAR_CLUB_ID, "Musterverein e.V.", is_demo=False, owner=user
        )
        state.clubs[DEMO_CLUB_ID] = _club(
            DEMO_CLUB_ID, "Demoverein", is_demo=True, owner=user
        )
        state.selected_club_id = DEMO_CLUB_ID
        for club_id in state.clubs:
            state.members[club_id] = {}
            state.areas[club_id] = seed.areas(club_id)
            state.sub_areas[club_id] = seed.sub_areas(club_id)
            state.individual_fields[club_id] = seed.individual_fields(club_id)
            state.roles[club_id] = seed.roles(club_id)
            for role in state.roles[club_id]:
                state.role_permissions[role["id"]] = seed.default_permissions(
                    role["type"]
                )
            state.master[club_id] = seed.master_data(club_id)
            state.event_categories[club_id] = seed.event_categories(club_id)
            state.events[club_id] = {}
            state.lists[club_id] = {
                item["id"]: item for item in seed.default_lists(club_id)
            }
            state.dispatches[club_id] = {}
            state.sent_items[club_id] = []
            state.documents[club_id] = {}
            for folder_id, name, system in seed.DOCUMENT_FOLDERS:
                state.documents[club_id][folder_id] = seed.folder(
                    folder_id, name, None, system=system
                )
            state.bank_accounts[club_id] = []
            state.bookings[club_id] = {}
            state.transactions[club_id] = []
        state.bank_accounts[DEMO_CLUB_ID] = seed.bank_accounts()
        state.transactions[DEMO_CLUB_ID] = seed.business_transactions()
        for booking_id, account, day, contact, purpose, amount in seed.DEMO_BOOKINGS:
            state.add_booking(
                DEMO_CLUB_ID, account, day, contact, purpose, amount, booking_id
            )
        for event in seed.DEMO_EVENTS:
            state.events[DEMO_CLUB_ID][event["id"]] = {
                "clubId": DEMO_CLUB_ID,
                **event,
            }
        for person in seed.DEMO_MEMBERS:
            state.add_member(DEMO_CLUB_ID, dict(person), seeded=True)
        for person in seed.REGULAR_MEMBERS:
            state.add_member(REGULAR_CLUB_ID, dict(person), seeded=True)
        state.lists[REGULAR_CLUB_ID][seed.LIST_BOARD]["_member_ids"] = [8001]
        state.pictures[7002] = b"\xff\xd8\xff\xe0mock-jpeg\xff\xd9"
        state.members[DEMO_CLUB_ID][7002]["pictureExists"] = True
        return state

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def issue_ticket(self, email: str) -> str:
        ticket = secrets.token_urlsafe(32)
        self.tickets[ticket] = email
        return ticket

    def issue_token(self, email: str) -> str:
        """Create a session token (shaped like a JWT, but meaningless)."""
        token = "mock." + secrets.token_urlsafe(24) + ".sig"
        self.tokens[token] = email
        return token

    def club_areas(self, club_id: int) -> list[Json]:
        """The department structure as the API sends it: levels with entries."""
        return [
            {
                **area,
                "subAreas": [
                    sub
                    for sub in self.sub_areas[club_id]
                    if sub["areaId"] == area["id"]
                ],
            }
            for area in self.areas[club_id]
        ]

    def master_data(self, club_id: int) -> Json:
        """Answer of ``GET .../data``."""
        return {
            **self.master[club_id],
            "clubAreas": self.club_areas(club_id),
            "individualFields": self.individual_fields[club_id],
        }

    def next_member_number(self, club_id: int) -> str:
        """The next free member number: highest numeric number plus one."""
        numbers = [
            int(member["memberId"])
            for member in self.members.get(club_id, {}).values()
            if str(member.get("memberId", "")).isdecimal()
        ]
        return str(max(numbers, default=0) + 1)

    def sync_membership(self, member: Json) -> None:
        """Normalize the membership periods and derive the member's status.

        On the real API the overall ``state`` and ``membershipEndAt`` follow
        from the periods ("histories"); setting them directly has no effect.
        """
        periods = member.get("histories") or []
        for period in periods:
            period.setdefault("id", self.next_id())
            period["clubMemberId"] = member["id"]
            period.setdefault("membershipEnd", None)
            period.setdefault("status", 0)
            period.setdefault("isHonoured", False)
            for key in ("membershipStart", "membershipEnd"):
                period[key] = seed.iso_day(period.get(key))
            period["isFormer"] = period["status"] == 1
        member["histories"] = periods
        if not periods:
            return
        statuses = {period["status"] for period in periods}
        member["state"] = 0 if 0 in statuses else 2 if 2 in statuses else 1
        member["isHonoured"] = any(
            period["isHonoured"] for period in periods if not period["isFormer"]
        )
        ends = [period["membershipEnd"] for period in periods]
        member["membershipEndAt"] = (
            max(ends) if member["state"] == 1 and all(ends) else None
        )

    def add_member(self, club_id: int, fields: Json, *, seeded: bool = False) -> Json:
        """Store a new member built from ``fields`` and return it.

        Missing fields get the defaults the real API was seen to apply. The
        keys ``_sub_area``, ``_custom`` and ``_roles`` are seed shortcuts for a
        department membership, custom field values and permission roles.
        """
        sub_area = fields.pop("_sub_area", None)
        custom = fields.pop("_custom", {})
        role_ids = fields.pop("_roles", [])
        member_id = int(fields.pop("id", 0)) or self.next_id()
        timestamp = now_iso()
        kind = int(fields.get("type", 1))
        email = fields.get("email") or ""
        member: Json = {
            "firstName": None,
            "gender": 2,
            "formOfAddressId": None,
            "titleId": None,
            "birthday": None,
            "maritalStatus": None,
            "id": member_id,
            "clubId": club_id,
            "originalClubMemberId": None,
            "userId": None,
            "memberId": self.next_member_number(club_id),
            "type": kind,
            "isPerson": 1,
            "lastName": "",
            "email": "",
            "additionalEmail": "",
            "phone": "",
            "phoneNotes": "",
            "phone2": "",
            "phone2Notes": "",
            "mobilePhone": "",
            "mobilePhoneNotes": "",
            "fax": "",
            "website": "",
            "address": {
                "addressLine1": "",
                "addressLine2": "",
                "zip": "",
                "city": "",
                "countryId": 2,
            },
            "membershipBeginAt": timestamp if kind == 1 else None,
            "membershipEndAt": None,
            "state": 0,
            "invitationState": 4,
            "isHonoured": False,
            "notifications": {
                "bySms": None,
                "byEmail": None,
                "byPost": None,
                "byPhone": None,
                "interval": None,
            },
            "bankConnections": [],
            "notes": None,
            "placeholderColor": "#26C6DA",
            "rateAmount": "0",
            "balance": "0",
            "pictureExists": False,
            "useUnionReport": True,
            "editedBy": None,
            "editedAtDate": timestamp,
            "blockedCommunication": False,
            "communicationChannel": 0 if email else 1,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "clubSubAreas": [],
            "paymentType": {
                "id": self.next_id(),
                "type": 1,
                "sepaMandateReference": None,
                "clubMemberId": member_id,
                "payerMemberId": None,
            },
            "formOfAddress": None,
            "title": None,
            "memberIndividualFieldData": [
                {
                    "clubId": club_id,
                    "clubMemberId": member_id,
                    "individualFieldId": field_id,
                    "values": values,
                }
                for field_id, values in custom.items()
            ],
            "clubMemberContributionRates": [],
            "clubMemberSepaMandates": [],
            "histories": [],
        }
        member.update(fields)
        for key in ("birthday", "membershipBeginAt", "membershipEndAt"):
            member[key] = seed.iso_day(member[key])
        if kind == 1 and seeded:
            # Seed members get one membership period; members created through
            # the API only have the periods the request contains.
            member["histories"] = [
                {
                    "isFormer": member["state"] == 1,
                    "id": self.next_id(),
                    "clubMemberId": member_id,
                    "subAreaId": sub_area,
                    "membershipStart": member["membershipBeginAt"],
                    "membershipEnd": member["membershipEndAt"],
                    "status": member["state"],
                    "isHonoured": False,
                    "autoGenerated": False,
                    "autoUpdated": False,
                }
            ]
        self.sync_membership(member)
        self.members.setdefault(club_id, {})[member_id] = member
        if role_ids:
            self.member_roles[member_id] = list(role_ids)
        return member

    def add_booking(
        self,
        club_id: int,
        account_id: int,
        day: str,
        contact: str,
        purpose: str,
        amount: float,
        booking_id: int | None = None,
    ) -> Json:
        """Store a booking and return it."""
        account = next(a for a in self.bank_accounts[club_id] if a["id"] == account_id)
        stamp = seed.iso_day(day[:10]).replace(".000Z", "Z")
        booking: Json = {
            "id": booking_id or self.next_id(),
            "bankAccountId": account_id,
            "bankAccountName": account["accountName"],
            "bankAccountType": account["accountType"],
            "bookingDate": stamp,
            "valutaDate": stamp,
            "bookingContactName": contact,
            "purposeDescription": purpose,
            "bookingAmount": amount,
            "assignmentState": "notAssigned",
            "isManually": False,
            "booked": True,
            "isInitialBalance": False,
            "bookingOpenAmount": amount,
        }
        self.bookings[club_id][booking["id"]] = booking
        self.sync_balances(club_id)
        return booking

    def sync_balances(self, club_id: int) -> None:
        """Recompute the account balances from the bookings."""
        for account in self.bank_accounts[club_id]:
            total = sum(
                booking["bookingAmount"]
                for booking in self.bookings[club_id].values()
                if booking["bankAccountId"] == account["id"]
            )
            account["accountBalance"] = account["calculatedBalance"] = round(total, 2)
