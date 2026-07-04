vk_user_states: dict[int, str] = {}
vk_user_contexts: dict[int, dict[str, str]] = {}

WAITING_FOR_PLAYED_BEFORE = "waiting_for_played_before"
WAITING_FOR_NEW_NAME = "waiting_for_new_name"
WAITING_FOR_ADMIN_CORRECTED_NAME = "waiting_for_admin_corrected_name"
WAITING_FOR_OPTIONAL_DETAILS_ACTION = "waiting_for_optional_details_action"
WAITING_FOR_OPTIONAL_BANK = "waiting_for_optional_bank"
WAITING_FOR_OPTIONAL_PHONE = "waiting_for_optional_phone"
WAITING_FOR_ADMIN_CASHOUT_AMOUNT = "waiting_for_admin_cashout_amount"
WAITING_FOR_ADMIN_NEW_PLAYER_NAME = "waiting_for_admin_new_player_name"
WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT = "waiting_for_admin_buyin_correct_amount"
WAITING_FOR_BET_AMOUNT = "waiting_for_bet_amount"
WAITING_FOR_BET_PAYMENT_RECEIPT = "waiting_for_bet_payment_receipt"
WAITING_FOR_POLL_CUSTOM_DAY = "waiting_for_poll_custom_day"
