# Emoji Assets for Stat PNG

Put custom emoji PNG files here to improve stat table rendering quality.

## File naming

Each file name is based on Unicode codepoint(s) in lowercase hex:

- `🐴` -> `1f434.png`
- `🐮` -> `1f42e.png`
- `🍀` -> `1f340.png`
- `🦑` -> `1f991.png`

If an asset is found, stat rendering uses this PNG instead of font emoji.
If not found, renderer falls back to the system emoji font.

## Recommended source size

- 128x128 or 256x256 PNG
- Transparent background
- Consistent style across icons

## Scope

This is currently used by stat image rendering in:

- Poker stat export PNG
- Betting stat export PNG
