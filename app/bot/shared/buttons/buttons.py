from app.bot.shared.buttons.buttons_inline import AdminInlineBtns, BettingInlineBtns, RegistrationInlineBtns
from app.bot.shared.buttons.buttons_reply import (
  AdminMainBtns,
  AdminRoomBtns,
  AdminRoomCorrectBtns,
  BettingBtns,
  BettingCurrentBtns,
  BettingInfoBtns,
  MainBtns,
  NewUserBtns,
  PokerBtns,
  PokerInfoBtns,
  RoomBtns,
)


class Buttons:
  new_user = NewUserBtns
  registration_inline = RegistrationInlineBtns
  admin_inline = AdminInlineBtns
  betting_inline = BettingInlineBtns
  main = MainBtns
  admin_main = AdminMainBtns
  room = RoomBtns
  admin_room = AdminRoomBtns
  admin_room_correct = AdminRoomCorrectBtns
  betting = BettingBtns
  betting_current = BettingCurrentBtns
  bettingInfo = BettingInfoBtns
  poker = PokerBtns
  pokerInfo = PokerInfoBtns
