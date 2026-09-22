import asyncio
import urllib.request

from app.bot.shared.texts.inline.shared import formatting as FormattingText
from app.bot.shared.texts.inline.vk.user import common as InlineText
from app.db.models.user import User


def _format_payment_requisites(owner: User | None) -> str:
    if owner is None:
        return InlineText.FORMAT_PAYMENT_REQUISITES_TEXT_01
    phone = (owner.tel_number or "").strip()
    bank = (owner.bank_name or "").strip()
    if phone and bank:
        return f"{phone} ({bank})"
    if phone:
        return phone
    return InlineText.FORMAT_PAYMENT_REQUISITES_TEXT_02

def _format_unpaid_bets_lines(bets: list) -> str:
    if not bets:
        return "-"
    return "\n".join(
        f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_01_PART_2}{int(bet.amount_kopecks) // 100}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_01_PART_4}'
        for bet in bets
    )

def _pick_fifo_bets_to_close(*, bets: list, paid_kopecks: int) -> list:
    selected: list = []
    running = 0
    for bet in bets:
        running += int(bet.amount_kopecks)
        selected.append(bet)
        if running == paid_kopecks:
            return selected
        if running > paid_kopecks:
            return []
    return []

def _extract_vk_attachment_url(raw_message: dict | None) -> str | None:
    attachments = (raw_message or {}).get("attachments") or []
    for item in attachments:
        item_type = str(item.get("type") or "")
        if item_type == "photo":
            photo = item.get("photo") or {}
            sizes = photo.get("sizes") or []
            if sizes:
                best = max(sizes, key=lambda s: int(s.get("width", 0)) * int(s.get("height", 0)))
                url = best.get("url")
                if isinstance(url, str) and url:
                    return url
        if item_type == "doc":
            doc = item.get("doc") or {}
            url = doc.get("url")
            if isinstance(url, str) and url:
                return url
    return None

def _extract_vk_external_file_id(raw_message: dict | None) -> str | None:
    attachments = (raw_message or {}).get("attachments") or []
    for item in attachments:
        item_type = str(item.get("type") or "")
        if item_type == "photo":
            photo = item.get("photo") or {}
            owner_id = photo.get("owner_id")
            photo_id = photo.get("id")
            if owner_id is not None and photo_id is not None:
                return f"photo:{owner_id}_{photo_id}"
        if item_type == "doc":
            doc = item.get("doc") or {}
            owner_id = doc.get("owner_id")
            doc_id = doc.get("id")
            if owner_id is not None and doc_id is not None:
                return f"doc:{owner_id}_{doc_id}"
    return None

async def _download_vk_receipt_bytes(raw_message: dict | None) -> bytes | None:
    url = _extract_vk_attachment_url(raw_message)
    if not url:
        return None

    def _read() -> bytes | None:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read()
        except Exception:
            return None

    return await asyncio.to_thread(_read)
