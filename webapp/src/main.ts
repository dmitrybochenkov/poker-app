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
import { buildInfoContentUrl } from "./services/platform";

const infoMainMenu = [
  { label: "ℹ️💍 Про покер", to: "/info/poker" },
  { label: "ℹ️🍀 Про ставки", to: "/info/bets" },
  { label: "🏠 На главную", to: "/" },
];

const pokerInfoMenu = [
  { label: "ℹ️🌟 Ачивки для покера", to: "/info/poker/achievements" },
  { label: "ℹ️📊 Показатели для покера", to: "/info/poker/metrics" },
  { label: "⌛ История", to: "/poker/history" },
  { label: "🏠 На главную", to: "/" },
];

const betsInfoMenu = [
  { label: "📖 Правила", to: "/info/bets/rules" },
  { label: "ℹ️🌟 Ачивки для ставок", to: "/info/bets/achievements" },
  { label: "ℹ️📊 Показатели для ставок", to: "/info/bets/metrics" },
  { label: "🏠 На главную", to: "/" },
];

const bettingCurrentMenu = [
  { label: "💰 Регулярный турнир", to: "/bets/current/regular" },
  { label: "🎄💰 Годовой турнир", to: "/bets/current/year" },
  { label: "🏠 На главную", to: "/" },
];

const router = createRouter({
  history: createWebHistory("/app/"),
  routes: [
    { path: "/", component: HomePage },
    { path: "/poker", component: PokerPage, meta: { hideGlobalHome: true } },
    { path: "/bets", component: BetsPage, meta: { hideGlobalHome: true } },
    { path: "/info", component: InfoPage, meta: { hideGlobalHome: true } },
    { path: "/players", component: PlayersPage },
    { path: "/room", component: RoomPage },
    { path: "/next-poker", component: NextPokerPage, meta: { hideGlobalHome: true } },
    { path: "/next-poker/vote", component: PlaceholderActionsPage, props: { title: "✅ Проголосовать", theme: "poker" } },
    { path: "/next-poker/results", component: PlaceholderActionsPage, props: { title: "📊 Посмотреть результаты", theme: "poker" } },
    { path: "/poker/stat", component: PlaceholderActionsPage, props: { title: "🦑 Статистика покера", theme: "poker" } },
    { path: "/poker/history", component: PlaceholderActionsPage, props: { title: "⌛ История", theme: "poker" } },
    { path: "/bets/make", component: PlaceholderActionsPage, props: { title: "🐔 Сделать ставку", theme: "bets" } },
    { path: "/bets/pay", component: PlaceholderActionsPage, props: { title: "🤝 Оплатить ставку", theme: "bets" } },
    {
      path: "/bets/current",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: {
        title: "🎰 Текущие турниры",
        theme: "bets",
        menuItems: bettingCurrentMenu,
      },
    },
    {
      path: "/bets/current/regular",
      component: PlaceholderActionsPage,
      props: { title: "💰 Регулярный турнир", theme: "bets" },
    },
    {
      path: "/bets/current/year",
      component: PlaceholderActionsPage,
      props: { title: "🎄💰 Годовой турнир", theme: "bets" },
    },
    { path: "/bets/stat", component: PlaceholderActionsPage, props: { title: "🍀 Статистика ставок", theme: "bets" } },
    {
      path: "/info/poker",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: {
        title: "ℹ️💍 Про покер",
        theme: "info",
        contentApi: buildInfoContentUrl("poker", "root"),
        menuItems: pokerInfoMenu,
      },
    },
    {
      path: "/info/bets",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: {
        title: "ℹ️🍀 Про ставки",
        theme: "info",
        contentApi: buildInfoContentUrl("bets", "root"),
        menuItems: betsInfoMenu,
      },
    },
    {
      path: "/info/poker/achievements",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: { title: "ℹ️🌟 Ачивки для покера", theme: "info", contentApi: buildInfoContentUrl("poker", "achievements"), menuItems: pokerInfoMenu },
    },
    {
      path: "/info/poker/metrics",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: { title: "ℹ️📊 Показатели для покера", theme: "info", contentApi: buildInfoContentUrl("poker", "metrics"), menuItems: pokerInfoMenu },
    },
    {
      path: "/info/bets/rules",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: { title: "📖 Правила", theme: "info", contentApi: buildInfoContentUrl("bets", "rules"), menuItems: betsInfoMenu },
    },
    {
      path: "/info/bets/achievements",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: { title: "ℹ️🌟 Ачивки для ставок", theme: "info", contentApi: buildInfoContentUrl("bets", "achievements"), menuItems: betsInfoMenu },
    },
    {
      path: "/info/bets/metrics",
      component: PlaceholderActionsPage,
      meta: { hideGlobalHome: true },
      props: { title: "ℹ️📊 Показатели для ставок", theme: "info", contentApi: buildInfoContentUrl("bets", "metrics"), menuItems: betsInfoMenu },
    },
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
