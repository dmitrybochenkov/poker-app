from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
  waiting_for_played_before_answer = State()
  waiting_for_new_name = State()
  waiting_for_registration_platform_choice = State()
  waiting_for_optional_details_action = State()
  waiting_for_bank_name = State()
  waiting_for_phone = State()
  waiting_for_corrected_name = State()
  waiting_for_bet_amount = State()


class AdminPokerState(StatesGroup):
  waiting_for_cashout_amount = State()
  waiting_for_new_player_name = State()
