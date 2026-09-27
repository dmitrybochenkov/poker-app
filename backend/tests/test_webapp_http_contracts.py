from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.api.http import (
    webapp,
    webapp_bootstrap,
    webapp_common,
    webapp_info,
    webapp_profile,
    webapp_schemas,
)
from app.bot.shared.texts.texts import Text

EXPECTED_ROUTES = [
    ("GET", "/api/webapp/me/bootstrap", "webapp_bootstrap_by_platform", None, "WebAppBootstrapRead"),
    ("GET", "/api/webapp/players", "webapp_players", None, "list[WebAppPlayerCardRead]"),
    (
        "GET",
        "/api/webapp/info/{section}/{topic}",
        "webapp_info_content",
        None,
        "WebAppInfoContentRead",
    ),
    (
        "POST",
        "/api/webapp/me/photo",
        "upload_webapp_user_photo_by_platform",
        201,
        "WebAppPhotoUploadRead",
    ),
    (
        "POST",
        "/api/webapp/me/phone",
        "update_webapp_user_phone_by_platform",
        None,
        "WebAppPhoneUpdateRead",
    ),
    (
        "POST",
        "/api/webapp/me/bank",
        "update_webapp_user_bank_by_platform",
        None,
        "WebAppBankUpdateRead",
    ),
]


def _response_model_name(response_model):
    if getattr(response_model, "__origin__", None) is list:
        return f"list[{response_model.__args__[0].__name__}]"
    return response_model.__name__


def _route_contracts():
    return [
        (
            next(iter(route.methods)),
            f"{webapp.router.prefix}{route.path}",
            route.name,
            route.status_code,
            _response_model_name(route.response_model),
        )
        for included in webapp.router.routes
        for route in included.original_router.routes
    ]


def _image_bytes(*, size=(20, 10), image_format="JPEG"):
    output = BytesIO()
    Image.new("RGB", size, color=(100, 20, 30)).save(output, format=image_format)
    return output.getvalue()


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _BootstrapSession:
    def __init__(self, active_poker):
        self.active_poker = active_poker

    async def execute(self, statement):
        return _ScalarResult(self.active_poker)


class _MutationSession:
    def __init__(self, *, before_commit=None, commit_error=None):
        self.events = []
        self.before_commit = before_commit
        self.commit_error = commit_error

    async def commit(self):
        if self.before_commit is not None:
            self.before_commit()
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    async def refresh(self, user):
        self.events.append(("refresh", user.row_id))


def test_webapp_route_table_contract():
    assert webapp.router.prefix == "/api/webapp"
    assert webapp.router.tags == ["webapp"]
    assert _route_contracts() == EXPECTED_ROUTES
    assert len({(method, path) for method, path, *_ in _route_contracts()}) == len(EXPECTED_ROUTES)


def test_webapp_schema_fields_requiredness_and_defaults_are_stable():
    schemas = {
        webapp_schemas.WebAppBootstrapRead: (
            {
                "user_row_id",
                "is_registered",
                "is_admin",
                "is_approved",
                "has_phone",
                "has_active_poll",
                "has_active_poker",
            },
            {"user_row_id": None},
        ),
        webapp_schemas.WebAppPlayerCardRead: (
            {
                "player_id",
                "name",
                "tel_number",
                "bank_name",
                "games",
                "wins",
                "losses",
                "profit_rub",
                "photo_url",
            },
            {"tel_number": None, "bank_name": None, "photo_url": None},
        ),
        webapp_schemas.WebAppPhotoUploadRead: ({"photo_url"}, {}),
        webapp_schemas.WebAppPhoneUpdateWrite: ({"tel_number"}, {}),
        webapp_schemas.WebAppPhoneUpdateRead: ({"tel_number"}, {}),
        webapp_schemas.WebAppBankUpdateWrite: ({"bank_name"}, {}),
        webapp_schemas.WebAppBankUpdateRead: ({"bank_name"}, {}),
        webapp_schemas.WebAppInfoContentRead: ({"title", "body_html"}, {}),
    }

    for schema, (field_names, defaults) in schemas.items():
        assert set(schema.model_fields) == field_names
        assert {
            name: field.default
            for name, field in schema.model_fields.items()
            if not field.is_required()
        } == defaults

    with pytest.raises(ValidationError):
        webapp_schemas.WebAppPhoneUpdateWrite()
    with pytest.raises(ValidationError):
        webapp_schemas.WebAppBankUpdateWrite()


