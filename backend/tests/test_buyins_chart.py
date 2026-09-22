from datetime import date

from app.services.buyins_chart import render_buyins_history_chart_png


def test_history_chart_renders_nonempty_series() -> None:
    image = render_buyins_history_chart_png(
        title="Закупы",
        series={"Игрок": [(date(2026, 9, 1), 1), (date(2026, 9, 8), 2)]},
    )
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
