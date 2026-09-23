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


def test_start_betting_application_is_transport_neutral() -> None:
    imports = _imports(APP_ROOT / "application/use_cases/poker/start_betting.py")
    assert not any(
        name == "aiogram"
        or name.startswith("aiogram.")
        or name == "vkbottle"
        or name.startswith("vkbottle.")
        or name.startswith("app.bot.")
        for name in imports
    )


def test_start_betting_handlers_do_not_cross_import_presentations() -> None:
    telegram_imports = _imports(APP_ROOT / "bot/telegram/handlers/admin/start_betting.py")
    vk_imports = _imports(APP_ROOT / "bot/vk/handlers/admin/start_betting.py")

    assert not any(name.startswith("app.bot.vk") for name in telegram_imports)
    assert not any(name.startswith("app.bot.telegram") for name in vk_imports)
