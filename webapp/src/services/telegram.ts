function applyThemeFromTelegram(webApp: TelegramWebApp): void {
  const root = document.documentElement;
  const theme = webApp.themeParams ?? {};

  if (theme.bg_color) {
    root.style.setProperty("--tg-bg", theme.bg_color);
  }
  if (theme.text_color) {
    root.style.setProperty("--tg-text", theme.text_color);
  }
  if (theme.hint_color) {
    root.style.setProperty("--tg-hint", theme.hint_color);
  }
  if (theme.button_color) {
    root.style.setProperty("--tg-accent", theme.button_color);
  }
  if (theme.button_text_color) {
    root.style.setProperty("--tg-accent-text", theme.button_text_color);
  }
}

export function initTelegramWebApp(): void {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  webApp.ready();
  webApp.expand();
  applyThemeFromTelegram(webApp);
}

export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}
