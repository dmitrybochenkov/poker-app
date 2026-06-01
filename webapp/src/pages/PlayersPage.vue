<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="player in players" :key="player.player_id" class="player-card">
        <div class="player-meta">
          <h3>{{ player.name }}</h3>
        </div>
        <div class="player-stats">
          <div class="stat-cell">
            <span class="k">Игр</span>
            <span class="v">{{ player.games }}</span>
          </div>
          <div class="stat-cell">
            <span class="k">Профит</span>
            <span class="v">{{ player.profit }}</span>
          </div>
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

function formatRub(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toLocaleString("ru-RU")} ₽`;
}

onMounted(async () => {
  try {
    const res = await fetch("/api/webapp/players");
    if (!res.ok) return;
    const data = (await res.json()) as PlayerCardApi[];
    players.value = data.map((item) => ({
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