@pytest.mark.asyncio
async def test_bootstrap_preserves_platform_lookup_and_exact_known_user_flags(monkeypatch):
    user = SimpleNamespace(
        row_id=17,
        is_admin=True,
        is_approved=False,
        tel_number=" +79990000000 ",
    )
    repository = SimpleNamespace(get_by_row_id=AsyncMock(return_value=user))
    poll_repository = SimpleNamespace(get_active_month=AsyncMock(return_value="2026-09"))
    monkeypatch.setattr(webapp_bootstrap, "UserRepository", lambda session: repository)
    monkeypatch.setattr(webapp_bootstrap, "PollConfigRepository", lambda session: poll_repository)

    result = await webapp_bootstrap.webapp_bootstrap_by_platform(
        session=_BootstrapSession(active_poker=9),
        identity=SimpleNamespace(user_row_id=17),
    )

    repository.get_by_row_id.assert_awaited_once_with(17)
    assert result.model_dump() == {
        "user_row_id": 17,
        "is_registered": True,
        "is_admin": True,
        "is_approved": False,
        "has_phone": True,
        "has_active_poll": True,
        "has_active_poker": True,
    }


@pytest.mark.asyncio
async def test_telegram_bootstrap_unknown_user_preserves_current_flags(monkeypatch):
    repository = SimpleNamespace(get_by_row_id=AsyncMock())
    poll_repository = SimpleNamespace(get_active_month=AsyncMock(return_value=None))
    monkeypatch.setattr(webapp_bootstrap, "UserRepository", lambda session: repository)
    monkeypatch.setattr(webapp_bootstrap, "PollConfigRepository", lambda session: poll_repository)

    result = await webapp_bootstrap.webapp_bootstrap_by_platform(
        session=_BootstrapSession(active_poker=None),
        identity=SimpleNamespace(user_row_id=None),
    )

    repository.get_by_row_id.assert_not_awaited()
    assert result.model_dump() == {
        "user_row_id": None,
        "is_registered": False,
        "is_admin": False,
        "is_approved": False,
        "has_phone": False,
        "has_active_poll": False,
        "has_active_poker": False,
    }


@pytest.mark.asyncio
async def test_info_root_and_betting_rules_preserve_shared_html_sources():
    poker = await webapp_info.webapp_info_content(section="poker", topic="root", session=object())
    bets = await webapp_info.webapp_info_content(section="bets", topic="root", session=object())
    rules = await webapp_info.webapp_info_content(section="bets", topic="rules", session=object())

    assert poker.model_dump() == {
        "title": "ℹ️💍 Про покер",
        "body_html": Text.user.POKER_INFO.value,
    }
    assert bets.model_dump() == {
        "title": "ℹ️🍀 Про ставки",
        "body_html": Text.user.BETTING_MENU.value,
    }
    assert rules.model_dump() == {
        "title": "📖 Правила",
        "body_html": Text.user.BET_RULES.value,
    }


@pytest.mark.asyncio
async def test_info_metrics_and_achievements_preserve_html_formatting(monkeypatch):
    indicators = [
        SimpleNamespace(row_id=3, pic="🏆", description="Wins", description_full="Full wins")
    ]
    achievements = [SimpleNamespace(pic="⭐", description="Champion_Win often", stat_id=3)]
    monkeypatch.setattr(
        webapp_info,
        "StatIndicatorRepository",
        lambda session: SimpleNamespace(list_by_type=AsyncMock(return_value=indicators)),
    )
    monkeypatch.setattr(
        webapp_info,
        "AchievementRepository",
        lambda session: SimpleNamespace(list_by_type=AsyncMock(return_value=achievements)),
    )

    metrics = await webapp_info.webapp_info_content(
        section="poker", topic="metrics", session=object()
    )
    achievement_info = await webapp_info.webapp_info_content(
        section="poker", topic="achievements", session=object()
    )

    assert metrics.model_dump() == {
        "title": "ℹ️📊 Показатели",
        "body_html": "🏆 <b>Wins</b>\nFull wins",
    }
    assert achievement_info.model_dump() == {
        "title": "ℹ️🌟 Ачивки",
        "body_html": "⭐ <b>Champion</b>\nWin often\nПоказатель: 🏆 Wins",
    }


