import secrets
import json

import aiohttp

from app.config.settings import settings


class VkApiError(RuntimeError):
  def __init__(self, *, code: int | None, method: str, message: str) -> None:
    self.code = code
    self.method = method
    self.message = message
    super().__init__(f"VK API error {code} in {method}: {message}")


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
        raise VkApiError(code=code, method=method, message=msg)
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


async def send_vk_message_with_id(*, user_id: int, message: str, keyboard: str | None = None) -> int | None:
  params = {
    "user_id": user_id,
    "random_id": secrets.randbelow(2**31 - 1),
    "message": message,
  }
  if keyboard is not None:
    params["keyboard"] = keyboard
  data = await vk_api_call("messages.send", **params)
  response = data.get("response")
  if isinstance(response, int):
    return response
  return None


async def edit_vk_message_by_id(*, peer_id: int, message_id: int, message: str, keyboard: str | None = None) -> None:
  params = {
    "peer_id": peer_id,
    "message_id": message_id,
    "message": message,
  }
  if keyboard is not None:
    params["keyboard"] = keyboard
  await vk_api_call("messages.edit", **params)


async def clear_vk_message_keyboard_by_id(*, peer_id: int, message_id: int) -> None:
  await vk_api_call(
    "messages.edit",
    peer_id=peer_id,
    message_id=message_id,
    keyboard=json.dumps({"buttons": []}, ensure_ascii=False),
  )


async def delete_vk_message_by_id(*, peer_id: int, message_id: int) -> None:
  await vk_api_call(
    "messages.delete",
    peer_id=peer_id,
    message_ids=str(message_id),
    delete_for_all=1,
  )


async def pin_vk_message_by_id(*, peer_id: int, message_id: int) -> None:
  await vk_api_call(
    "messages.pin",
    peer_id=peer_id,
    message_id=message_id,
  )


async def unpin_vk_message(*, peer_id: int) -> None:
  await vk_api_call(
    "messages.unpin",
    peer_id=peer_id,
  )


async def send_vk_photo(
  *,
  user_id: int,
  image_bytes: bytes,
  filename: str = "stat.png",
  message: str = "",
  keyboard: str | None = None,
) -> None:
  upload = await vk_api_call("photos.getMessagesUploadServer", peer_id=user_id)
  upload_url = upload.get("response", {}).get("upload_url")
  if not upload_url:
    raise VkApiError(code=None, method="photos.getMessagesUploadServer", message="upload_url missing")

  form = aiohttp.FormData()
  form.add_field("photo", image_bytes, filename=filename, content_type="image/png")
  async with aiohttp.ClientSession() as session:
    async with session.post(upload_url, data=form) as response:
      upload_result = await response.json()

  saved = await vk_api_call(
    "photos.saveMessagesPhoto",
    photo=upload_result.get("photo"),
    server=upload_result.get("server"),
    hash=upload_result.get("hash"),
  )
  photo_list = saved.get("response", [])
  if not photo_list:
    raise VkApiError(code=None, method="photos.saveMessagesPhoto", message="empty response")
  photo = photo_list[0]
  owner_id = photo.get("owner_id")
  media_id = photo.get("id")
  if owner_id is None or media_id is None:
    raise VkApiError(code=None, method="photos.saveMessagesPhoto", message="invalid photo ids")

  params = {
    "user_id": user_id,
    "random_id": secrets.randbelow(2**31 - 1),
    "attachment": f"photo{owner_id}_{media_id}",
    "message": message,
  }
  if keyboard is not None:
    params["keyboard"] = keyboard
  await vk_api_call("messages.send", **params)


async def send_vk_message_event_answer(
  *,
  event_id: str,
  user_id: int,
  peer_id: int,
  text: str,
) -> None:
  safe_text = text
  if len(safe_text) > 90:
    safe_text = safe_text[:87].rstrip() + "..."
  try:
    await vk_api_call(
      "messages.sendMessageEventAnswer",
      event_id=event_id,
      user_id=user_id,
      peer_id=peer_id,
      event_data=json.dumps(
        {
          "type": "show_snackbar",
          "text": safe_text,
        },
        ensure_ascii=False,
      ),
    )
  except VkApiError as exc:
    # VK can return "invalid event_id" when callback answer is late/stale.
    # This should not break webhook processing.
    if exc.code == 100 and (
      "invalid event_id" in exc.message.lower()
      or "client_action text should be not more than 90 letters length" in exc.message.lower()
    ):
      return
    raise


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
