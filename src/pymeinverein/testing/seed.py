"""Invented sample data for the mock server.

Nothing here comes from a real club. The data only follows the *shape* of the
real API answers: a club with two departments, a few active and former
members, contacts, custom fields, roles and the default lists.
"""

from __future__ import annotations

from typing import Any

type Json = dict[str, Any]

DAY_SUFFIX = "T00:00:00.000Z"
CREATED = "2026-01-05T09:00:00.000Z"

# Departments (level 1) and the function "Spieler" below each (level 2).
AREA_TEAMS = 301
AREA_FUNCTIONS = 302
AREA_LEVEL_3 = 303
DEPARTMENT_WOMEN = 2001
DEPARTMENT_MEN = 2002
PLAYERS_WOMEN = 2011
PLAYERS_MEN = 2012

FIELD_ELIGIBLE = 3001
FIELD_POSITION = 3002

ROLE_ADMIN = 4001
ROLE_FINANCE = 4002
ROLE_MANAGER = 4003
ROLE_MEMBER = 4004

LIST_BIRTHDAYS = 5001
LIST_ANNIVERSARIES = 5002
LIST_EVERYONE = 5003
LIST_ACTIVE = 5004
LIST_ALL_MEMBERS = 5005
LIST_FORMER = 5006
LIST_WOMEN = 5007
LIST_MEN = 5008
LIST_BOARD = 5009
LIST_NOT_FORMER = 5010

COUNTRIES: list[Json] = [
    {
        "id": 2,
        "name": "Deutschland",
        "code": "D",
        "iso3166Code": "DE",
        "phoneCode": "49",
    },
    {
        "id": 3,
        "name": "Österreich",
        "code": "A",
        "iso3166Code": "AT",
        "phoneCode": "43",
    },
    {"id": 4, "name": "Schweiz", "code": "CH", "iso3166Code": "CH", "phoneCode": "41"},
]


def sub_areas(club_id: int) -> list[Json]:
    def sub(
        sub_id: int, area_id: int, name: str, level: int, parent: int | None
    ) -> Json:
        return {
            "id": sub_id,
            "clubId": club_id,
            "areaId": area_id,
            "name": name,
            "level": level,
            "alias": None,
            "parentId": parent,
        }

    return [
        sub(DEPARTMENT_WOMEN, AREA_TEAMS, "1. Mannschaft - Damen", 1, None),
        sub(DEPARTMENT_MEN, AREA_TEAMS, "1. Mannschaft - Herren", 1, None),
        sub(PLAYERS_WOMEN, AREA_FUNCTIONS, "Spieler", 2, DEPARTMENT_WOMEN),
        sub(PLAYERS_MEN, AREA_FUNCTIONS, "Spieler", 2, DEPARTMENT_MEN),
    ]


def areas(club_id: int) -> list[Json]:
    """The three levels of the department structure (without their entries)."""

    def level(area_id: int, name: str, number: int) -> Json:
        return {
            "id": area_id,
            "clubId": club_id,
            "name": name,
            "type": 0,
            "level": number,
        }

    return [
        level(AREA_TEAMS, "Mannschaften", 1),
        level(AREA_FUNCTIONS, "Rollen", 2),
        level(AREA_LEVEL_3, "Ebene 3", 3),
    ]


def individual_fields(club_id: int) -> list[Json]:
    def field(field_id: int, name: str, kind: int, options: list[str]) -> Json:
        return {
            "id": field_id,
            "clubId": club_id,
            "listId": None,
            "area": 0,
            "name": name,
            "type": kind,
            "options": options,
            "suffix": None,
        }

    return [
        field(FIELD_ELIGIBLE, "Spielberechtigt", 5, []),
        field(FIELD_POSITION, "Position", 1, ["Tor", "Abwehr", "Mittelfeld", "Sturm"]),
    ]


