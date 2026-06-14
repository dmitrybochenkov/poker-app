<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="(player, index) in players" :key="player.player_id" class="player-card">
        <div class="player-card-art" :class="[cardTheme(index), cardRole(index)]">
          <div class="card-corner top-left" :class="cardTheme(index)">
            <template v-if="cardRole(index) === 'joker'">
              <span class="joker-rank-vertical">JOKER</span>
            </template>
            <template v-else>
              <span class="rank">{{ cardRank(index) }}</span>
              <span class="suit">{{ cardSuit(index) }}</span>
            </template>
          </div>
          <div class="player-card-figure" :class="[cardRole(index), cardTheme(index)]"></div>
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
  { title: "Туз пик", role: "ace", rank: "A", suit: "♠" },
  { title: "Король пик", role: "king", rank: "K", suit: "♠" },
  { title: "Дама пик", role: "queen", rank: "Q", suit: "♠" },
  { title: "Валет пик", role: "jack", rank: "J", suit: "♠" },
  { title: "Десятка пик", role: "number", rank: "10", suit: "♠" },
  { title: "Девятка пик", role: "number", rank: "9", suit: "♠" },
  { title: "Восьмерка пик", role: "number", rank: "8", suit: "♠" },
  { title: "Семерка пик", role: "number", rank: "7", suit: "♠" },
  { title: "Шестерка пик", role: "number", rank: "6", suit: "♠" },
  { title: "Пятерка пик", role: "number", rank: "5", suit: "♠" },
  { title: "Четверка пик", role: "number", rank: "4", suit: "♠" },
  { title: "Тройка пик", role: "number", rank: "3", suit: "♠" },
  { title: "Двойка пик", role: "number", rank: "2", suit: "♠" },
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
  return deck[index]?.suit ?? "♠";
}

function cardTheme(index: number): string {
  return "theme-black";
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
