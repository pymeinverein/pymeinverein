"""Models for members and contacts.

MeinVerein stores members, contacts and companies in one table and tells them
apart by ``type``. The API calls all of them "club members".

The integer codes of the enums below were taken from the web application.
Model fields keep the plain integers the API sends (so unknown future values
do not break parsing); compare them with the enums::

    if member.type == MemberType.CONTACT: ...
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import IntEnum
from typing import Any

from pydantic import Field, field_validator

from .base import ApiModel


class MemberType(IntEnum):
    """What kind of entry a "club member" is (field ``type``)."""

    MEMBER = 1
    CONTACT = 2
    COMPANY = 3


class MemberState(IntEnum):
    """Membership status (field ``state``)."""

    ACTIVE = 0
    FORMER = 1
    PASSIVE = 2


class Gender(IntEnum):
    MALE = 0
    FEMALE = 1
    NOT_SPECIFIED = 2
    DIVERSE = 3


class MaritalStatus(IntEnum):
    LIKE_MARRIAGE = 0
    PARTNERSHIP = 1
    DIVORCED = 2
    SEPARATED = 3
    SINGLE = 4
    MARRIED = 5
    WIDOWED = 6


class InvitationState(IntEnum):
    """State of the invitation to the member portal."""

    ACCEPTED = 0
    INVITED = 1
    REQUESTED = 2
    REVOKED = 3
    NOT_INVITED = 4
    REJECTED = 5


class PaymentMethod(IntEnum):
    """How a member pays (``paymentType.type``)."""

    SEPA_DEBIT = 0
    INVOICE = 1
    THIRD_PARTY = 2


class CommunicationChannel(IntEnum):
    EMAIL = 0
    LETTER = 1
    SETTINGS = 2


class Address(ApiModel):
    address_line1: str | None = None
    address_line2: str | None = None
    #: Postal code. The API sends it sometimes as number, sometimes as text.
    zip: str | None = None
    city: str | None = None
    country_id: int | None = None
    #: Country name; only present in some answers.
    country: str | None = None
    use_po_box: bool | None = Field(default=None, alias="usePOBox")


class SubArea(ApiModel):
    """A department or a function inside a department ("Abteilung", "Rolle")."""

    id: int
    name: str
    #: 1 = department, 2 and 3 = levels below it.
    level: int | None = None
    area_id: int | None = None
    parent_id: int | None = None
    alias: str | None = None


class MembershipHistory(ApiModel):
    """One membership period, optionally tied to a department."""

    id: int | None = None
    sub_area_id: int | None = None
    membership_start: datetime | None = None
    membership_end: datetime | None = None
    status: int | None = None
    is_former: bool | None = None
    is_honoured: bool | None = None


@dataclass(frozen=True)
class MembershipPeriod:
    """A membership period to set with ``MembersAPI.set_memberships``.

    Unlike :class:`MembershipHistory` (what the API sends back) this describes
    the complete wanted state of one period: ``end=None`` means the period is
    open, and an existing end date is removed.
    """

    #: Department or function: id, unique name, ``"Department/Function"`` path
    #: or :class:`SubArea`; ``None`` means the club as a whole.
    department: int | str | SubArea | None
    start: date
    end: date | None = None
    #: Default: ``FORMER`` if the period ended before today, else ``ACTIVE``.
    status: MemberState | None = None
    honoured: bool = False

    def effective_status(self, today: date | None = None) -> MemberState:
        """The status sent to the API: ``status`` or the default described there."""
        if self.status is not None:
            return self.status
        if self.end is not None and self.end < (today or date.today()):
            return MemberState.FORMER
        return MemberState.ACTIVE


class IndividualFieldValue(ApiModel):
    """Value(s) of a custom field ("individuelles Feld") for one member.

    A multiple choice field stores ``null`` for values that are not among its
    options; those are left out here.
    """

    individual_field_id: int
    values: list[str] = []

    @field_validator("values", mode="before")
    @classmethod
    def _drop_nulls(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [item for item in value if item is not None]
        return value


class RoleRef(ApiModel):
    id: int
    name: str


class PaymentType(ApiModel):
    id: int | None = None
    #: See :class:`PaymentMethod`.
    type: int | None = None
    sepa_mandate_reference: str | None = None
    payer_member_id: int | None = None


class Member(ApiModel):
    """A member, contact or company of a club.

    The same model is used for the detail answer and for list rows. List rows
    carry resolved departments (``club_sub_areas``) and roles; the detail
    answer carries the membership ``histories`` instead.
    """

    id: int
    club_id: int | None = None
    #: The member number shown in MeinVerein (text, not the database id).
    member_id: str | None = None
    #: See :class:`MemberType`.
    type: int | None = None
    is_person: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    #: See :class:`Gender`.
    gender: int | None = None
    birthday: datetime | None = None
    #: See :class:`MaritalStatus`.
    marital_status: int | None = None
    form_of_address_id: int | None = None
    title_id: int | None = None

    email: str | None = None
    additional_email: str | None = None
    phone: str | None = None
    phone_notes: str | None = None
    phone2: str | None = None
    phone2_notes: str | None = None
    mobile_phone: str | None = None
    mobile_phone_notes: str | None = None
    fax: str | None = None
    website: str | None = None
    address: Address | None = None

    membership_begin_at: datetime | None = None
    membership_end_at: datetime | None = None
    #: See :class:`MemberState`.
    state: int | None = None
    is_honoured: bool | None = None
    #: See :class:`InvitationState`.
    invitation_state: int | None = None
    invited_at: datetime | None = None
    #: Id of the MeinVerein user account linked to this member, if any.
    user_id: int | None = None

    notes: str | None = None
    #: See :class:`CommunicationChannel`.
    communication_channel: int | None = None
    blocked_communication: bool | None = None
    picture_exists: bool | None = None
    payment_type: PaymentType | None = None

    #: The member's contributions, as the API sends them (shape differs
    #: between the detail answer and list rows).
    club_member_contribution_rates: list[dict[str, Any]] = []
    club_sub_areas: list[SubArea] = []
    histories: list[MembershipHistory] = []
    roles: list[RoleRef] = []
    #: Custom field values as sent in list rows.
    individual_field_data: list[IndividualFieldValue] | None = None
    #: Custom field values as sent in the detail answer.
    member_individual_field_data: list[IndividualFieldValue] | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def full_name(self) -> str:
        """First and last name, or just the name for companies."""
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    @property
    def is_member(self) -> bool:
        return self.type == MemberType.MEMBER

    @property
    def is_contact(self) -> bool:
        """``True`` for contacts and companies (everything that is no member)."""
        return self.type in (MemberType.CONTACT, MemberType.COMPANY)

    @property
    def is_active(self) -> bool:
        return self.state == MemberState.ACTIVE

    @property
    def departments(self) -> list[str]:
        """Names of the member's departments (level 1 sub areas).

        Only filled for list rows; the detail answer has no department names.
        A department is listed once even if the member has several functions
        in it (the API repeats the department for every function).
        """
        names = [area.name for area in self.club_sub_areas if area.level == 1]
        return list(dict.fromkeys(names))

    @property
    def custom_values(self) -> dict[int, list[str]]:
        """Custom field values by field id, from whichever form the API sent."""
        source = self.individual_field_data or self.member_individual_field_data or []
        return {item.individual_field_id: item.values for item in source}

    def to_record(self) -> dict[str, Any]:
        """Return a plain dict with API field names and Python values."""
        return self.model_dump(mode="python", by_alias=True)


class DeleteResult(ApiModel):
    """Answer of the bulk delete call.

    Note that the API counts ids that do not exist as "deleted".
    """

    deleted_count: int = 0
    skipped_count: int = 0


class BulkSkip(ApiModel):
    """A member a bulk call left untouched, with the API's reason code."""

    club_member_id: int
    #: For example ``NO_SEPA_MANDATE`` or ``NOT_A_CLUB_MEMBER``.
    reason: str | None = None


class BulkResult(ApiModel):
    """Answer of the bulk edit calls: which members were skipped and why."""

    skips: list[BulkSkip] = []
    skipped_club_member_ids: list[int] = []

    @property
    def ok(self) -> bool:
        """``True`` if no member was skipped."""
        return not self.skipped_club_member_ids


class InviteResult(ApiModel):
    """Answer of the invitation call: how many members were (not) invited."""

    invited: int = 0
    not_invited: int = 0