def roles(club_id: int) -> list[Json]:
    def role(role_id: int, name: str, kind: int, text: str) -> Json:
        return {
            "id": role_id,
            "clubId": club_id,
            "name": name,
            "description": text,
            "type": kind,
            "isSystemRole": True,
            "posIndex": kind,
            "isDefault": kind == 4,
            "memberCount": 0,
            "createdAt": CREATED,
            "updatedAt": CREATED,
        }

    return [
        role(ROLE_ADMIN, "Administrator", 1, "Alle Rechte."),
        role(ROLE_FINANCE, "Finanzverwalter", 2, "Zugriff auf Zahlungen."),
        role(ROLE_MANAGER, "Verwalter", 3, "Verwaltung von Mitgliedern."),
        role(ROLE_MEMBER, "Mitglied", 4, "Zugriff auf das eigene Profil."),
    ]


def master_data(club_id: int) -> Json:
    """Salutations, titles and rates; areas and fields are added by the state."""

    def salutation(sid: int, label: str, gender: int) -> Json:
        return {
            "id": sid,
            "clubId": club_id,
            "label": label,
            "isDefault": True,
            "gender": gender,
            "address": "" if gender == 2 else label,
            "personalLetterSalutation": "<p>Hallo,</p>",
            "formalLetterSalutation": "<p>Sehr geehrte Damen und Herren,</p>",
        }

    return {
        "formOfAddresses": [
            salutation(6001, "keine Angabe", 2),
            salutation(6002, "Frau", 1),
            salutation(6003, "Herr", 0),
        ],
        "titles": [
            {
                "id": 6101,
                "clubId": club_id,
                "label": "Dr.",
                "isDefault": True,
                "isFavorite": False,
            },
            {
                "id": 6102,
                "clubId": club_id,
                "label": "Prof.",
                "isDefault": True,
                "isFavorite": False,
            },
        ],
        "clubContributionRates": [
            {
                "id": 6201,
                "clubId": club_id,
                "name": "Mitgliedsbeitrag",
                "amount": "120.00",
                "interval": 3,
                "type": 0,
            }
        ],
        "clubLetterSalutationType": {"letterSalutationType": 1},
    }


def default_lists(club_id: int) -> list[Json]:
    """The lists MeinVerein creates for every club, plus one user list.

    Keys starting with ``_`` are internal to the mock and never sent.
    """

    def entry(
        list_id: int,
        name: str,
        list_type: int,
        default_type: int | None,
        *,
        criteria: list[tuple[str, str]] | None = None,
        department: int | None = None,
        members: list[int] | None = None,
    ) -> Json:
        return {
            "id": list_id,
            "departmentId": department,
            "name": name,
            "listType": list_type,
            "isDefaultList": default_type is not None,
            "defaultListType": default_type,
            "isFavourite": False,
            "clubId": club_id,
            "createdAt": CREATED,
            "updatedAt": CREATED,
            "_criteria": [
                {
                    "id": list_id * 10 + index,
                    "columnName": column,
                    "operator": "=",
                    "value": value,
                }
                for index, (column, value) in enumerate(criteria or [])
            ],
            "_field_criteria": [],
            "_member_ids": members or [],
        }

    return [
        entry(LIST_BIRTHDAYS, "Geburtstage", 1, 1, criteria=[("type", "1")]),
        entry(LIST_ANNIVERSARIES, "Jubiläumsliste", 1, 2, criteria=[("type", "1")]),
        entry(LIST_EVERYONE, "Alle Kontakte", 1, 5),
        entry(
            LIST_ACTIVE,
            "Aktuelle Mitglieder",
            1,
            4,
            criteria=[("type", "1"), ("state", "0")],
        ),
        entry(LIST_ALL_MEMBERS, "Alle Mitglieder", 1, 6, criteria=[("type", "1")]),
        entry(
            LIST_FORMER,
            "Ehemalige Mitglieder",
            1,
            8,
            criteria=[("type", "1"), ("state", "1")],
        ),
        # The real service appends a space to the names of department lists.
        entry(
            LIST_WOMEN,
            "Abteilung 1. Mannschaft - Damen ",
            0,
            3,
            department=DEPARTMENT_WOMEN,
        ),
        entry(
            LIST_MEN,
            "Abteilung 1. Mannschaft - Herren ",
            0,
            3,
            department=DEPARTMENT_MEN,
        ),
        entry(LIST_BOARD, "Vorstand", 0, None, members=[7001, 7002]),
        # Like on the real service: two rules on one column mean "either".
        entry(
            LIST_NOT_FORMER,
            "Aktive und Passive",
            1,
            None,
            criteria=[("type", "1"), ("state", "0"), ("state", "2")],
        ),
    ]


