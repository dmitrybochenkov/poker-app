from typing import Protocol


class CanonicalRecipientNotifier(Protocol):
    async def notify(self, *, user_ids: tuple[int, ...]) -> None: ...
