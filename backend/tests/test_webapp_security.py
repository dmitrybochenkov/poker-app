import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from app.api.http import registration, users, webapp
from app.api.security.telegram_webapp import verify_telegram_init_data
from app.api.security.webapp_auth import (
    TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
    require_admin_principal,
    require_authenticated_principal,
    resolve_webapp_identity,
)
from app.schemas.registration import RegistrationRequest

BOT_TOKEN = "test:bot-token"
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def signed_init_data(*, user_id=101, auth_date=None, user=None, token=BOT_TOKEN):
    values = {
        "auth_date": str(auth_date if auth_date is not None else int(NOW.timestamp())),
        "query_id": "AAE-test",
        "user": json.dumps(user if user is not None else {"id": user_id}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def assert_unauthorized(call):
    with pytest.raises(HTTPException) as exc:
        call()
    assert exc.value.status_code == 401


def test_telegram_init_data_cryptography_and_freshness():
    assert verify_telegram_init_data(signed_init_data(), bot_token=BOT_TOKEN, now=NOW) == 101

    invalid = signed_init_data().replace("hash=", "hash=00")
    assert_unauthorized(lambda: verify_telegram_init_data(invalid, bot_token=BOT_TOKEN, now=NOW))
    assert_unauthorized(
        lambda: verify_telegram_init_data(
            signed_init_data().replace("%22id%22%3A101", "%22id%22%3A202"),
            bot_token=BOT_TOKEN,
            now=NOW,
        )
    )
    assert_unauthorized(lambda: verify_telegram_init_data("auth_date=1&user=%7B%7D", bot_token=BOT_TOKEN, now=NOW))
    assert_unauthorized(lambda: verify_telegram_init_data(signed_init_data(user="broken"), bot_token=BOT_TOKEN, now=NOW))
    assert_unauthorized(
        lambda: verify_telegram_init_data(
            signed_init_data(auth_date=int(NOW.timestamp()) - TELEGRAM_INIT_DATA_MAX_AGE_SECONDS - 1),
            bot_token=BOT_TOKEN,
            now=NOW,
        )
    )
    assert verify_telegram_init_data(
        signed_init_data(auth_date=int(NOW.timestamp()) - TELEGRAM_INIT_DATA_MAX_AGE_SECONDS),
        bot_token=BOT_TOKEN,
        now=NOW,
    ) == 101
    assert verify_telegram_init_data(
        signed_init_data(auth_date=int(NOW.timestamp()) + 30), bot_token=BOT_TOKEN, now=NOW
    ) == 101
    assert_unauthorized(
        lambda: verify_telegram_init_data(
            signed_init_data(auth_date=int(NOW.timestamp()) + 31),
            bot_token=BOT_TOKEN,
            now=NOW,
        )
    )


@pytest.mark.asyncio
async def test_identity_is_derived_from_verified_telegram_proof(monkeypatch):
    user = SimpleNamespace(row_id=7, telegram_id=101, is_admin=False, is_approved=True)
    repository = SimpleNamespace(get_by_telegram_id=AsyncMock(return_value=user))
    monkeypatch.setattr("app.api.security.webapp_auth.UserRepository", lambda session: repository)
    monkeypatch.setattr("app.api.security.webapp_auth.settings.telegram_bot_token", BOT_TOKEN)
    identity = await resolve_webapp_identity(
        session=object(),
        platform="telegram",
        telegram_init_data=signed_init_data(auth_date=int(datetime.now(timezone.utc).timestamp())),
    )
    assert (identity.external_user_id, identity.user_row_id) == (101, 7)
    repository.get_by_telegram_id.assert_awaited_once_with(telegram_id=101)


@pytest.mark.asyncio
async def test_missing_invalid_and_vk_proof_fail_closed():
    for platform, proof in (("telegram", None), ("telegram", "bad"), ("vk", None)):
        with pytest.raises(HTTPException) as exc:
            await resolve_webapp_identity(
                session=object(), platform=platform, telegram_init_data=proof
            )
        assert exc.value.status_code == 401


def test_principal_authorization_distinguishes_401_and_403():
    unknown = SimpleNamespace(user_row_id=None, is_approved=False, is_admin=False)
    normal = SimpleNamespace(user_row_id=1, is_approved=True, is_admin=False)
    admin = SimpleNamespace(user_row_id=2, is_approved=True, is_admin=True)
    assert_unauthorized(lambda: require_authenticated_principal(unknown))
    with pytest.raises(HTTPException) as exc:
        require_admin_principal(normal)
    assert exc.value.status_code == 403
    assert require_admin_principal(admin) is admin


def _dependency_names(route):
    names = set()
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        names.add(getattr(dependency.call, "__name__", ""))
        pending.extend(dependency.dependencies)
    return names


def test_sensitive_routes_install_authentication_and_admin_dependencies():
    admin_routes = [
        route
        for route in [*users.router.routes, *registration.router.routes]
        if not route.path.endswith("/request")
    ]
    assert admin_routes
    assert all("require_admin_principal" in _dependency_names(route) for route in admin_routes)

    webapp_routes = [
        route
        for included in webapp.router.routes
        for route in included.original_router.routes
        if route.path != "/info/{section}/{topic}"
    ]
    assert webapp_routes
    assert all(
        {"get_webapp_identity", "require_authenticated_principal"} & _dependency_names(route)
        for route in webapp_routes
    )


@pytest.mark.asyncio
async def test_registration_uses_verified_identity_not_forged_payload(monkeypatch):
    created = SimpleNamespace(
        row_id=1,
        name="Alice",
        telegram_id=101,
        vk_id=None,
        notification_platform="tg",
        is_approved=False,
    )
    execute = AsyncMock(return_value=created)
    monkeypatch.setattr(registration, "UserRepository", lambda session: object())
    monkeypatch.setattr(
        registration,
        "RequestRegistrationUseCase",
        lambda repository: SimpleNamespace(execute=execute),
    )
    result = await registration.request_registration(
        payload=RegistrationRequest(name="Alice", telegram_id=999, vk_id=888),
        session=object(),
        identity=SimpleNamespace(external_user_id=101),
    )
    assert result.telegram_id == 101
    execute.assert_awaited_once_with(
        name="Alice",
        telegram_id=101,
        vk_id=None,
        tel_number=None,
        bank_name=None,
        notification_platform="tg",
    )
