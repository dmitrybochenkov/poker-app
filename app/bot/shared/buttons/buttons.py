from app.bot.shared.buttons.buttons_inline import AdminInlineBtns, RegistrationInlineBtns
from app.bot.shared.buttons.buttons_reply import (
  AdminMainBtns,
  AdminRoomBtns,
  BettingBtns,
  BettingCurrentBtns,
  BettingInfoBtns,
  MainBtns,
  NewUserBtns,
  PokerBtns,
  PokerInfoBtns,
  RegistrationFlowBtns,
  RoomBtns,
)


class Buttons:
  new_user = NewUserBtns
  registration_flow = RegistrationFlowBtns
  registration_inline = RegistrationInlineBtns
  admin_inline = AdminInlineBtns
  main = MainBtns
  admin_main = AdminMainBtns
  room = RoomBtns
  admin_room = AdminRoomBtns
  betting = BettingBtns
  betting_current = BettingCurrentBtns
  bettingInfo = BettingInfoBtns
  poker = PokerBtns
  pokerInfo = PokerInfoBtns