#: Sample people of the demo club: keyword arguments for ``MockState.add_member``.
DEMO_MEMBERS: list[Json] = [
    {
        "id": 7001,
        "firstName": "Demo",
        "lastName": "User",
        "email": "demo@example.org",
        "userId": 4711,
        "_roles": [ROLE_ADMIN],
    },
    {
        "id": 7002,
        "firstName": "Erika",
        "lastName": "Beispiel",
        "gender": 1,
        "birthday": "1988-04-12",
        "email": "erika.beispiel@example.org",
        "phone": "030 1234567",
        "mobilePhone": "0170 1234567",
        "address": {
            "addressLine1": "Musterweg 1",
            "addressLine2": "",
            "zip": "10115",
            "city": "Berlin",
            "countryId": 2,
        },
        "membershipBeginAt": "2015-03-01",
        "_sub_area": PLAYERS_WOMEN,
        "_custom": {FIELD_ELIGIBLE: ["true"], FIELD_POSITION: ["Tor"]},
        "userId": 4712,
        "_roles": [ROLE_FINANCE],
    },
    {
        "id": 7003,
        "firstName": "Max",
        "lastName": "Muster",
        "gender": 0,
        "birthday": "1992-11-30",
        "email": "max.muster@example.org",
        "address": {
            "addressLine1": "Beispielstraße 22",
            "addressLine2": "",
            "zip": "20095",
            "city": "Hamburg",
            "countryId": 2,
        },
        "membershipBeginAt": "2018-08-15",
        "_sub_area": PLAYERS_MEN,
        "_custom": {FIELD_ELIGIBLE: ["true"], FIELD_POSITION: ["Sturm"]},
        "userId": 4713,
        "_roles": [ROLE_MEMBER],
    },
    {
        "id": 7004,
        "firstName": "Lena",
        "lastName": "Probe",
        "gender": 1,
        "birthday": "2001-06-05",
        "email": "lena.probe@example.org",
        "membershipBeginAt": "2021-01-10",
        "_sub_area": PLAYERS_WOMEN,
        "_custom": {FIELD_POSITION: ["Abwehr"]},
    },
    {
        "id": 7005,
        "firstName": "Jonas",
        "lastName": "Test",
        "gender": 0,
        "birthday": "1975-02-20",
        "email": "",
        "phone": "040 7654321",
        "membershipBeginAt": "2010-05-01",
        "_sub_area": PLAYERS_MEN,
    },
    {
        "id": 7006,
        "firstName": "Greta",
        "lastName": "Vorlage",
        "gender": 1,
        "email": "greta.vorlage@example.org",
        "membershipBeginAt": "2012-02-01",
        "membershipEndAt": "2024-12-31",
        "state": 1,
    },
    {
        "id": 7007,
        "firstName": "Paul",
        "lastName": "Entwurf",
        "gender": 0,
        "email": "paul.entwurf@example.org",
        "membershipBeginAt": "2009-09-01",
        "membershipEndAt": "2023-06-30",
        "state": 1,
    },
    {
        "id": 7008,
        "firstName": "Nora",
        "lastName": "Skizze",
        "gender": 3,
        "email": "nora.skizze@example.org",
        "membershipBeginAt": "2019-04-01",
        "state": 2,
    },
    {
        "id": 7009,
        "firstName": "Hans",
        "lastName": "Kontakt",
        "type": 2,
        "email": "hans.kontakt@example.org",
        "membershipBeginAt": None,
    },
    {
        "id": 7010,
        "firstName": None,
        "lastName": "Sporthaus Beispiel GmbH",
        "type": 2,
        "isPerson": 0,
        "email": "info@sporthaus.example",
        "membershipBeginAt": None,
    },
]

