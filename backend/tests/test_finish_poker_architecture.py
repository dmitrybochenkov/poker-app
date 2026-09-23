import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_finish_poker_application_is_transport_neutral() -> None:
    imports = _imports(APP_ROOT / "application/use_cases/poker/finish_poker.py")
    assert not any(
        name == "aiogram"
        or name.startswith("aiogram.")
        or name == "vkbottle"
        or name.startswith("vkbottle.")
        or name.startswith("app.bot.")
        for name in imports
    )


def test_finish_poker_handlers_do_not_cross_import_presentations() -> None:
    telegram_imports = _imports(APP_ROOT / "bot/telegram/handlers/admin/finish_poker.py")
    vk_imports = _imports(APP_ROOT / "bot/vk/handlers/admin/finish_poker.py")

    assert not any(name.startswith("app.bot.vk") for name in telegram_imports)
    assert not any(name.startswith("app.bot.telegram") for name in vk_imports)


def test_finish_poker_notification_uses_one_shared_text_source() -> None:
    source = (APP_ROOT / "services/finish_poker_notifications.py").read_text()
    assert source.count("Text.user.POKER_FINISHED_ENTER_CHIPS.value") == 2
