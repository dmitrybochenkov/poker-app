from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.webapp_schemas import WebAppInfoContentRead
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.texts import Text
from app.db.dependencies import get_db_session
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository

router = APIRouter()


def _format_stat_info_report(indicators) -> str:
    if not indicators:
        return "Справка пока пустая."
    lines: list[str] = []
    for item in indicators:
        pic = StatUseCases._prettify_header(str(item.pic or ""))
        lines.append(f"{pic} <b>{item.description}</b>")
        lines.append(f"{item.description_full}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_achievement_description(raw: str) -> tuple[str, str | None]:
    if "_" not in raw:
        return raw, None
    title, detail = raw.split("_", 1)
    return title.strip(), detail.strip() if detail else None


def _format_achievement_info_report(
    achievements, indicators_by_id: dict[int, tuple[str, str]]
) -> str:
    if not achievements:
        return "Справка пока пустая."
    lines: list[str] = []
    for item in achievements:
        title, detail = _format_achievement_description(item.description)
        ach_pic = StatUseCases._prettify_header(str(item.pic or ""))
        lines.append(f"{ach_pic} <b>{title}</b>")
        if detail:
            lines.append(detail)
        indicator_info = indicators_by_id.get(int(item.stat_id))
        if indicator_info:
            indicator_pic, indicator_name = indicator_info
            indicator_pic = StatUseCases._prettify_header(str(indicator_pic or ""))
            lines.append(f"Показатель: {indicator_pic} {indicator_name}".strip())
        lines.append("")
    return "\n".join(lines).strip()


@router.get("/info/{section}/{topic}", response_model=WebAppInfoContentRead)
async def webapp_info_content(
    section: Literal["poker", "bets"],
    topic: Literal["root", "rules", "achievements", "metrics"],
    session: AsyncSession = Depends(get_db_session),
) -> WebAppInfoContentRead:
    if topic == "root":
        if section == "poker":
            return WebAppInfoContentRead(
                title="ℹ️💍 Про покер", body_html=Text.user.POKER_INFO.value
            )
        return WebAppInfoContentRead(title="ℹ️🍀 Про ставки", body_html=Text.user.BETTING_MENU.value)

    if section == "bets" and topic == "rules":
        return WebAppInfoContentRead(title="📖 Правила", body_html=Text.user.BET_RULES.value)

    if topic == "metrics":
        indicator_type = "poker" if section == "poker" else "betting"
        indicators = await StatIndicatorRepository(session).list_by_type(
            indicator_type=indicator_type
        )
        return WebAppInfoContentRead(
            title="ℹ️📊 Показатели",
            body_html=_format_stat_info_report(indicators),
        )

    if topic == "achievements":
        achievement_type = "poker" if section == "poker" else "betting"
        achievements = await AchievementRepository(session).list_by_type(
            achievement_type=achievement_type
        )
        indicators = await StatIndicatorRepository(session).list_by_type(
            indicator_type=achievement_type
        )
        indicators_by_id = {
            int(item.row_id): (str(item.pic or ""), str(item.description or ""))
            for item in indicators
        }
        return WebAppInfoContentRead(
            title="ℹ️🌟 Ачивки",
            body_html=_format_achievement_info_report(achievements, indicators_by_id),
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Info page not found")