#: Sample people of the regular (non-demo) club.
REGULAR_MEMBERS: list[Json] = [
    {
        "id": 8001,
        "firstName": "Demo",
        "lastName": "User",
        "email": "demo@example.org",
        "userId": 4711,
    },
    {
        "id": 8002,
        "firstName": "Clara",
        "lastName": "Echt",
        "email": "clara.echt@example.org",
        "membershipBeginAt": "2020-01-01",
    },
]


def iso_day(value: Any) -> Any:
    """Expand ``YYYY-MM-DD`` to the timestamp format the API stores."""
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" == value[7]:
        return value + DAY_SUFFIX
    return value


#: A small permission tree: containers with the permissions below them.
PERMISSION_TREE: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "dynamic_list_member_container",
        "Mitglieder",
        [
            ("member_list_name_all_members", "Alle Mitglieder"),
            ("member_list_name_former_members", "Ehemalige Mitglieder"),
        ],
    ),
    (
        "calendar_container",
        "Kalender",
        [("calendar_events_module", "Termine")],
    ),
    (
        "finance_container",
        "Finanzen",
        [("finance_invoices_module", "Rechnungen")],
    ),
]


def default_permissions(role_type: int) -> dict[str, int]:
    """Permission states a role of the given type starts with."""
    keys = [key for _, _, children in PERMISSION_TREE for key, _ in children]
    if role_type == 1:  # administrator: everything
        return dict.fromkeys(keys, 3)
    if role_type == 2:  # finance manager
        return {key: 3 if key.startswith("finance") else 0 for key in keys}
    if role_type == 3:  # manager
        return {key: 0 if key.startswith("finance") else 3 for key in keys}
    if role_type == 4:  # member
        return {key: 1 if key.startswith("calendar") else 0 for key in keys}
    return dict.fromkeys(keys, 0)  # custom roles start locked


CLUB_CATEGORIES: list[Json] = [
    {
        "id": 14,
        "name": "Sportverein",
        "children": [
            {"id": 15, "name": "Fußball", "children": None},
            {"id": 16, "name": "Golf", "children": None},
        ],
    },
    {"id": 30, "name": "Kulturverein", "children": None},
]


CATEGORY_CUSTOM = 9101
CATEGORY_DEFAULT = 9102
CATEGORY_BIRTHDAY = 9103


def event_categories(club_id: int) -> list[Json]:
    def category(category_id: int, name: str, color: str, kind: str) -> Json:
        return {
            "id": category_id,
            "clubId": club_id,
            "name": name,
            "color": color,
            "type": kind,
            "checked": True,
        }

    return [
        category(CATEGORY_CUSTOM, "Training", "#e33232", "custom"),
        category(CATEGORY_DEFAULT, "Standard", "#fa7d19", "default"),
        category(
            CATEGORY_BIRTHDAY, "Aktive/ Passive Mitglieder", "#5c5bce", "birthday"
        ),
    ]


def _event(event_id: int, title: str, start: str, end: str, category: int) -> Json:
    return {
        "id": event_id,
        "title": title,
        "startDate": start,
        "endDate": end,
        "fullDay": False,
        "description": "Vereinsheim",
        "notes": None,
        "categoryId": category,
        "isRecurringEvent": False,
        "recType": None,
        "participants": [],
        "createdAt": CREATED,
        "updatedAt": CREATED,
    }


DEMO_EVENTS: list[Json] = [
    _event(
        9201,
        "Vorstandssitzung",
        "2026-11-14T18:00:00.000Z",
        "2026-11-14T20:00:00.000Z",
        CATEGORY_DEFAULT,
    ),
    _event(
        9202,
        "Training Damen",
        "2026-11-17T17:00:00.000Z",
        "2026-11-17T18:30:00.000Z",
        CATEGORY_CUSTOM,
    ),
    _event(
        9203,
        "Weihnachtsfeier",
        "2026-12-19T18:00:00.000Z",
        "2026-12-19T23:00:00.000Z",
        CATEGORY_DEFAULT,
    ),
]


ACCOUNT_CASH = 9301
ACCOUNT_BANK = 9302


