"""pymeinverein - async Python client for the (unofficial) WISO MeinVerein Web API."""

from importlib.metadata import PackageNotFoundError, version

from .api.mailing import SendingDisabledError
from .client import MeinVereinClient
from .exceptions import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    LoginThrottledError,
    LookupFailedError,
    MeinVereinError,
    NoAccountError,
    NotFoundError,
    PermissionDeniedError,
    RequestRejectedError,
    ServerError,
    TwoFactorRequiredError,
    UnexpectedResponseError,
)
from .filters import MemberFilter
from .models import (
    Account,
    Address,
    Club,
    DefaultListType,
    Gender,
    ListType,
    Member,
    MemberList,
    MemberState,
    MemberType,
    User,
)

try:
    __version__ = version("pymeinverein")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "Account",
    "Address",
    "ApiError",
    "AuthenticationError",
    "BadRequestError",
    "Club",
    "DefaultListType",
    "Gender",
    "ListType",
    "LoginThrottledError",
    "LookupFailedError",
    "MeinVereinClient",
    "MeinVereinError",
    "Member",
    "MemberFilter",
    "MemberList",
    "MemberState",
    "MemberType",
    "NoAccountError",
    "NotFoundError",
    "PermissionDeniedError",
    "RequestRejectedError",
    "SendingDisabledError",
    "ServerError",
    "TwoFactorRequiredError",
    "UnexpectedResponseError",
    "User",
    "__version__",
]
