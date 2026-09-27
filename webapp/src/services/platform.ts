import { getTelegramWebApp, initTelegramWebApp } from "./telegram";

export type WebAppPlatform = "telegram" | "vk" | "web";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function inferApiBaseUrl(): string {
  const configured = String(import.meta.env.VITE_API_BASE_URL ?? "").trim();
  if (configured) {
    return trimTrailingSlash(configured);
  }

  const { protocol, hostname, origin } = window.location;
  if (hostname.startsWith("app.")) {
    return `${protocol}//api.${hostname.slice(4)}`;
  }

  return trimTrailingSlash(origin);
}

function buildApiUrl(path: string): string {
  return `${inferApiBaseUrl()}${path}`;
}

function readVkUserIdFromQuery(): number | null {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("vk_user_id");
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

type VkBridgeLike = {
  send(method: string, params?: Record<string, unknown>): Promise<unknown>;
};

function getVkBridge(): VkBridgeLike | null {
  const bridge = (window as Window & { vkBridge?: VkBridgeLike }).vkBridge;
  return bridge && typeof bridge.send === "function" ? bridge : null;
}

export function detectPlatform(): WebAppPlatform {
  if (getTelegramWebApp()) {
    return "telegram";
  }
  const params = new URLSearchParams(window.location.search);
  if (readVkUserIdFromQuery() !== null || params.has("vk_platform") || params.has("sign")) {
    return "vk";
  }
  return "web";
}

export function initPlatformWebApp(): void {
  const platform = detectPlatform();
  if (platform === "telegram") {
    initTelegramWebApp();
    return;
  }

  if (platform === "vk") {
    void getVkBridge()
      ?.send("VKWebAppInit")
      .catch(() => {
        // VK can still pass launch params in the URL even if bridge init fails.
      });
  }
}

export function authenticatedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const platform = detectPlatform();
  const headers = new Headers(init.headers);
  headers.set("X-WebApp-Platform", platform);
  if (platform === "telegram") {
    headers.set("X-Telegram-Init-Data", getTelegramWebApp()?.initData ?? "");
  }
  return fetch(input, { ...init, headers });
}

export function buildBootstrapUrl(): string {
  return buildApiUrl("/api/webapp/me/bootstrap");
}

export function buildPlayersUrl(): string {
  return buildApiUrl("/api/webapp/players");
}

export function buildPhotoUploadUrl(): string {
  return buildApiUrl("/api/webapp/me/photo");
}

export function buildPhoneUpdateUrl(): string {
  return buildApiUrl("/api/webapp/me/phone");
}

export function buildBankUpdateUrl(): string {
  return buildApiUrl("/api/webapp/me/bank");
}

export function buildInfoContentUrl(section: "poker" | "bets", topic: "rules" | "achievements" | "metrics" | "root"): string {
  return buildApiUrl(`/api/webapp/info/${section}/${topic}`);
}
