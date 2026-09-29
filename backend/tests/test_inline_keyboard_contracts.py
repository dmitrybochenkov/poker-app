import json
from datetime import date
from types import SimpleNamespace

from app.bot.telegram import keyboards as tg
from app.bot.vk import keyboards as vk


def _tg_callbacks(markup):
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def _vk_payloads(keyboard):
    return [
        [button["action"].get("payload") for button in row]
        for row in json.loads(keyboard)["buttons"]
    ]


def test_registration_review_contracts():
    assert _tg_callbacks(tg.registration_review_keyboard(row_id=7)) == [
        ["approve:7"],
        ["correct:7"],
        ["reject:7"],
        ["link:7"],
    ]
    assert _vk_payloads(vk.registration_review_keyboard(row_id=7)) == [
        [{"action": "approve", "row_id": 7}],
        [{"action": "reject", "row_id": 7}],
        [{"action": "correct", "row_id": 7}],
        [{"action": "link", "row_id": 7}],
    ]


def test_poker_room_start_betting_button_is_conditional_and_last():
    player = SimpleNamespace(player_id=7, player_name="Alice")

    assert _tg_callbacks(
        tg.poker_room_admin_status_keyboard(
            players=[player], can_start_betting=False
        )
    ) == [["pokerroommanage:7"]]
    assert _tg_callbacks(
        tg.poker_room_admin_status_keyboard(players=[player], can_start_betting=True)
    ) == [["pokerroommanage:7"], ["pokerstartbetting:inline"]]
    assert _vk_payloads(
        vk.poker_room_admin_status_keyboard(players=[player], can_start_betting=True)
    ) == [
        [{"action": "poker_room_manage_select", "player_id": 7}],
        [{"action": "poker_start_betting_inline"}],
    ]


def test_buyin_count_preserves_integer_encoding_and_layout():
    kwargs = {
        "player_id": 7,
        "max_buyins": 3,
        "big_buyin": 4,
        "king_buyin": 5,
        "super_buyin": 6,
        "big_buyin_pic": "B",
        "king_buyin_pic": "K",
        "super_buyin_pic": "S",
        "include_king_buyin": True,
        "current_big_buyin_count": 1,
        "current_super_buyin_count": 2,
    }
    assert _tg_callbacks(tg.poker_buyin_count_keyboard(**kwargs)) == [
        ["pokerbuyincount:7:1"],
        ["pokerbuyincount:7:2"],
        ["pokerbuyincount:7:3"],
        ["pokerbuyincancel:7"],
    ]
    assert _vk_payloads(vk.poker_buyin_count_keyboard(**kwargs)) == [
        [{"action": "poker_buyin_count_select", "player_id": 7, "count": 1}],
        [{"action": "poker_buyin_count_select", "player_id": 7, "count": 2}],
        [{"action": "poker_buyin_count_select", "player_id": 7, "count": 3}],
        [{"action": "poker_buyin_cancel", "player_id": 7}],
    ]


def test_betting_and_receipt_contracts():
    assert _tg_callbacks(
        tg.betting_player_keyboard(
            action="winner", players=["Alice", "Bob"], player_marks={"Alice": "✅"}
        )
    ) == [["bet_winner:Alice"], ["bet_winner:Bob"]]
    assert _vk_payloads(
        vk.betting_player_keyboard(
            action="winner", players=["Alice", "Bob"], player_marks={"Alice": "✅"}
        )
    ) == [
        [{"action": "bet_winner", "player_name": "Alice"}],
        [{"action": "bet_winner", "player_name": "Bob"}],
    ]
    assert _tg_callbacks(tg.bet_receipt_manual_keyboard(receipt_row_id=9)) == [
        ["betreceipt:done:9", "betreceipt:cancel:9"]
    ]
    assert _vk_payloads(vk.bet_receipt_manual_keyboard(receipt_row_id=9)) == [
        [
            {"action": "bet_receipt_done", "receipt_row_id": 9},
            {"action": "bet_receipt_cancel", "receipt_row_id": 9},
        ]
    ]


def test_statistics_contracts():
    indicator = SimpleNamespace(row_id=3, pic="🏆", description="Wins")
    assert _tg_callbacks(
        tg.betting_stat_indicators_keyboard(
            indicators=[indicator], page=0, selected_ids=[3]
        )
    ) == [["betstat_toggle:3:0"], ["betstat_back", "betstat_done", "betstat_cancel"]]
    assert _vk_payloads(
        vk.betting_stat_indicators_keyboard(
            indicators=[indicator], page=0, selected_ids=[3]
        )
    ) == [
        [{"action": "betstat_toggle", "indicator_id": 3, "page": 0}],
        [
            {"action": "betstat_back"},
            {"action": "betstat_done"},
            {"action": "betstat_cancel"},
        ],
    ]


def test_poll_contract_preserves_rows_and_parameter_formats():
    kwargs = {
        "month": date(2026, 9, 1),
        "page": 0,
        "selected_dates": [date(2026, 9, 4)],
        "extra_dates": [],
    }
    assert _tg_callbacks(tg.poll_month_keyboard(**kwargs)) == [
        ["poll_day:2026-09-04:0", "poll_day:2026-09-05:0"],
        ["poll_day:2026-09-11:0", "poll_day:2026-09-12:0"],
        ["poll_noop", "poll_page:2026-09:1"],
        ["poll_suggest:2026-09"],
        ["poll_done", "poll_cancel"],
    ]
    assert _vk_payloads(vk.poll_month_keyboard(**kwargs)) == [
        [
            {"action": "poll_day", "date": "2026-09-04", "page": 0},
            {"action": "poll_day", "date": "2026-09-05", "page": 0},
        ],
        [
            {"action": "poll_day", "date": "2026-09-11", "page": 0},
            {"action": "poll_day", "date": "2026-09-12", "page": 0},
        ],
        [{"action": "poll_noop"}, {"action": "poll_page", "month": "2026-09", "page": 1}],
        [{"action": "poll_suggest", "month": "2026-09"}],
        [{"action": "poll_done"}, {"action": "poll_cancel"}],
    ]
