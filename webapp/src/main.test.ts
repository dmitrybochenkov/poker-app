import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const bootstrapResponse = {
  ok: true,
  json: async () => ({
    is_registered: true,
    is_admin: false,
    is_approved: true,
    has_phone: true,
    has_active_poll: false,
    has_active_poker: false,
  }),
} as Response;

function telegramWebApp(overrides: Partial<TelegramWebApp> = {}): TelegramWebApp {
  return {
    initData: "signed-test-data",
    themeParams: {},
    ready: vi.fn(),
    expand: vi.fn(),
    ...overrides,
  };
}

let mountedApp: { unmount(): void } | null = null;

async function loadApplication(webApp: TelegramWebApp): Promise<void> {
  document.body.innerHTML = '<div id="app"></div>';
  window.history.replaceState({}, "", "/app/");
  window.Telegram = { WebApp: webApp };
  const application = await import("./main");
  mountedApp = application.mountedApp;
  if (mountedApp) {
    await application.router.isReady();
  }
  await nextTick();
  await nextTick();
}

describe("WebApp bootstrap", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bootstrapResponse));
    delete (window as Window & { vkBridge?: unknown }).vkBridge;
  });

  afterEach(() => {
    mountedApp?.unmount();
    mountedApp = null;
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
    delete window.Telegram;
  });

  it("mounts HomePage, initializes Telegram and attempts bootstrap without VK Bridge", async () => {
    const webApp = telegramWebApp();

    await loadApplication(webApp);

    expect(webApp.ready).toHaveBeenCalledOnce();
    expect(webApp.expand).toHaveBeenCalledOnce();
    expect(document.querySelector("#app")?.textContent).toContain("Покер рум");
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/webapp/me/bootstrap",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(document.querySelector('script[src*="vkontakte"]')).toBeNull();
  });

  it("renders a visible fallback when Telegram initialization throws", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const webApp = telegramWebApp({
      ready: vi.fn(() => {
        throw new Error("SDK initialization failed");
      }),
    });

    await expect(loadApplication(webApp)).resolves.toBeUndefined();

    expect(document.querySelector("#app")?.textContent).toContain(
      "Не удалось запустить приложение. Попробуйте открыть его снова.",
    );
  });

  it("does not synchronously load VK Bridge and prevents source-tree build output", () => {
    const html = readFileSync("index.html", "utf8");
    const packageJson = JSON.parse(
      readFileSync("package.json", "utf8"),
    ) as { scripts: { build: string } };
    const tsconfig = JSON.parse(
      readFileSync("tsconfig.json", "utf8"),
    ) as { compilerOptions: { noEmit?: boolean } };

    expect(html).not.toContain("unpkg.com/@vkontakte/vk-bridge");
    expect(packageJson.scripts.build).not.toContain("vue-tsc -b");
    expect(tsconfig.compilerOptions.noEmit).toBe(true);
  });

  it("loads and initializes VK Bridge only for a VK launch", async () => {
    vi.resetModules();
    delete window.Telegram;
    window.history.replaceState({}, "", "/app/?vk_platform=desktop_web");
    const send = vi.fn().mockResolvedValue(undefined);
    const platform = await import("./services/platform");

    platform.initPlatformWebApp();

    const script = document.querySelector<HTMLScriptElement>(
      'script[src="https://unpkg.com/@vkontakte/vk-bridge/dist/browser.min.js"]',
    );
    expect(script).not.toBeNull();
    (window as Window & { vkBridge?: { send: typeof send } }).vkBridge = { send };
    script?.dispatchEvent(new Event("load"));
    await vi.waitFor(() => expect(send).toHaveBeenCalledWith("VKWebAppInit"));
    script?.remove();
  });
});
