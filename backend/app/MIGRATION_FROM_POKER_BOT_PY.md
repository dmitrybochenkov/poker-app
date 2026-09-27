# Migration Notes: `poker-bot-py` -> `poker-app`

This file tracks what is already migrated and what is still pending.

## Already moved

- Legacy texts/buttons/keyboards were migrated and removed from runtime tree.
- Concrete poker use cases live in `app/application/use_cases/poker/`.

## Why this shape

- Current registration flow stays stable.
- We can migrate service-by-service into use-cases without breaking runtime.

## Next steps

1. Replace legacy text/button usages in handlers with current `Text/Buttons` keys where needed.
2. Add platform-agnostic notification ports and bind TG/VK adapters where a migrated flow requires them.
3. Port remaining legacy flows into concrete use cases incrementally.
