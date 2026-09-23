from typing import Protocol


class BettingStartedNotifier(Protocol):
    async def notify(self, *, recipient_user_ids: tuple[int, ...]) -> None: ...
