"""Club scoped routes of the mock server, one module per area of the API."""

from __future__ import annotations

from aiohttp import web

from ..state import MockState
from ._base import RouteGroup
from .bulk import BulkRoutes
from .contributions import ContributionRoutes
from .departments import DepartmentRoutes
from .documents import DocumentRoutes
from .events import EventRoutes
from .finance import FinanceRoutes
from .invitations import InvitationRoutes
from .lists import ListRoutes
from .mailing import MailingRoutes
from .masterdata import MasterDataRoutes
from .members import MemberRoutes
from .reports import ReportRoutes
from .roles import RoleRoutes
from .settings import SettingsRoutes

#: Order matters where paths overlap: the first matching route wins.
GROUPS: tuple[type[RouteGroup], ...] = (
    SettingsRoutes,
    MasterDataRoutes,
    RoleRoutes,
    ReportRoutes,
    DepartmentRoutes,
    DocumentRoutes,
    EventRoutes,
    FinanceRoutes,
    ContributionRoutes,
    BulkRoutes,
    InvitationRoutes,
    MemberRoutes,
    ListRoutes,
    MailingRoutes,
)


class ClubRoutes:
    """Registers every route group on a router."""

    def __init__(self, state: MockState) -> None:
        self.state = state

    def register(self, router: web.UrlDispatcher) -> None:
        for group in GROUPS:
            group(self.state).register(router)
