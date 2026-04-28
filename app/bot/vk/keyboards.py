import json

from app.bot.shared.buttons import Buttons

main_keyboard = json.dumps(
  {
    "one_time": False,
    "buttons": [
      [
        {
          "action": {
            "type": "text",
            "label": Buttons.new_user.REGISTRATION.value,
          },
          "color": "primary",
        }
      ]
    ],
  },
  ensure_ascii=False,
)
