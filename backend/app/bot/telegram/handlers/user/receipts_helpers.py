import io

from aiogram.types import Message

from app.bot.shared.texts.inline.shared import formatting as FormattingText
from app.bot.shared.texts.inline.telegram.user import common as InlineText
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
        f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_15_PART_2}{int(bet.amount_kopecks) // 100}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_15_PART_4}'
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

async def _download_telegram_receipt_bytes(message: Message) -> bytes | None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is None:
        return None
    file_id: str | None = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document is not None:
        file_id = message.document.file_id
    if not file_id:
        return None
    try:
        tg_file = await telegram_bot.get_file(file_id)
        if tg_file.file_path is None:
            return None
        buffer = io.BytesIO()
        await telegram_bot.download_file(tg_file.file_path, destination=buffer)
        return buffer.getvalue()
    except Exception:
        return None

def _telegram_external_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_unique_id
    if message.document is not None:
        return message.document.file_unique_id
    return None