@pytest.mark.asyncio
async def test_info_unsupported_section_topic_pair_remains_404():
    with pytest.raises(HTTPException) as error:
        await webapp_info.webapp_info_content(section="poker", topic="rules", session=object())

    assert (error.value.status_code, error.value.detail) == (404, "Info page not found")


@pytest.mark.asyncio
async def test_phone_route_uses_principal_normalizes_commits_and_responds(monkeypatch):
    user = SimpleNamespace(row_id=7, tel_number=None)
    lookup = AsyncMock(return_value=user)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=lookup))
    session = _MutationSession()

    result = await webapp_profile.update_webapp_user_phone_by_platform(
        payload=webapp_schemas.WebAppPhoneUpdateWrite(tel_number="+7 (999) 123-45-67"),
        session=session,
        principal=SimpleNamespace(user_row_id=7),
    )

    lookup.assert_awaited_once_with(7)
    assert user.tel_number == "+79991234567"
    assert session.events == ["commit", ("refresh", 7)]
    assert result.model_dump() == {"tel_number": "+79991234567"}


@pytest.mark.asyncio
async def test_profile_routes_preserve_not_found_and_validation_errors(monkeypatch):
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=lookup))
    with pytest.raises(HTTPException) as not_found:
        await webapp_profile.update_webapp_user_phone_by_platform(
            payload=webapp_schemas.WebAppPhoneUpdateWrite(tel_number="79991234567"),
            session=_MutationSession(),
            principal=SimpleNamespace(user_row_id=7),
        )
    assert (not_found.value.status_code, not_found.value.detail) == (404, "User not found")

    user = SimpleNamespace(row_id=7, tel_number=None)
    lookup.return_value = user
    session = _MutationSession()
    with pytest.raises(HTTPException) as invalid_phone:
        await webapp_profile.update_webapp_user_phone_by_platform(
            payload=webapp_schemas.WebAppPhoneUpdateWrite(tel_number="89991234567"),
            session=session,
            principal=SimpleNamespace(user_row_id=7),
        )
    assert (invalid_phone.value.status_code, invalid_phone.value.detail) == (
        400,
        "Invalid phone number",
    )
    assert session.events == []


@pytest.mark.asyncio
async def test_bank_route_preserves_normalization_commit_and_response(monkeypatch):
    user = SimpleNamespace(row_id=7, bank_name=None)
    lookup = AsyncMock(return_value=user)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=lookup))
    session = _MutationSession()

    result = await webapp_profile.update_webapp_user_bank_by_platform(
        payload=webapp_schemas.WebAppBankUpdateWrite(bank_name="  ТИНЬКОФФ   БАНК "),
        session=session,
        principal=SimpleNamespace(user_row_id=7),
    )

    assert user.bank_name == "Тинькофф банк"
    assert session.events == ["commit", ("refresh", 7)]
    assert result.model_dump() == {"bank_name": "Тинькофф банк"}


