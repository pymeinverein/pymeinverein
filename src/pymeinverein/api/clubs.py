"""Access to the clubs of the logged-in user."""

from __future__ import annotations

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.account import Club
from .account import AccountAPI
from .contributions import ContributionsAPI
from .custom_fields import CustomFieldsAPI
from .dashboard import DashboardAPI
from .departments import DepartmentsAPI
from .documents import DocumentsAPI
from .events import EventsAPI
from .finance import FinanceAPI
from .lists import ListsAPI
from .mailing import MailingAPI
from .masterdata import MasterDataAPI
from .members import MembersAPI
from .reports import ReportsAPI
from .roles import RolesAPI
from .settings import ClubSettingsAPI


class ClubClient:
    """All calls that belong to one club.

    Obtain an instance through :meth:`ClubsAPI.get`.
    """

    def __init__(self, transport: Transport, info: Club) -> None:
        self._transport = transport
        #: The club data as returned when the club was looked up.
        self.info = info
        #: Salutations, titles, departments, custom fields, roles.
        self.master_data = MasterDataAPI(transport, info.id)
        #: Departments and the functions inside them.
        self.departments = DepartmentsAPI(transport, info.id, self.master_data)
        #: Definitions of custom fields.
        self.custom_fields = CustomFieldsAPI(transport, info.id, self.master_data)
        #: Permission roles and who holds them.
        self.roles = RolesAPI(transport, info.id)
        #: Club details, logo, salutations, titles, numbering.
        self.settings = ClubSettingsAPI(transport, info.id)
        #: Contribution rates and their assignment to members.
        self.contributions = ContributionsAPI(transport, info.id)
        #: Calendar events and their categories.
        self.events = EventsAPI(transport, info.id)
        #: Accounts, bookings and business transactions (mostly read-only).
        self.finance = FinanceAPI(transport, info.id)
        #: Dashboard statistics.
        self.dashboard = DashboardAPI(transport, info.id)
        #: Folders and files.
        self.documents = DocumentsAPI(transport, info.id)
        #: Mailing templates, drafts, sent items and sending.
        self.mailing = MailingAPI(transport, info.id)
        #: Reports (income and expenses, receipts, member association report).
        self.reports = ReportsAPI(transport, info.id)
        #: Member lists.
        self.lists = ListsAPI(transport, info.id, self.master_data)
        #: Members and contacts.
        self.members = MembersAPI(transport, info.id, self.lists, self.master_data)

    @property
    def id(self) -> int:
        return self.info.id

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def is_demo(self) -> bool:
        return self.info.is_demo

    def __repr__(self) -> str:
        return f"<ClubClient id={self.id} name={self.name!r}>"

    async def select(self) -> None:
        """Mark this club as the one that is selected in the web application.

        The API itself does not need a selected club - every call names the club
        explicitly - so this only changes what the web application opens next.
        ``POST /protected/mv365/clubs/{clubId}/selected``
        """
        await self._transport.post(f"/protected/mv365/clubs/{self.id}/selected")


class ClubsAPI:
    """Lists the clubs of the logged-in user and opens a client for one of them."""

    def __init__(self, transport: Transport, account: AccountAPI) -> None:
        self._transport = transport
        self._account = account

    async def list(self) -> list[Club]:
        """Return all clubs the logged-in user can access."""
        return (await self._account.get()).clubs

    async def get(
        self, club_id: int | None = None, *, name: str | None = None
    ) -> ClubClient:
        """Return a client for one club, chosen by id or by exact name.

        Without arguments the club that is selected in the web application is
        used; if none is selected and the user has exactly one club, that one.
        """
        account = await self._account.get()
        clubs = account.clubs
        if club_id is not None:
            matches = [club for club in clubs if club.id == club_id]
            wanted = f"id {club_id}"
        elif name is not None:
            matches = [club for club in clubs if club.name == name]
            wanted = f"name {name!r}"
        elif account.selected_club_id is not None:
            matches = [club for club in clubs if club.id == account.selected_club_id]
            wanted = "the selected club"
        else:
            matches = clubs
            wanted = "a default club"
        if len(matches) != 1:
            available = ", ".join(f"{club.name!r} ({club.id})" for club in clubs)
            raise LookupFailedError(
                f"Expected exactly one club for {wanted}, found {len(matches)}. "
                f"Available clubs: {available or 'none'}"
            )
        return ClubClient(self._transport, matches[0])
