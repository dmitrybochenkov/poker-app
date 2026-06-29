import { getTelegramWebApp, initTelegramWebApp } from "./telegram";

export type WebAppPlatform = "telegram" | "vk" | "web";

export type PlatformBootstrap = {
  platform: WebAppPlatform;
  userId: number | null;
};

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

export function getCurrentPlatformUserId(): number | null {
  const tgUserId = Number((getTelegramWebApp()?.initDataUnsafe?.user as { id?: number } | undefined)?.id);
  if (Number.isFinite(tgUserId)) {
    return tgUserId;
  }
  return readVkUserIdFromQuery();
}

export function getPlatformBootstrap(): PlatformBootstrap {
  return {
    platform: detectPlatform(),
    userId: getCurrentPlatformUserId(),
  };
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

export function buildBootstrapUrl(platform: WebAppPlatform, userId: number): string {
  return buildApiUrl(`/api/webapp/bootstrap/${platform}/${userId}`);
}

export function buildPlayersUrl(): string {
  return buildApiUrl("/api/webapp/players");
}

export function buildPhotoUploadUrl(platform: WebAppPlatform, userId: number): string {
  return buildApiUrl(`/api/webapp/users/${platform}/${userId}/photo`);
}

export function buildPhoneUpdateUrl(platform: WebAppPlatform, userId: number): string {
  return buildApiUrl(`/api/webapp/users/${platform}/${userId}/phone`);
}

export function buildBankUpdateUrl(platform: WebAppPlatform, userId: number): string {
  return buildApiUrl(`/api/webapp/users/${platform}/${userId}/bank`);
}

export function buildInfoContentUrl(section: "poker" | "bets", topic: "rules" | "achievements" | "metrics" | "root"): string {
  return buildApiUrl(`/api/webapp/info/${section}/${topic}`);
}
