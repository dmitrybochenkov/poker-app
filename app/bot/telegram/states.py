from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
  waiting_for_played_before_answer = State()
  waiting_for_new_name = State()
  waiting_for_registration_existing_row_id = State()
  waiting_for_existing_row_id = State()
  waiting_for_corrected_name = State()