@pytest.mark.asyncio
async def test_photo_routes_preserve_processing_storage_commit_and_response(
    monkeypatch, tmp_path
):
    user = SimpleNamespace(row_id=7, photo_path=None, updated_at=None)
    lookup = AsyncMock(return_value=user)
    output_path = tmp_path / "7.webp"
    session = _MutationSession(
        before_commit=lambda: (
            output_path.is_file()
            and user.photo_path == "user_photos/7.webp"
            or pytest.fail("photo must be written before commit")
        )
    )
    monkeypatch.setattr(webapp_profile, "USER_PHOTOS_DIR", tmp_path)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=lookup))
    monkeypatch.setattr(webapp_common, "_build_static_url", lambda path: f"/api/static/{path}")
    file = SimpleNamespace(
        content_type="image/jpeg",
        read=AsyncMock(return_value=_image_bytes(size=(2000, 1000))),
    )

    result = await webapp_profile.upload_webapp_user_photo_by_platform(
        file=file, session=session, principal=SimpleNamespace(user_row_id=7)
    )

    lookup.assert_awaited_once_with(7)
    assert user.photo_path == "user_photos/7.webp"
    assert isinstance(user.updated_at, datetime)
    assert session.events == ["commit", ("refresh", 7)]
    assert result.photo_url.startswith("/api/static/user_photos/7.webp?v=")
    with Image.open(output_path) as saved:
        assert saved.format == "WEBP"
        assert saved.mode == "RGB"
        assert saved.size == (1200, 600)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "content", "detail"),
    [
        ("text/plain", b"not image", "Only image files are supported"),
        ("image/png", b"", "Empty file"),
        ("image/png", b"x" * (8 * 1024 * 1024 + 1), "Image is too large"),
        ("image/png", b"not image", "Invalid image file"),
    ],
)
async def test_photo_validation_preserves_errors_without_commit(
    monkeypatch, tmp_path, content_type, content, detail
):
    user = SimpleNamespace(row_id=7, photo_path=None, updated_at=None)
    monkeypatch.setattr(webapp_profile, "USER_PHOTOS_DIR", tmp_path)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=AsyncMock(return_value=user)))
    session = _MutationSession()
    file = SimpleNamespace(content_type=content_type, read=AsyncMock(return_value=content))

    with pytest.raises(HTTPException) as error:
        await webapp_profile.upload_webapp_user_photo_by_platform(
            file=file, session=session, principal=SimpleNamespace(user_row_id=7)
        )

    assert (error.value.status_code, error.value.detail) == (400, detail)
    assert session.events == []
    assert user.photo_path is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_photo_filesystem_failure_propagates_before_db_mutation(monkeypatch, tmp_path):
    user = SimpleNamespace(row_id=7, photo_path=None, updated_at=None)
    image_bytes = _image_bytes(image_format="PNG")
    monkeypatch.setattr(webapp_profile, "USER_PHOTOS_DIR", tmp_path)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=AsyncMock(return_value=user)))
    monkeypatch.setattr(
        Image.Image, "save", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk"))
    )
    session = _MutationSession()
    file = SimpleNamespace(
        content_type="image/png",
        read=AsyncMock(return_value=image_bytes),
    )

    with pytest.raises(OSError, match="disk"):
        await webapp_profile.upload_webapp_user_photo_by_platform(
            file=file, session=session, principal=SimpleNamespace(user_row_id=7)
        )

    assert user.photo_path is None
    assert session.events == []


@pytest.mark.asyncio
async def test_photo_commit_failure_leaves_written_file_and_mutated_user(monkeypatch, tmp_path):
    user = SimpleNamespace(row_id=7, photo_path=None, updated_at=None)
    monkeypatch.setattr(webapp_profile, "USER_PHOTOS_DIR", tmp_path)
    monkeypatch.setattr(webapp_profile, "UserRepository", lambda session: SimpleNamespace(get_by_row_id=AsyncMock(return_value=user)))
    session = _MutationSession(commit_error=RuntimeError("db commit"))
    file = SimpleNamespace(
        content_type="image/png",
        read=AsyncMock(return_value=_image_bytes(image_format="PNG")),
    )

    with pytest.raises(RuntimeError, match="db commit"):
        await webapp_profile.upload_webapp_user_photo_by_platform(
            file=file, session=session, principal=SimpleNamespace(user_row_id=7)
        )

    assert (tmp_path / "7.webp").is_file()
    assert user.photo_path == "user_photos/7.webp"
    assert isinstance(user.updated_at, datetime)
    assert session.events == ["commit"]


def test_user_photo_directory_is_created_during_module_import():
    assert webapp_common.USER_PHOTOS_DIR.is_dir()
