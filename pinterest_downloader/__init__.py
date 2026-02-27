from .pinterest import Pinterest
from .exceptions import (
    PinterestError,
    PinNotFoundError,
    UserNotFoundError,
    BoardNotFoundError,
    SearchError,
    InvalidURLError,
)

__version__ = "3.0.0"
__author__ = "Ahmed Nagm"
__all__ = [
    "Pinterest",
    "PinterestError",
    "PinNotFoundError",
    "UserNotFoundError",
    "BoardNotFoundError",
    "SearchError",
    "InvalidURLError",
]
