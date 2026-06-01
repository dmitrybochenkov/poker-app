import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./styles.css";
import { initTelegramWebApp } from "./services/telegram";
import HomePage from "./pages/HomePage.vue";
import PokerPage from "./pages/PokerPage.vue";
import BetsPage from "./pages/BetsPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HomePage },
    { path: "/poker", component: PokerPage },
    { path: "/bets", component: BetsPage }
  ]
});

initTelegramWebApp();

createApp(App).use(router).mount("#app");
