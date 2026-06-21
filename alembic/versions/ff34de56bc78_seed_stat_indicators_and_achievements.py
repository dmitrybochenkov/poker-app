"""seed stat indicators and achievements from historical data

Revision ID: ff34de56bc78
Revises: fe21cd43ab65
Create Date: 2026-05-13 13:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ff34de56bc78"
down_revision: Union[str, None] = "fe21cd43ab65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STAT_INDICATORS = [
  {"row_id": 1, "type": "betting", "description": "Баллы", "description_full": "Количество баллов за ставки", "pic": "💯", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 2, "type": "betting", "description": "Ставки", "description_full": "Количество поставленных ставок", "pic": "🐔🐤", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 3, "type": "betting", "description": "Удачные ставки", "description_full": "Количество угаданных ставок", "pic": "🔮🍀", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 4, "type": "betting", "description": "Процент удачных ставок", "description_full": "Отношение угаданных ставок к поставленным", "pic": "🔮🍀%", "for_current_tournaments": "yes", "is_for_achievement": True},
  {"row_id": 5, "type": "betting", "description": "Выбран победителем", "description_full": "Сколько раз ставили на победу игрока (без учета ставок на самого себя)", "pic": "👍", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 6, "type": "betting", "description": "Выбран проигравшим", "description_full": "Сколько раз ставили на поражение игрока", "pic": "👎", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 7, "type": "betting", "description": "Денег поставлено", "description_full": "Сколько всего поставил денег на ставках", "pic": "-💲", "for_current_tournaments": "yes", "is_for_achievement": False},
  {"row_id": 8, "type": "betting", "description": "Денег выиграно", "description_full": "Сколько выиграл денег на ставках", "pic": "+💲", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 9, "type": "betting", "description": "Выигрыш к проигрышу", "description_full": "Отношение выигранных денег к поставленным", "pic": "+💲/-💲", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 10, "type": "betting", "description": "Ставки на проигрыш к победам", "description_full": "Количество ставок на проигрыш игрока в дни, когда он побеждал", "pic": "👎/💍", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 11, "type": "betting", "description": "Ставки на победу к проигрышам", "description_full": "Количество ставок на победу игрока в дни, когда он проигрывал (без учета ставок на самого себя)", "pic": "👍/❌", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 12, "type": "betting", "description": "Принес денег проигрышами", "description_full": "Сумма денег, которую принесли ставки на проигрыш этого игрока", "pic": "❌➡️💲", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 13, "type": "betting", "description": "Принес денег выигрышами", "description_full": "Сумма денег, которую принесли ставки на победу этого игрока (без учета ставок на самого себя)", "pic": "💍➡️💲", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 14, "type": "betting", "description": "Побед в турнирах", "description_full": "Количество побед в ставочных регулярных турнирах", "pic": "🏆", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 15, "type": "betting", "description": "Побед в годовых турнирах", "description_full": "Количество побед в ставочных праздничных турнирах", "pic": "🎄🏆", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 16, "type": "poker", "description": "Денег всего", "description_full": "Баланс денег в покере", "pic": "💲", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 17, "type": "poker", "description": "Игр всего", "description_full": "Количество сыгранных игр", "pic": "🎲", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 18, "type": "poker", "description": "Закупов всего", "description_full": "Сумма закупов ", "pic": "🏦", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 19, "type": "poker", "description": "Количество побед", "description_full": "Количество побед в покерах", "pic": "💍", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 20, "type": "poker", "description": "Победы в 2ух играх подряд", "description_full": "Количество побед в двух покерах подряд", "pic": "🛡️💍", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 21, "type": "poker", "description": "Количество проигрышей", "description_full": "Количество проигрышей", "pic": "❌", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 22, "type": "poker", "description": "Макс.закуп", "description_full": "Максимальное количество закупов за одну игру", "pic": "🔝🏦", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 23, "type": "poker", "description": "Макс.выигрыш", "description_full": "Максимальный выигрыш в одной игре", "pic": "🔝💲⬆️", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 24, "type": "poker", "description": "Макс.проигрыш", "description_full": "Максимальный проигрыш в одной игре", "pic": "🔝💲⬇️", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 25, "type": "poker", "description": "Денег за игру", "description_full": "Отношение баланса денег к количеству игр", "pic": "💲/🎲", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 26, "type": "poker", "description": "Денег за закуп", "description_full": "Отношение баланса денег к количеству закупов", "pic": "💲/🏦", "for_current_tournaments": "no", "is_for_achievement": True},
  {"row_id": 27, "type": "poker", "description": "Закупов за игру", "description_full": "Отношение количества закупов к количеству игр", "pic": "🏦/🎲", "for_current_tournaments": "no", "is_for_achievement": False},
  {"row_id": 28, "type": "betting", "description": "Неоплаченных ставок", "description_full": "Количество неоплаченных ставок", "pic": "🚨", "for_current_tournaments": "only", "is_for_achievement": True},
  {"row_id": 29, "type": "betting", "description": "Ставок на самого себя", "description_full": "Количество ставок на самого себя", "pic": "🍆✊💦", "for_current_tournaments": "yes", "is_for_achievement": True},
]


ACHIEVEMENTS = [
  {"row_id": 1, "type": "poker", "sort": "desc", "description": "Король_Наибольший баланс денег за период", "pic": "👑", "stat_id": 16, "is_permanent": False},
  {"row_id": 2, "type": "poker", "sort": "asc", "description": "Кальмар_Наименьший баланс денег за период", "pic": "🦑", "stat_id": 16, "is_permanent": False},
  {"row_id": 3, "type": "poker", "sort": "desc", "description": "Мозг_Наибольшее среднее количество денег за закуп", "pic": "🧠", "stat_id": 26, "is_permanent": False},
  {"row_id": 4, "type": "poker", "sort": "none", "description": "Силач_Обладатель защищенных колец - 2 победы подряд за все время", "pic": "💪", "stat_id": 20, "is_permanent": False},
  {"row_id": 5, "type": "poker", "sort": "none", "description": "Киборг_Обладатель дважды защищенных колец - 3 победы подряд за все время", "pic": "🦾", "stat_id": 20, "is_permanent": False},
  {"row_id": 6, "type": "poker", "sort": "none", "description": "Легенда покера_Трижды защитил кольцо победителя - 4 победы подряд за все время", "pic": "🎖️", "stat_id": 20, "is_permanent": True},
  {"row_id": 7, "type": "betting", "sort": "desc", "description": "Гений_Наибольший процент успешных ставок в тотализаторе", "pic": "🎓", "stat_id": 4, "is_permanent": False},
  {"row_id": 8, "type": "betting", "sort": "desc", "description": "Темная лошадка_Наибольшее количество ставок на проигрыш игрока в дни, когда он победил", "pic": "🐎", "stat_id": 10, "is_permanent": False},
  {"row_id": 9, "type": "betting", "sort": "desc", "description": "Дохлый осел_Наибольшее количество ставок на победу игрока в дни, когда он проиграл", "pic": "🫏", "stat_id": 11, "is_permanent": False},
  {"row_id": 10, "type": "betting", "sort": "desc", "description": "Курочка, которая несет золотые яица_Игрок приносит выигрышами больше всего денег другим игрокам", "pic": "🐓", "stat_id": 13, "is_permanent": False},
  {"row_id": 11, "type": "betting", "sort": "desc", "description": "Дойная корова_Игрок приносит проигрышами больше всего денег другим игрокам", "pic": "🐄", "stat_id": 12, "is_permanent": False},
  {"row_id": 12, "type": "betting", "sort": "desc", "description": "Мудрая сова_Наибольшее отношение выигрыша к сумме ставок в тотализаторе", "pic": "🦉", "stat_id": 9, "is_permanent": False},
  {"row_id": 13, "type": "betting", "sort": "none", "description": "Сыщик_Победил в двух годовых турнирах", "pic": "🕵️", "stat_id": 15, "is_permanent": False},
  {"row_id": 14, "type": "betting", "sort": "none", "description": "Маг-предсказатель_Победил в трех годовых турнирах", "pic": "🧙", "stat_id": 15, "is_permanent": False},
  {"row_id": 15, "type": "betting", "sort": "none", "description": "Легенда тотализатора_Победил в четырех годовых турнирах", "pic": "🏅", "stat_id": 15, "is_permanent": True},
  {"row_id": 16, "type": "betting", "sort": "none", "description": "Законопослушный гражданин_Не имеет неоплаченных ставок в текущем турнире", "pic": "👮", "stat_id": 28, "is_permanent": False},
  {"row_id": 17, "type": "betting", "sort": "desc", "description": "Дрочила_Ставит сам на себя чаще всех", "pic": "🍆", "stat_id": 29, "is_permanent": False},
]


def upgrade() -> None:
  op.execute(sa.text("DELETE FROM achievements"))
  op.execute(sa.text("DELETE FROM stat_indicators"))

  stat_table = sa.table(
    "stat_indicators",
    sa.column("row_id", sa.Integer()),
    sa.column("type", sa.String(length=16)),
    sa.column("description", sa.String(length=255)),
    sa.column("description_full", sa.String(length=1024)),
    sa.column("pic", sa.String(length=32)),
    sa.column("for_current_tournaments", sa.String(length=16)),
    sa.column("is_for_achievement", sa.Boolean()),
  )
  ach_table = sa.table(
    "achievements",
    sa.column("row_id", sa.Integer()),
    sa.column("type", sa.String(length=16)),
    sa.column("sort", sa.String(length=16)),
    sa.column("description", sa.String(length=255)),
    sa.column("pic", sa.String(length=32)),
    sa.column("stat_id", sa.Integer()),
    sa.column("is_permanent", sa.Boolean()),
  )

  op.bulk_insert(stat_table, STAT_INDICATORS)
  op.bulk_insert(ach_table, ACHIEVEMENTS)


def downgrade() -> None:
  op.execute(sa.text("DELETE FROM achievements"))
  op.execute(sa.text("DELETE FROM stat_indicators"))
