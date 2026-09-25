import inspect
import json

import pytest

from app.bot.shared.keyboards.keyboards_reply import ReplyKbs

STATIC_METHODS = {"make_tg", "make_vk", "make_vk_callback"}
CLASS_METHODS = {
    "admin_main_entry_tg",
    "admin_main_entry_vk",
    "admin_main_tg",
    "admin_main_vk",
    "admin_room_correct_tg",
    "admin_room_correct_vk",
    "admin_room_tg",
    "admin_room_vk",
    "betting_current_tg",
    "betting_current_vk",
    "betting_dynamic_tg",
    "betting_dynamic_vk",
    "betting_info_tg",
    "betting_info_vk",
    "betting_tg",
    "betting_vk",
    "main_dynamic_tg",
    "main_dynamic_vk",
    "main_info_tg",
    "main_info_vk",
    "main_tg",
    "main_vk",
    "new_user_tg",
    "new_user_vk",
    "poker_info_tg",
    "poker_info_vk",
    "poker_tg",
    "poker_vk",
    "poll_menu_tg",
    "poll_menu_vk",
    "room_admin_tg",
    "room_admin_vk",
    "room_tg",
    "room_vk",
}

MENU_CONTRACTS = {
    "new_user": ["ℹ️ О покер боте", "💾 Зарегистрироваться"],
    "main": [
        "♣️ Покер рум",
        "💍 Про покер",
        "🍀 Про ставки",
        "ℹ️ Информация",
        "🔑 Админ панель",
    ],
    "admin_main_entry": [
        "♣️ Покер рум",
        "💍 Про покер",
        "🍀 Про ставки",
        "ℹ️ Информация",
        "🔑 Админ панель",
    ],
    "poll_menu": [
        "✅ Проголосовать",
        "📊 Посмотреть результаты",
        "🏠 На главную",
    ],
    "main_info": ["ℹ️💍 Про покер", "ℹ️🍀 Про ставки", "🏠 На главную"],
    "admin_main": [
        "🗓 Создать опрос",
        "🎲 Старт покера",
        "👨🏻\u200d💻 Добавить админа",
        "🏠 На главную",
    ],
    "betting": [
        "🐔 Сделать ставку",
        "🤝 Оплатить ставку",
        "🎰 Текущие турниры",
        "🍀 Статистика ставок",
        "🏠 На главную",
    ],
    "betting_current": [
        "💰 Регулярный турнир",
        "🎄💰 Годовой турнир",
        "🏠 На главную",
    ],
    "poker": [
        "📅 Следующий покер",
        "🦑 Статистика покера",
        "⌛ История",
        "🏠 На главную",
    ],
    "betting_info": [
        "📖 Правила",
        "ℹ️🌟 Ачивки для ставок",
        "ℹ️📊 Показатели для ставок",
        "🏠 На главную",
    ],
    "poker_info": [
        "ℹ️🌟 Ачивки для покера",
        "ℹ️📊 Показатели для покера",
        "🏠 На главную",
    ],
    "room": [
        "ℹ️ Статус",
        "🏦 Закуп",
        "🔑 Покер админ панель",
        "🏠 На главную",
    ],
    "room_admin": [
        "ℹ️ Статус",
        "🏦 Закуп",
        "🔑 Покер админ панель",
        "🏠 На главную",
    ],
    "admin_room": [
        "🔧 Корректировать покер",
        "🏁 Финиш покера",
        "♣️ В ПокерРум",
        "🏠 На главную",
    ],
    "admin_room_correct": [
        "🏦 Назначить кассира",
        "👨 Добавить игрока",
        "❌ Удалить игрока",
        "🏦 Корректировать закупы",
        "↩️ Назад",
    ],
}


def _tg_contract(markup):
    return {
        "rows": [[button.text for button in row] for row in markup.keyboard],
        "resize_keyboard": markup.resize_keyboard,
        "one_time_keyboard": markup.one_time_keyboard,
        "selective": markup.selective,
        "input_field_placeholder": markup.input_field_placeholder,
    }


def _vk_contract(keyboard):
    return json.loads(keyboard)


