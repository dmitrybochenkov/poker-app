# Migration Notes: `poker-bot-py` -> `poker-app`

This file tracks what is already migrated and what is still pending.

## Already moved

- Legacy texts/buttons/keyboards were migrated and removed from runtime tree.
- Use-case skeletons for old service areas:
  - `app/application/use_cases/poker/`

## Why this shape

- Current registration flow stays stable.
- We can migrate service-by-service into use-cases without breaking runtime.

## Next steps

1. Replace legacy text/button usages in handlers with current `Text/Buttons` keys where needed.
2. Implement `PlayerUseCases` and `PokerTableUseCases` first (they are the critical path).
3. Add platform-agnostic notification ports and bind TG/VK adapters.
4. Port betting/stat/info flows from legacy service methods into concrete use-cases.
