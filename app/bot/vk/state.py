vk_user_states: dict[int, str] = {}
vk_user_contexts: dict[int, dict[str, str]] = {}

WAITING_FOR_PLAYED_BEFORE = "waiting_for_played_before"
WAITING_FOR_NEW_NAME = "waiting_for_new_name"
WAITING_FOR_EXISTING_ROW_ID = "waiting_for_existing_row_id"
