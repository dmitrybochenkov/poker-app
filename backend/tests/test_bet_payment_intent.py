import asyncio
import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.bet import Bet
from app.db.models.bet_param import BetParam
from app.db.models.bet_payment_receipt import BetPaymentReceipt, BetPaymentReceiptBet
from app.db.models.poker import Poker
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.services.bet_payment import (
    apply_exact_receipt_payment,
    change_receipt_intent,
    confirm_receipt_payment,
    reject_receipt_payment,
)


async def _store(tmp_path, name="receipts.db"):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                BetParam.__table__,
                Bet.__table__,
                BetPaymentReceipt.__table__,
                BetPaymentReceiptBet.__table__,
            ],
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(sessions):
    async with sessions() as session:
        user = User(row_id=7, telegram_id=7, name="Player", is_approved=True)
        poker_params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        bet_params = BetParam(
            small_size_kopecks=10_000,
            small_score=1,
            small_score_combo=2,
            big_size_kopecks=20_000,
            big_score=2,
            big_score_combo=4,
        )
        session.add_all([user, poker_params, bet_params])
        await session.flush()
        pokers = [
            Poker(params_id=poker_params.row_id, date=date(2026, 9, day))
            for day in (1, 2, 3)
        ]
        session.add_all(pokers)
        await session.flush()
        bets = [
            Bet(
                poker_id=poker.row_id,
                params_id=bet_params.row_id,
                date=poker.date,
                better_name="Player",
                better_id=user.row_id,
                amount_kopecks=amount,
                winner_id=user.row_id,
                winner_name=user.name,
                loser_id=user.row_id,
                loser_name=user.name,
            )
            for poker, amount in zip(pokers, (10_000, 20_000, 30_000), strict=True)
        ]
        session.add_all(bets)
        await session.commit()
        return [int(bet.row_id) for bet in bets]


@pytest.mark.asyncio
async def test_new_receipt_intent_persists_across_sessions(tmp_path):
    engine, sessions = await _store(tmp_path)
    bet_ids = await _seed(sessions)
    try:
        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7,
                platform="tg",
                external_file_id="file-1",
                operation_id="operation-1",
                amount_kopecks_ocr=30_000,
                recipient_tail4_ocr="1234",
                status="manual",
                expected_amount_kopecks=30_000,
                intended_bet_ids=bet_ids[:2],
            )
            receipt_id = int(receipt.row_id)
            await session.commit()

        async with sessions() as restarted_session:
            receipt = await BetPaymentReceiptRepository(restarted_session).get_by_row_id(
                row_id=receipt_id
            )
            assert receipt.expected_amount_kopecks == 30_000
            assert await BetPaymentReceiptRepository(restarted_session).list_intended_bet_ids(
                receipt_row_id=receipt_id
            ) == bet_ids[:2]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_acceptance_pays_exact_ids_without_same_total_substitution(tmp_path):
    engine, sessions = await _store(tmp_path)
    bet_ids = await _seed(sessions)
    try:
        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7, platform="vk", external_file_id="file-2",
                operation_id="operation-2", amount_kopecks_ocr=30_000,
                recipient_tail4_ocr="1234", status="manual",
                expected_amount_kopecks=30_000, intended_bet_ids=bet_ids[:2],
            )
            result = await apply_exact_receipt_payment(session=session, receipt=receipt)
            await session.commit()
            assert result.ok is True

        async with sessions() as session:
            rows = (await session.execute(select(Bet).order_by(Bet.row_id))).scalars().all()
            assert [row.is_paid for row in rows] == [True, True, False]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_conditional_update_mismatch_rolls_back_every_bet_mutation(tmp_path):
    engine, sessions = await _store(tmp_path)
    bet_ids = await _seed(sessions)
    try:
        async with sessions() as session:
            already_paid = await session.get(Bet, bet_ids[1])
            already_paid.is_paid = True
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7, platform="tg", external_file_id="file-3",
                operation_id="operation-3", amount_kopecks_ocr=30_000,
                recipient_tail4_ocr="1234", status="manual",
                expected_amount_kopecks=30_000, intended_bet_ids=bet_ids[:2],
            )
            await session.commit()

        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).get_by_row_id(row_id=int(receipt.row_id))
            result = await apply_exact_receipt_payment(session=session, receipt=receipt)
            await session.commit()
            assert result.ok is False
            assert result.status == "manual_conflict"

        async with sessions() as session:
            first = await session.get(Bet, bet_ids[0])
            second = await session.get(Bet, bet_ids[1])
            assert first.is_paid is False
            assert second.is_paid is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_change_is_durable_and_confirm_is_replay_safe(tmp_path):
    engine, sessions = await _store(tmp_path)
    bet_ids = await _seed(sessions)
    try:
        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7, platform="tg", external_file_id="file-4",
                operation_id="operation-4", amount_kopecks_ocr=30_000,
                recipient_tail4_ocr="1234", status="manual",
                expected_amount_kopecks=30_000, intended_bet_ids=bet_ids[:2],
            )
            receipt_id = int(receipt.row_id)
            changed = await change_receipt_intent(
                session=session, receipt_row_id=receipt_id, intended_bet_ids=[bet_ids[2]]
            )
            assert changed.ok is True
            await session.commit()

        async with sessions() as restarted_session:
            result = await confirm_receipt_payment(
                session=restarted_session, receipt_row_id=receipt_id
            )
            await restarted_session.commit()
            assert result.ok is True
            assert result.closed_count == 1

        async with sessions() as session:
            repeated = await confirm_receipt_payment(session=session, receipt_row_id=receipt_id)
            assert repeated.ok is False
            rows = (await session.execute(select(Bet).order_by(Bet.row_id))).scalars().all()
            assert [row.is_paid for row in rows] == [False, False, True]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_legacy_receipt_uses_fifo_compatibility(tmp_path):
    engine, sessions = await _store(tmp_path)
    await _seed(sessions)
    try:
        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7, platform="tg", external_file_id="legacy",
                operation_id=None, amount_kopecks_ocr=30_000,
                recipient_tail4_ocr=None, status="manual",
            )
            receipt_id = int(receipt.row_id)
            await session.commit()
        async with sessions() as session:
            result = await confirm_receipt_payment(session=session, receipt_row_id=receipt_id)
            await session.commit()
            assert result.ok is True
            assert result.status == "accepted_manual_legacy"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_receipts_cannot_both_claim_the_same_bet(tmp_path):
    engine, sessions = await _store(tmp_path, "double-claim.db")
    bet_ids = await _seed(sessions)
    try:
        receipt_ids = []
        async with sessions() as session:
            for suffix in ("a", "b"):
                receipt = await BetPaymentReceiptRepository(session).create(
                    user_row_id=7, platform="tg", external_file_id=f"file-{suffix}",
                    operation_id=f"operation-{suffix}", amount_kopecks_ocr=10_000,
                    recipient_tail4_ocr="1234", status="manual",
                    expected_amount_kopecks=10_000, intended_bet_ids=[bet_ids[0]],
                )
                receipt_ids.append(int(receipt.row_id))
            await session.commit()

        async def claim(receipt_id):
            async with sessions() as session:
                result = await confirm_receipt_payment(
                    session=session, receipt_row_id=receipt_id
                )
                await session.commit()
                return result

        results = await asyncio.gather(*(claim(item) for item in receipt_ids))
        assert sum(result.ok for result in results) == 1
    finally:
        await engine.dispose()


