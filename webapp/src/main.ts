import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./styles.css";
import { initTelegramWebApp } from "./services/telegram";
import HomePage from "./pages/HomePage.vue";
import PokerPage from "./pages/PokerPage.vue";
import BetsPage from "./pages/BetsPage.vue";
import InfoPage from "./pages/InfoPage.vue";
import PlayersPage from "./pages/PlayersPage.vue";
import NextPokerPage from "./pages/NextPokerPage.vue";
import PlaceholderActionsPage from "./pages/PlaceholderActionsPage.vue";

const router = createRouter({
  history: createWebHistory("/webapp/"),
  routes: [
    { path: "/", component: HomePage },
    { path: "/poker", component: PokerPage },
    { path: "/bets", component: BetsPage },
    { path: "/info", component: InfoPage },
    { path: "/players", component: PlayersPage },
    { path: "/next-poker", component: NextPokerPage },
    { path: "/poker/actions", component: PlaceholderActionsPage, props: { title: "Про покер" } },
    { path: "/bets/actions", component: PlaceholderActionsPage, props: { title: "Про ставки" } },
    { path: "/info/actions", component: PlaceholderActionsPage, props: { title: "Информация" } },
    { path: "/admin", component: PlaceholderActionsPage, props: { title: "Админ панель" } }
  ]
});

initTelegramWebApp();

createApp(App).use(router).mount("#app");