def bank_accounts() -> list[Json]:
    def account(account_id: int, name: str, kind: str, iban: str | None) -> Json:
        return {
            "id": account_id,
            "contactId": 0,
            "accountName": name,
            "accountCurrency": "EUR",
            "accountHolder": None,
            "accountBalance": 0,
            "accountBalanceDate": CREATED,
            "accountIban": iban,
            "bicCode": None,
            "bankCode": None,
            "accountType": kind,
            "accountActive": True,
            "bankName": None,
            "hasBookings": True,
            "calculatedBalance": 0,
            "hasDeviation": False,
        }

    return [
        account(ACCOUNT_CASH, "Kasse", "cash", None),
        account(
            ACCOUNT_BANK, "Vereinskonto", "offlineBankAccount", "DE02100500000054540402"
        ),
    ]


#: Bookings as ``(id, account, date, contact, purpose, amount)``.
DEMO_BOOKINGS: list[tuple[int, int, str, str, str, float]] = [
    (9401, ACCOUNT_CASH, "2026-10-01", "", "Anfangsbestand", 200.0),
    (9402, ACCOUNT_CASH, "2026-10-12", "Erika Beispiel", "Getränkeverkauf", 85.5),
    (9403, ACCOUNT_CASH, "2026-10-20", "Sporthaus Beispiel GmbH", "Bälle", -49.9),
    (9404, ACCOUNT_BANK, "2026-10-05", "Max Muster", "Mitgliedsbeitrag", 120.0),
]


def business_transactions() -> list[Json]:
    def entry(
        number: int, kind: str, state: str, receiver: str, gross: float, open_: float
    ) -> Json:
        return {
            "id": 9500 + number,
            "unifiedId": f"INV_{9500 + number}",
            "type": kind,
            "state": state,
            "closingState": "closed",
            "number": f"2026{number:06d}",
            "date": "2026-10-05T00:00:00.000Z",
            "receiver": receiver,
            "receiverId": "7003",
            "totalGross": gross,
            "paymentOpenAmount": open_,
            "paymentPaidAmount": gross - open_,
            "paymentDueDate": None,
            "notes": "",
            "positions": [],
        }

    return [
        entry(1, "invoice", "Paid", "Max Muster", 120.0, 0.0),
        entry(2, "invoice", "Open", "Lena Probe", 120.0, 120.0),
        entry(3, "expense", "Paid", "Sporthaus Beispiel GmbH", -49.9, 0.0),
    ]


FOLDER_SYSTEM = "00000000-0000-4000-8000-000000000001"
FOLDER_GENERAL = "00000000-0000-4000-8000-000000000002"
#: Top level folders every club starts with: ``(id, name, is system folder)``.
DOCUMENT_FOLDERS: list[tuple[str, str, bool]] = [
    (FOLDER_SYSTEM, "Systemordner", True),
    (FOLDER_GENERAL, "Allgemeines", False),
]


def folder(
    folder_id: str, name: str, parent: str | None, *, system: bool = False
) -> Json:
    return {
        "id": folder_id,
        "name": name,
        "parentId": parent,
        "type": "directory",
        "documentType": "directory",
        "size": 0,
        "isSystem": system,
        "updatedAt": CREATED,
        "updatedBy": {"userId": None, "fullName": ""},
    }


def _range(name: str) -> Json:
    return {"name": name, "type": "date-range", "validators": {"required": True}}


def _dropdown(name: str, options: list[str], default: str) -> Json:
    return {
        "name": name,
        "type": "dropdown",
        "options": options,
        "defaultValue": default,
    }


REPORTS: list[Json] = [
    {
        "id": "report-income-expense",
        "categories": [1],
        "fields": [
            _range("date"),
            _dropdown("observationPeriod", ["weekly", "monthly", "yearly"], "monthly"),
            _dropdown("layoutStyle", ["tabular", "visual"], "tabular"),
        ],
        "exportTypes": ["excel", "pdf"],
        "defaultExportType": "excel",
    },
    {
        "id": "report-member-association-a",
        "categories": [2],
        "fields": [
            {"name": "cutOffDate", "type": "date", "validators": {"required": True}},
            {"name": "memberState", "type": "checkbox-multi-select", "options": [0, 2]},
        ],
        "exportTypes": ["csv", "excel", "xml"],
        "defaultExportType": "csv",
    },
]
