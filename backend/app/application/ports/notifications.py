from typing import Protocol


class CanonicalRecipientNotifier(Protocol):
    async def notify(self, *, recipient_user_ids: tuple[int, ...]) -> None: ...
