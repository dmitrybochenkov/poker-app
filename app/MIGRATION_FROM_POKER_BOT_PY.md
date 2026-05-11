# Migration Notes: `poker-bot-py` -> `poker-app`

This file tracks what is already migrated and what is still pending.

## Already moved

- Legacy texts:
  - `app/bot/shared/texts/legacy_texts_user.py`
  - `app/bot/shared/texts/legacy_texts_admin.py`
  - `app/bot/shared/texts/legacy_texts.py`
- Legacy buttons:
  - `app/bot/shared/buttons/legacy_buttons.py`
- Legacy reply keyboards:
  - `app/bot/shared/keyboards/legacy_keyboards.py`
- Use-case skeletons for old service areas:
  - `app/application/use_cases/poker/`

## Why this shape

- Current registration flow stays stable.
- Legacy content is available in one place and can be ported incrementally.
- We can migrate service-by-service into use-cases without breaking runtime.

## Next steps

1. Replace legacy text/button usages in handlers with current `Text/Buttons` keys where needed.
2. Implement `PlayerUseCases` and `PokerTableUseCases` first (they are the critical path).
3. Add platform-agnostic notification ports and bind TG/VK adapters.
4. Port betting/stat/info flows from legacy service methods into concrete use-cases.
