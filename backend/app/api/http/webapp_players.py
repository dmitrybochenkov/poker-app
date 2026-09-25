from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.webapp_common import _build_photo_url
from app.api.http.webapp_schemas import WebAppPlayerCardRead
from app.db.dependencies import get_db_session
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.user import User

router = APIRouter()


@router.get("/players", response_model=list[WebAppPlayerCardRead])
async def webapp_players(
    session: AsyncSession = Depends(get_db_session),
) -> list[WebAppPlayerCardRead]:
    approved_users = (
        await session.execute(
            select(
                User.row_id,
                User.name,
                User.photo_path,
                User.updated_at,
                User.tel_number,
                User.bank_name,
            )
            .where(User.is_approved.is_(True))
            .order_by(User.name.asc())
        )
    ).all()

    completed_pokers = (
        await session.execute(
            select(Poker.winners, Poker.loosers).where(
                or_(
                    Poker.winners.is_not(None),
                    Poker.loosers.is_not(None),
                )
            )
        )
    ).all()

    wins_by_name: dict[str, int] = {}
    losses_by_name: dict[str, int] = {}
    for winners_csv, losers_csv in completed_pokers:
        winners = {item.strip() for item in str(winners_csv or "").split(",") if item.strip()}
        losers = {item.strip() for item in str(losers_csv or "").split(",") if item.strip()}
        for name in winners:
            wins_by_name[name] = wins_by_name.get(name, 0) + 1
        for name in losers:
            losses_by_name[name] = losses_by_name.get(name, 0) + 1

    # Single bulk query instead of one query per player (was N+1: one extra
    # round-trip to the DB per approved user). We fetch all PokerData rows that
    # could belong to ANY approved user (matched either by player_id or by
    # player_name, same condition the old per-user query used) and aggregate
    # them in Python, preserving the original OR-matching semantics: a row
    # counts for a user if it matches by id OR by name (but only once each).
    user_ids = {int(user.row_id) for user in approved_users}
    user_names = {str(user.name) for user in approved_users}
    user_ids_by_name: dict[str, set[int]] = {}
    for user in approved_users:
        user_ids_by_name.setdefault(str(user.name), set()).add(int(user.row_id))

    poker_data_rows = (
        await session.execute(
            select(PokerData.player_id, PokerData.player_name, PokerData.money_kopecks).where(
                or_(
                    PokerData.player_id.in_(user_ids),
                    PokerData.player_name.in_(user_names),
                )
            )
        )
    ).all()

    games_by_user_id: dict[int, int] = {}
    profit_by_user_id: dict[int, int] = {}
    for player_id, player_name, money_kopecks in poker_data_rows:
        matched_user_ids: set[int] = set()
        if player_id in user_ids:
            matched_user_ids.add(int(player_id))
        matched_user_ids.update(user_ids_by_name.get(str(player_name), set()))
        for uid in matched_user_ids:
            games_by_user_id[uid] = games_by_user_id.get(uid, 0) + 1
            profit_by_user_id[uid] = profit_by_user_id.get(uid, 0) + int(money_kopecks or 0)

    result: list[WebAppPlayerCardRead] = []
    for user in approved_users:
        uid = int(user.row_id)
        result.append(
            WebAppPlayerCardRead(
                player_id=uid,
                name=str(user.name),
                tel_number=(str(user.tel_number).strip() if user.tel_number else None),
                bank_name=(str(user.bank_name).strip() if user.bank_name else None),
                games=games_by_user_id.get(uid, 0),
                wins=wins_by_name.get(str(user.name), 0),
                losses=losses_by_name.get(str(user.name), 0),
                profit_rub=int(profit_by_user_id.get(uid, 0) / 100),
                photo_url=_build_photo_url(user),
            )
        )

    return sorted(
        result,
        key=lambda item: (-(1 if item.wins > 0 else 0), -item.profit_rub, item.name),
    )
