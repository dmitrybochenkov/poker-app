<template>
  <section class="players-page">
    <div class="players-carousel" aria-label="Игроки">
      <article v-for="player in players" :key="player.id" class="player-card">
        <img class="player-photo" :src="player.photo" :alt="player.name" loading="lazy" />
        <div class="player-meta">
          <h3>{{ player.name }}</h3>
          <p>{{ player.nickname }}</p>
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
          <div class="stat-cell">
            <span class="k">Winrate</span>
            <span class="v">{{ player.winrate }}</span>
          </div>
        </div>
      </article>
    </div>
    <p class="players-hint">Свайп влево/вправо</p>
  </section>
</template>

<script setup lang="ts">
type PlayerCard = {
  id: number;
  name: string;
  nickname: string;
  games: number;
  profit: string;
  winrate: string;
  photo: string;
};

const players: PlayerCard[] = [
  {
    id: 1,
    name: "Дима Боченков",
    nickname: "Капитан стола",
    games: 42,
    profit: "+12 450 ₽",
    winrate: "27%",
    photo: "https://api.dicebear.com/9.x/notionists/svg?seed=Dima&backgroundColor=b6e3f4",
  },
  {
    id: 2,
    name: "Серега Кузьмин",
    nickname: "Стабильный рейзер",
    games: 39,
    profit: "+8 910 ₽",
    winrate: "24%",
    photo: "https://api.dicebear.com/9.x/notionists/svg?seed=Serega&backgroundColor=c0aede",
  },
  {
    id: 3,
    name: "Саня Волков",
    nickname: "Тайтовый волк",
    games: 31,
    profit: "+2 120 ₽",
    winrate: "19%",
    photo: "https://api.dicebear.com/9.x/notionists/svg?seed=Volkov&backgroundColor=ffd5dc",
  },
  {
    id: 4,
    name: "Игорь Пышкин",
    nickname: "Мастер колла",
    games: 28,
    profit: "-1 340 ₽",
    winrate: "16%",
    photo: "https://api.dicebear.com/9.x/notionists/svg?seed=Igor&backgroundColor=d1d4f9",
  },
];
</script>
