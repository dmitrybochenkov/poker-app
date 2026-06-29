/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare global {
  interface TelegramWebAppThemeParams {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
  }

  interface TelegramWebApp {
    initData: string;
    initDataUnsafe?: Record<string, unknown>;
    colorScheme?: "light" | "dark";
    isExpanded?: boolean;
    platform?: string;
    themeParams: TelegramWebAppThemeParams;
    ready(): void;
    expand(): void;
    setHeaderColor?(color: string): void;
    setBackgroundColor?(color: string): void;
    MainButton?: {
      text: string;
      isVisible: boolean;
      show(): void;
      hide(): void;
      setText(text: string): void;
      onClick(cb: () => void): void;
      offClick(cb: () => void): void;
    };
    HapticFeedback?: {
      impactOccurred(style: "light" | "medium" | "heavy"): void;
      notificationOccurred(type: "error" | "success" | "warning"): void;
      selectionChanged(): void;
    };
  }

  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export {};
