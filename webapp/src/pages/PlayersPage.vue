<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="(player, index) in players" :key="player.player_id" class="player-card">
        <div class="player-card-art" :class="[cardTheme(index), cardRole(index)]">
          <div class="card-corner top-left" :class="cardTheme(index)">
            <span class="rank">{{ cardRank(index) }}</span>
            <span v-if="showSuit(index)" class="suit">{{ cardSuit(index) }}</span>
            <span v-else class="joker-mark">{{ jokerMark(index) }}</span>
          </div>
          <div class="player-card-figure" :class="[cardRole(index), cardTheme(index)]">
            <div v-if="cardRole(index) === 'joker'" class="jester-crown">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div v-else-if="cardRole(index) === 'king'" class="figure-crown">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div v-else-if="cardRole(index) === 'queen'" class="figure-hair"></div>
            <div v-else class="figure-cap"></div>
            <div class="figure-head"></div>
            <div class="figure-neck"></div>
            <div class="figure-shoulders"></div>
            <div class="figure-emblem" v-if="showSuit(index)">{{ cardSuit(index) }}</div>
            <div class="figure-joker-label" v-else>JOKER</div>
          </div>
        </div>
        <div class="player-meta">
          <h3>{{ player.name }}</h3>
        </div>
        <div class="player-stats">
          <div class="stat-cell">
            <span class="k">Профит</span>
            <span class="v">{{ player.profit }}</span>
          </div>
          <div class="stat-cell">
            <span class="k">Игр</span>
            <span class="v">{{ player.games }}</span>
          </div>
        </div>
        <div class="player-card-actions">
          <button class="mini-card-btn" type="button">Добавить фото</button>
          <button class="mini-card-btn" type="button">Добавить телефон</button>
        </div>
      </article>
    </div>
    <p v-if="!loading && players.length > 1" class="players-hint">Свайп влево/вправо</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

type PlayerCardApi = {
  player_id: number;
  name: string;
  games: number;
  profit_rub: number;
};

type PlayerCard = {
  player_id: number;
  name: string;
  games: number;
  profit: string;
};

const loading = ref(true);
const players = ref<PlayerCard[]>([]);
const deck = [
  { title: "Черный джокер", role: "joker", rank: "JKR", suit: "BLACK" },
  { title: "Красный джокер", role: "joker", rank: "JKR", suit: "RED" },
  { title: "Король треф", role: "king", rank: "K", suit: "♣" },
  { title: "Король пик", role: "king", rank: "K", suit: "♠" },
  { title: "Король червей", role: "king", rank: "K", suit: "♥" },
  { title: "Король бубен", role: "king", rank: "K", suit: "♦" },
  { title: "Дама треф", role: "queen", rank: "Q", suit: "♣" },
  { title: "Дама пик", role: "queen", rank: "Q", suit: "♠" },
  { title: "Дама червей", role: "queen", rank: "Q", suit: "♥" },
  { title: "Дама бубен", role: "queen", rank: "Q", suit: "♦" },
  { title: "Валет треф", role: "jack", rank: "J", suit: "♣" },
  { title: "Валет пик", role: "jack", rank: "J", suit: "♠" },
  { title: "Валет червей", role: "jack", rank: "J", suit: "♥" },
  { title: "Валет бубен", role: "jack", rank: "J", suit: "♦" },
];

function formatRub(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toLocaleString("ru-RU")} ₽`;
}

function cardTitle(index: number): string {
  return deck[index]?.title ?? deck[0].title;
}

function cardRole(index: number): string {
  return deck[index]?.role ?? "jack";
}

function cardRank(index: number): string {
  return deck[index]?.rank ?? "J";
}

function cardSuit(index: number): string {
  return deck[index]?.suit ?? "♣";
}

function showSuit(index: number): boolean {
  return !["BLACK", "RED"].includes(cardSuit(index));
}

function jokerMark(index: number): string {
  return cardSuit(index) === "RED" ? "★" : "✦";
}

function cardTheme(index: number): string {
  const suit = cardSuit(index);
  return suit === "♥" || suit === "♦" || suit === "RED" ? "theme-red" : "theme-black";
}

onMounted(async () => {
  try {
    const res = await fetch("/api/webapp/players");
    if (!res.ok) return;
    const data = (await res.json()) as PlayerCardApi[];
    players.value = data.slice(0, 14).map((item) => ({
      player_id: item.player_id,
      name: item.name,
      games: item.games,
      profit: formatRub(item.profit_rub),
    }));
  } finally {
    loading.value = false;
  }
});
</script>
