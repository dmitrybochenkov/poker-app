<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="(player, index) in players" :key="player.player_id" class="player-card">
        <div class="card-corner top-left" :class="suitClass(index)">
          <span class="rank">{{ cardRank(index) }}</span>
          <span v-if="showSuit(index)" class="suit">{{ cardSuit(index) }}</span>
        </div>
        <div class="face-card">
          <div class="face-card-inner">
            <div v-if="showSuit(index)" class="face-suit" :class="suitClass(index)">{{ cardSuit(index) }}</div>
            <div class="face-center" :class="suitClass(index)">
              <div class="face-center-rank">{{ cardRank(index) }}</div>
              <div v-if="showSuit(index)" class="face-center-suit">{{ cardSuit(index) }}</div>
              <div v-else class="face-center-joker">JOKER</div>
            </div>
            <div class="player-photo-zone">
              <div class="player-photo-placeholder"></div>
            </div>
          </div>
        </div>
        <div class="card-divider" aria-hidden="true"></div>
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
  { rank: "JKR", suit: "RED" },
  { rank: "JKR", suit: "BLACK" },
  { rank: "K", suit: "♣" },
  { rank: "K", suit: "♠" },
  { rank: "K", suit: "♥" },
  { rank: "K", suit: "♦" },
  { rank: "Q", suit: "♣" },
  { rank: "Q", suit: "♠" },
  { rank: "Q", suit: "♥" },
  { rank: "Q", suit: "♦" },
  { rank: "J", suit: "♣" },
  { rank: "J", suit: "♠" },
  { rank: "J", suit: "♥" },
  { rank: "J", suit: "♦" },
];

function formatRub(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toLocaleString("ru-RU")} ₽`;
}

function cardRank(index: number): string {
  return deck[index]?.rank ?? "J";
}

function cardSuit(index: number): string {
  return deck[index]?.suit ?? "♣";
}

function suitClass(index: number): string {
  const suit = cardSuit(index);
  return suit === "♥" || suit === "♦" || suit === "RED" ? "suit-red" : "suit-black";
}

function showSuit(index: number): boolean {
  const suit = cardSuit(index);
  return suit !== "RED" && suit !== "BLACK";
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
