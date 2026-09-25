from fastapi import APIRouter

from app.api.http.webapp_bootstrap import (
    router as bootstrap_router,
    webapp_bootstrap as webapp_bootstrap,
    webapp_bootstrap_by_platform as webapp_bootstrap_by_platform,
)
from app.api.http.webapp_info import (
    router as info_router,
    webapp_info_content as webapp_info_content,
)
from app.api.http.webapp_players import (
    router as players_router,
    webapp_players as webapp_players,
)
from app.api.http.webapp_profile import (
    router as profile_router,
    update_webapp_user_bank_by_platform as update_webapp_user_bank_by_platform,
    update_webapp_user_phone as update_webapp_user_phone,
    update_webapp_user_phone_by_platform as update_webapp_user_phone_by_platform,
    upload_webapp_user_photo as upload_webapp_user_photo,
    upload_webapp_user_photo_by_platform as upload_webapp_user_photo_by_platform,
)
from app.api.http.webapp_schemas import (
    WebAppBankUpdateRead as WebAppBankUpdateRead,
    WebAppBankUpdateWrite as WebAppBankUpdateWrite,
    WebAppBootstrapRead as WebAppBootstrapRead,
    WebAppInfoContentRead as WebAppInfoContentRead,
    WebAppPhoneUpdateRead as WebAppPhoneUpdateRead,
    WebAppPhoneUpdateWrite as WebAppPhoneUpdateWrite,
    WebAppPhotoUploadRead as WebAppPhotoUploadRead,
    WebAppPlayerCardRead as WebAppPlayerCardRead,
)

router = APIRouter(prefix="/api/webapp", tags=["webapp"])
router.include_router(bootstrap_router)
router.include_router(players_router)
router.include_router(info_router)
router.include_router(profile_router)