def _expected_vk(labels, *, color="primary", one_time=False, inline=False):
    return {
        "one_time": one_time,
        "inline": inline,
        "buttons": [
            [{"action": {"type": "text", "label": label}, "color": color}] for label in labels
        ],
    }


def test_reply_kbs_public_surface_and_descriptor_types():
    expected_names = STATIC_METHODS | CLASS_METHODS

    assert {name for name in dir(ReplyKbs) if not name.startswith("_")} == expected_names
    assert all(
        isinstance(inspect.getattr_static(ReplyKbs, name), staticmethod) for name in STATIC_METHODS
    )
    assert all(
        isinstance(inspect.getattr_static(ReplyKbs, name), classmethod) for name in CLASS_METHODS
    )
    assert all(
        sum(name in base.__dict__ for base in ReplyKbs.__mro__) == 1 for name in expected_names
    )


def test_low_level_tg_builder_contract():
    markup = ReplyKbs.make_tg(["A", "B", "C"], adjust=2, resize=False)

    assert _tg_contract(markup) == {
        "rows": [["A", "B"], ["C"]],
        "resize_keyboard": False,
        "one_time_keyboard": None,
        "selective": None,
        "input_field_placeholder": None,
    }


def test_low_level_vk_text_builder_contract():
    keyboard = ReplyKbs.make_vk(
        ["A", "B", "C"],
        adjust=2,
        one_time=True,
        inline=True,
        color="negative",
    )

    assert _vk_contract(keyboard) == {
        "one_time": True,
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "A"}, "color": "negative"},
                {"action": {"type": "text", "label": "B"}, "color": "negative"},
            ],
            [{"action": {"type": "text", "label": "C"}, "color": "negative"}],
        ],
    }


def test_low_level_vk_callback_builder_preserves_rows_and_flags():
    rows = [[{"action": {"type": "callback", "payload": {"id": 7}}, "color": "positive"}]]

    assert _vk_contract(ReplyKbs.make_vk_callback(rows, one_time=True, inline=False)) == {
        "one_time": True,
        "inline": False,
        "buttons": rows,
    }


@pytest.mark.parametrize(("factory", "labels"), MENU_CONTRACTS.items())
def test_static_tg_menu_contracts(factory, labels):
    assert _tg_contract(getattr(ReplyKbs, f"{factory}_tg")()) == {
        "rows": [[label] for label in labels],
        "resize_keyboard": True,
        "one_time_keyboard": None,
        "selective": None,
        "input_field_placeholder": None,
    }


@pytest.mark.parametrize(("factory", "labels"), MENU_CONTRACTS.items())
def test_static_vk_menu_contracts(factory, labels):
    assert _vk_contract(getattr(ReplyKbs, f"{factory}_vk")()) == _expected_vk(labels)


@pytest.mark.parametrize("is_admin", [False, True])
@pytest.mark.parametrize("has_active_poker", [False, True])
@pytest.mark.parametrize("has_active_poll", [False, True])
def test_main_dynamic_contract_preserves_all_current_argument_branches(
    is_admin, has_active_poker, has_active_poll
):
    kwargs = {
        "is_admin": is_admin,
        "has_active_poker": has_active_poker,
        "has_active_poll": has_active_poll,
    }
    labels = MENU_CONTRACTS["main"]

    assert _tg_contract(ReplyKbs.main_dynamic_tg(**kwargs))["rows"] == [[label] for label in labels]
    assert _vk_contract(ReplyKbs.main_dynamic_vk(**kwargs)) == _expected_vk(labels)


@pytest.mark.parametrize(
    ("include_make_bet", "labels"),
    [
        (True, MENU_CONTRACTS["betting"]),
        (False, MENU_CONTRACTS["betting"][1:]),
    ],
)
def test_betting_dynamic_contract_preserves_make_bet_branch(include_make_bet, labels):
    assert _tg_contract(ReplyKbs.betting_dynamic_tg(include_make_bet=include_make_bet))["rows"] == [
        [label] for label in labels
    ]
    assert _vk_contract(
        ReplyKbs.betting_dynamic_vk(include_make_bet=include_make_bet)
    ) == _expected_vk(labels)
