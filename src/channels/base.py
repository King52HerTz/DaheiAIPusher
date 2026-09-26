"""Push channel abstractions shared by every destination."""

from __future__ import annotations

from typing import Protocol

from ..feed import FeedItem


class PushError(RuntimeError):
    """Raised when a push channel does not accept a message."""


class PushChannel(Protocol):
    """A destination that can deliver one feed item as a notification.

    Concrete channels live next to this file and expose:
    - ``name``: identifier, also the per-channel state cursor key;
    - ``from_env``: classmethod building the channel from environment variables,
      validating its own configuration (only called when the channel is about
      to be used, so DRY_RUN / baseline runs need no credentials);
    - ``send``: deliver one feed item; raise ``PushError`` (config problems may
      raise ``ValueError``) on failure. The caller records the per-channel
      cursor only after ``send`` succeeds.
    """

    name: str

    def send(self, item: FeedItem, *, content_mode: str) -> None:
        ...
