from app.bot.shared.buttons.legacy_buttons import LegacyBtns
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs


def _labels(enum_cls) -> list[str]:
  return [button.value for button in enum_cls]


class LegacyReplyKbs:
  newUserVk = ReplyKbs.make_vk(_labels(LegacyBtns.newUser), adjust=1)
  mainVk = ReplyKbs.make_vk(_labels(LegacyBtns.main), adjust=1)
  mainAdminVk = ReplyKbs.make_vk(_labels(LegacyBtns.adminMain), adjust=1)
  roomVk = ReplyKbs.make_vk(_labels(LegacyBtns.room), adjust=1)
  roomAdminVk = ReplyKbs.make_vk(_labels(LegacyBtns.adminRoom), adjust=1)
  bettingVk = ReplyKbs.make_vk(_labels(LegacyBtns.betting), adjust=1)
  bettingCurrentVk = ReplyKbs.make_vk(_labels(LegacyBtns.bettingCurrent), adjust=1)
  bettingInfoVk = ReplyKbs.make_vk(_labels(LegacyBtns.bettingInfo), adjust=1)
  pokerStatVk = ReplyKbs.make_vk(_labels(LegacyBtns.poker), adjust=1)
  pokerInfoVk = ReplyKbs.make_vk(_labels(LegacyBtns.pokerInfo), adjust=1)

  newUserTg = ReplyKbs.make_tg(_labels(LegacyBtns.newUser), adjust=1, resize=True)
  mainTg = ReplyKbs.make_tg(_labels(LegacyBtns.main), adjust=1, resize=True)
  mainAdminTg = ReplyKbs.make_tg(_labels(LegacyBtns.adminMain), adjust=1, resize=True)
  roomTg = ReplyKbs.make_tg(_labels(LegacyBtns.room), adjust=1, resize=True)
  roomAdminTg = ReplyKbs.make_tg(_labels(LegacyBtns.adminRoom), adjust=1, resize=True)
  bettingTg = ReplyKbs.make_tg(_labels(LegacyBtns.betting), adjust=1, resize=True)
  bettingCurrentTg = ReplyKbs.make_tg(_labels(LegacyBtns.bettingCurrent), adjust=1, resize=True)
  bettingInfoTg = ReplyKbs.make_tg(_labels(LegacyBtns.bettingInfo), adjust=1, resize=True)
  pokerStatTg = ReplyKbs.make_tg(_labels(LegacyBtns.poker), adjust=1, resize=True)
  pokerInfoTg = ReplyKbs.make_tg(_labels(LegacyBtns.pokerInfo), adjust=1, resize=True)
