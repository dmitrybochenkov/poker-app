from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vk_conversation_state import VkConversationState


class VkConversationStateRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get(self, *, vk_user_id: int) -> VkConversationState | None:
    return await self.session.get(VkConversationState, int(vk_user_id))

  async def replace_without_commit(
    self,
    *,
    vk_user_id: int,
    user_row_id: int | None,
    state_type: str,
    payload: dict,
  ) -> VkConversationState:
    row = await self.get(vk_user_id=vk_user_id)
    if row is None:
      row = VkConversationState(vk_user_id=int(vk_user_id))
      self.session.add(row)
    row.user_row_id = int(user_row_id) if user_row_id is not None else None
    row.state_type = state_type
    row.payload = dict(payload)
    await self.session.flush()
    return row

  async def clear_without_commit(self, *, vk_user_id: int) -> bool:
    row = await self.get(vk_user_id=vk_user_id)
    if row is None:
      return False
    await self.session.delete(row)
    await self.session.flush()
    return True
