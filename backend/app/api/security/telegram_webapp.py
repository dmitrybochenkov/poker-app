import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from fastapi import HTTPException, status


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication proof")


def verify_telegram_init_data(
    raw_init_data: str,
    *,
    bot_token: str,
    now: datetime | None = None,
    max_age_seconds: int = 3600,
    future_skew_seconds: int = 30,
) -> int:
    if not raw_init_data or not bot_token:
        raise _unauthorized()
    try:
        pairs = parse_qsl(raw_init_data, keep_blank_values=True, strict_parsing=True)
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError
        values = dict(pairs)
        supplied_hash = values.pop("hash")
        auth_date = int(values["auth_date"])
        user_data = json.loads(values["user"])
        raw_user_id = user_data["id"]
        if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, int) or raw_user_id <= 0:
            raise ValueError
        user_id = raw_user_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise _unauthorized() from error

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash):
        raise _unauthorized()

    current = int((now or datetime.now(timezone.utc)).timestamp())
    age = current - auth_date
    if age > max_age_seconds or age < -future_skew_seconds:
        raise _unauthorized()
    return user_id
