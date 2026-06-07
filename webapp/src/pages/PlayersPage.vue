<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="(player, index) in players" :key="player.player_id" class="player-card">
        <div class="player-card-art">
          <img :src="cardArt(index)" :alt="cardTitle(index)" />
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
  { title: "Черный джокер", art: "/player-cards/joker-black.png" },
  { title: "Красный джокер", art: "/player-cards/joker-red.png" },
  { title: "Король треф", art: "/player-cards/king-clubs.png" },
  { title: "Король пик", art: "/player-cards/king-spades.png" },
  { title: "Король червей", art: "/player-cards/king-hearts.png" },
  { title: "Король бубен", art: "/player-cards/king-diamonds.png" },
  { title: "Дама треф", art: "/player-cards/queen-clubs.png" },
  { title: "Дама пик", art: "/player-cards/queen-spades.png" },
  { title: "Дама червей", art: "/player-cards/queen-hearts.png" },
  { title: "Дама бубен", art: "/player-cards/queen-diamonds.png" },
  { title: "Валет треф", art: "/player-cards/jack-clubs.png" },
  { title: "Валет пик", art: "/player-cards/jack-spades.png" },
  { title: "Валет червей", art: "/player-cards/jack-hearts.png" },
  { title: "Валет бубен", art: "/player-cards/jack-diamonds.png" },
];

function formatRub(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toLocaleString("ru-RU")} ₽`;
}

function cardArt(index: number): string {
  return deck[index]?.art ?? deck[0].art;
}

function cardTitle(index: number): string {
  return deck[index]?.title ?? deck[0].title;
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
