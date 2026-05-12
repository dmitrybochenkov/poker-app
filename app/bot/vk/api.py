import secrets
import json

import aiohttp

from app.config.settings import settings


class VkApiError(RuntimeError):
  pass


async def vk_api_call(method: str, **params) -> dict:
  async with aiohttp.ClientSession() as session:
    async with session.post(
      f"https://api.vk.com/method/{method}",
      data={
        **params,
        "access_token": settings.vk_group_token,
        "v": settings.vk_api_version,
      },
    ) as response:
      data = await response.json()
      error = data.get("error")
      if error:
        code = error.get("error_code")
        msg = error.get("error_msg", "VK API error")
        raise VkApiError(f"VK API error {code} in {method}: {msg}")
      return data


async def send_vk_message(*, user_id: int, message: str, keyboard: str | None = None) -> None:
  chunks = [message]
  if len(message) > 3500 and keyboard is None:
    chunks = []
    current = ""
    for line in message.splitlines(keepends=True):
      if len(current) + len(line) > 3500 and current:
        chunks.append(current)
        current = line
      else:
        current += line
    if current:
      chunks.append(current)

  for index, chunk in enumerate(chunks):
    params = {
      "user_id": user_id,
      "random_id": secrets.randbelow(2**31 - 1),
      "message": chunk,
    }
    if keyboard is not None and index == len(chunks) - 1:
      params["keyboard"] = keyboard
    await vk_api_call("messages.send", **params)


async def send_vk_message_event_answer(
  *,
  event_id: str,
  user_id: int,
  peer_id: int,
  text: str,
) -> None:
  await vk_api_call(
    "messages.sendMessageEventAnswer",
    event_id=event_id,
    user_id=user_id,
    peer_id=peer_id,
    event_data=json.dumps(
      {
        "type": "show_snackbar",
        "text": text,
      },
      ensure_ascii=False,
    ),
  )


async def clear_vk_inline_keyboard(*, peer_id: int, conversation_message_id: int) -> None:
  # VK may reject one keyboard shape depending on message/context; try both.
  await vk_api_call(
    "messages.edit",
    peer_id=peer_id,
    conversation_message_id=conversation_message_id,
    keyboard=json.dumps({"buttons": []}, ensure_ascii=False),
  )
  await vk_api_call(
    "messages.edit",
    peer_id=peer_id,
    conversation_message_id=conversation_message_id,
    keyboard=json.dumps({"inline": True, "buttons": []}, ensure_ascii=False),
  )


async def delete_vk_message(*, peer_id: int, conversation_message_id: int) -> None:
  await vk_api_call(
    "messages.delete",
    peer_id=peer_id,
    cmids=str(conversation_message_id),
    delete_for_all=1,
  )