def test_migration_preserves_legacy_receipt_and_adds_durable_intent_schema(tmp_path):
    database = tmp_path / "migration.db"
    environment = os.environ | {
        "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    root = Path(__file__).parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "c8f4e1a2b7d9"],
        cwd=root, env=environment, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO bet_payment_receipts "
            "(user_row_id, platform, external_file_id, operation_id, amount_kopecks_ocr, "
            "recipient_tail4_ocr, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (7, "tg", "legacy-file", None, 10_000, None, "manual"),
        )
        connection.commit()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root, env=environment, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        legacy = connection.execute(
            "SELECT expected_amount_kopecks, status FROM bet_payment_receipts "
            "WHERE external_file_id = 'legacy-file'"
        ).fetchone()
        association_columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info('bet_payment_receipt_bets')"
            )
        }
    assert legacy == (None, "manual")
    assert association_columns == {"receipt_id", "bet_id"}


@pytest.mark.asyncio
async def test_reject_is_terminal_and_never_pays_bets(tmp_path):
    engine, sessions = await _store(tmp_path, "reject.db")
    bet_ids = await _seed(sessions)
    try:
        async with sessions() as session:
            receipt = await BetPaymentReceiptRepository(session).create(
                user_row_id=7, platform="vk", external_file_id="reject-file",
                operation_id="reject-operation", amount_kopecks_ocr=10_000,
                recipient_tail4_ocr="1234", status="manual",
                expected_amount_kopecks=10_000, intended_bet_ids=[bet_ids[0]],
            )
            receipt_id = int(receipt.row_id)
            await session.commit()
        async with sessions() as session:
            first = await reject_receipt_payment(session=session, receipt_row_id=receipt_id)
            second = await reject_receipt_payment(session=session, receipt_row_id=receipt_id)
            await session.commit()
            assert first.ok is True
            assert second.ok is False
            assert (await session.get(Bet, bet_ids[0])).is_paid is False
    finally:
        await engine.dispose()
