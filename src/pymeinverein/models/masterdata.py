"""Models for a club's master data: salutations, titles, departments, fields."""

from __future__ import annotations

from enum import IntEnum

from .base import ApiModel
from .member import SubArea
from .roles import ClubRole


class IndividualFieldType(IntEnum):
    """Data type of a custom field (field ``type``)."""

    TEXT = 0
    SELECT = 1
    MULTISELECT = 2
    DATE = 3
    NUMBER = 4
    BOOLEAN = 5
    PERSON = 6


class FormOfAddress(ApiModel):
    """A salutation ("Anrede") such as "Frau" or "Herr"."""

    id: int
    label: str
    gender: int | None = None
    is_default: bool | None = None
    #: The form used in an address block, e.g. "Herrn".
    address: str | None = None
    #: HTML templates for the opening line of letters.
    personal_letter_salutation: str | None = None
    formal_letter_salutation: str | None = None


class Title(ApiModel):
    """An academic or other title such as "Dr."."""

    id: int
    label: str
    is_default: bool | None = None
    is_favorite: bool | None = None


class ClubArea(ApiModel):
    """A level of the department structure with its entries."""

    id: int
    name: str
    level: int | None = None
    sub_areas: list[SubArea] = []


class RateInterval(IntEnum):
    """How often a contribution is due (field ``interval``)."""

    MONTHLY = 0
    QUARTERLY = 1
    HALF_YEARLY = 2
    YEARLY = 3
    ONCE = 4


class RateType(IntEnum):
    """Kind of contribution rate (field ``type``)."""

    REGULAR = 0
    DEPENDS_ON_AGE = 1
    DEPENDS_ON_MEMBERSHIP_DURATION = 2
    ADDITIONAL = 3
    DONATION = 4


class ContributionRate(ApiModel):
    """A membership fee definition ("Beitragssatz")."""

    id: int
    name: str
    #: Amount as decimal text, e.g. ``"120.00"``.
    amount: str | None = None
    #: See :class:`RateInterval`.
    interval: int | None = None
    #: See :class:`RateType`.
    type: int | None = None
    vat_percent: float | None = None
    is_negative: bool | None = None
    #: Text template for the invoice line.
    invoice_text: str | None = None
    billing_period: str | None = None


class IndividualField(ApiModel):
    """Definition of a custom field ("individuelles Feld")."""

    id: int
    name: str
    #: See :class:`IndividualFieldType`.
    type: int | None = None
    options: list[str] = []
    suffix: str | None = None
    #: Set when the field belongs to one list only.
    list_id: int | None = None


class MasterData(ApiModel):
    """Answer of ``GET /protected/mv365/clubs/{clubId}/data``."""

    form_of_addresses: list[FormOfAddress] = []
    titles: list[Title] = []
    club_areas: list[ClubArea] = []
    club_contribution_rates: list[ContributionRate] = []
    individual_fields: list[IndividualField] = []

    @property
    def sub_areas(self) -> list[SubArea]:
        """All departments and functions of all levels as one flat list."""
        return [sub for area in self.club_areas for sub in area.sub_areas]


class Country(ApiModel):
    id: int
    name: str
    #: Vehicle registration style code, e.g. ``D``.
    code: str | None = None
    iso3166_code: str | None = None
    phone_code: str | None = None


__all__ = [
    "ClubArea",
    "ClubRole",
    "ContributionRate",
    "Country",
    "FormOfAddress",
    "IndividualField",
    "IndividualFieldType",
    "MasterData",
    "RateInterval",
    "RateType",
    "Title",
]
