import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./styles.css";
import { buildBootstrapUrl, getPlatformBootstrap, initPlatformWebApp } from "./services/platform";
import HomePage from "./pages/HomePage.vue";
import PokerPage from "./pages/PokerPage.vue";
import BetsPage from "./pages/BetsPage.vue";
import InfoPage from "./pages/InfoPage.vue";
import PlayersPage from "./pages/PlayersPage.vue";
import NextPokerPage from "./pages/NextPokerPage.vue";
import PlaceholderActionsPage from "./pages/PlaceholderActionsPage.vue";
import AdminPage from "./pages/AdminPage.vue";
import ApprovalRequiredPage from "./pages/ApprovalRequiredPage.vue";
import RoomPage from "./pages/RoomPage.vue";

const router = createRouter({
  history: createWebHistory("/webapp/"),
  routes: [
    { path: "/", component: HomePage },
    { path: "/poker", component: PokerPage, meta: { hideGlobalHome: true } },
    { path: "/bets", component: BetsPage, meta: { hideGlobalHome: true } },
    { path: "/info", component: InfoPage },
    { path: "/players", component: PlayersPage },
    { path: "/room", component: RoomPage },
    { path: "/next-poker", component: NextPokerPage, meta: { hideGlobalHome: true } },
    { path: "/next-poker/vote", component: PlaceholderActionsPage, props: { title: "✅ Проголосовать", theme: "poker" } },
    { path: "/next-poker/results", component: PlaceholderActionsPage, props: { title: "📊 Посмотреть результаты", theme: "poker" } },
    { path: "/poker/stat", component: PlaceholderActionsPage, props: { title: "🦑 Статистика покера", theme: "poker" } },
    { path: "/poker/history", component: PlaceholderActionsPage, props: { title: "⌛ История", theme: "poker" } },
    { path: "/bets/make", component: PlaceholderActionsPage, props: { title: "🐔 Сделать ставку", theme: "bets" } },
    { path: "/bets/pay", component: PlaceholderActionsPage, props: { title: "🤝 Оплатить ставку", theme: "bets" } },
    { path: "/bets/current", component: PlaceholderActionsPage, props: { title: "🎰 Текущие турниры", theme: "bets" } },
    { path: "/bets/stat", component: PlaceholderActionsPage, props: { title: "🍀 Статистика ставок", theme: "bets" } },
    { path: "/info/actions", component: PlaceholderActionsPage, props: { title: "Информация", theme: "info" } },
    { path: "/admin", component: AdminPage, meta: { hideGlobalHome: true } },
    { path: "/admin/create-poll", component: PlaceholderActionsPage, props: { title: "🗓 Создать опрос" } },
    { path: "/admin/start-poker", component: PlaceholderActionsPage, props: { title: "🎲 Старт покера" } },
    { path: "/admin/make-admin", component: PlaceholderActionsPage, props: { title: "👨🏻‍💻 Добавить админа" } },
    { path: "/approval-required", component: ApprovalRequiredPage }
  ]
});

router.beforeEach(async (to) => {
  if (to.path === "/" || to.path === "/approval-required") return true;

  const { platform, userId } = getPlatformBootstrap();
  if (userId === null || !Number.isFinite(userId)) return "/approval-required";
  const safeUserId = userId;

  try {
    const res = await fetch(buildBootstrapUrl(platform, safeUserId));
    if (!res.ok) return "/approval-required";
    const data = (await res.json()) as { is_approved?: boolean };
    if (!data.is_approved) return "/approval-required";
  } catch {
    return "/approval-required";
  }

  return true;
});

initPlatformWebApp();

createApp(App).use(router).mount("#app");
