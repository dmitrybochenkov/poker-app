from fastapi import APIRouter

from app.api.http.webapp_bootstrap import (
    router as bootstrap_router,
)
from app.api.http.webapp_bootstrap import (
    webapp_bootstrap_by_platform as webapp_bootstrap_by_platform,
)
from app.api.http.webapp_info import (
    router as info_router,
)
from app.api.http.webapp_info import (
    webapp_info_content as webapp_info_content,
)
from app.api.http.webapp_players import (
    router as players_router,
)
from app.api.http.webapp_players import (
    webapp_players as webapp_players,
)
from app.api.http.webapp_profile import (
    router as profile_router,
)
from app.api.http.webapp_profile import (
    update_webapp_user_bank_by_platform as update_webapp_user_bank_by_platform,
)
from app.api.http.webapp_profile import (
    update_webapp_user_phone_by_platform as update_webapp_user_phone_by_platform,
)
from app.api.http.webapp_profile import (
    upload_webapp_user_photo_by_platform as upload_webapp_user_photo_by_platform,
)
from app.api.http.webapp_schemas import (
    WebAppBankUpdateRead as WebAppBankUpdateRead,
)
from app.api.http.webapp_schemas import (
    WebAppBankUpdateWrite as WebAppBankUpdateWrite,
)
from app.api.http.webapp_schemas import (
    WebAppBootstrapRead as WebAppBootstrapRead,
)
from app.api.http.webapp_schemas import (
    WebAppInfoContentRead as WebAppInfoContentRead,
)
from app.api.http.webapp_schemas import (
    WebAppPhoneUpdateRead as WebAppPhoneUpdateRead,
)
from app.api.http.webapp_schemas import (
    WebAppPhoneUpdateWrite as WebAppPhoneUpdateWrite,
)
from app.api.http.webapp_schemas import (
    WebAppPhotoUploadRead as WebAppPhotoUploadRead,
)
from app.api.http.webapp_schemas import (
    WebAppPlayerCardRead as WebAppPlayerCardRead,
)

router = APIRouter(prefix="/api/webapp", tags=["webapp"])
router.include_router(bootstrap_router)
router.include_router(players_router)
router.include_router(info_router)
router.include_router(profile_router)
