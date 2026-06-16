<template>
  <section class="players-page">
    <div v-if="loading" class="hint players-status">Загрузка игроков...</div>
    <div v-else-if="players.length === 0" class="hint players-status">Пока нет данных</div>
    <div v-else class="players-carousel" aria-label="Игроки">
      <article v-for="(player, index) in players" :key="player.player_id" class="player-card">
        <div class="player-card-art" :class="[cardTheme(index), cardRole(index)]">
          <div class="card-corner top-left" :class="cardTheme(index)">
            <span class="rank">{{ cardRank(index) }}</span>
            <span class="suit">{{ cardSuit(index) }}</span>
          </div>
          <div class="player-card-figure" :class="[cardRole(index), cardTheme(index)]">
            <img
              v-if="player.photo_url"
              :src="player.photo_url"
              :alt="`Фото игрока ${player.name}`"
              class="player-photo"
            />
            <button
              v-if="player.photo_url && isOwnCard(player)"
              class="player-photo-edit-btn"
              type="button"
              :disabled="uploadingPhoto"
              @click="triggerPhotoPicker"
            >
              <span class="camera-icon camera-icon--small" aria-hidden="true">
                <span class="camera-body"></span>
                <span class="camera-lens"></span>
                <span class="camera-flash"></span>
                <span class="camera-plus"></span>
              </span>
            </button>
            <button
              v-else-if="isOwnCard(player)"
              class="player-photo-upload-btn"
              type="button"
              :disabled="uploadingPhoto"
              @click="triggerPhotoPicker"
            >
              <span class="player-photo-upload-circle">
                <span class="camera-icon" aria-hidden="true">
                  <span class="camera-body"></span>
                  <span class="camera-lens"></span>
                  <span class="camera-flash"></span>
                  <span class="camera-plus"></span>
                </span>
              </span>
            </button>
          </div>
        </div>
        <div class="player-meta">
          <h3>{{ player.name }}</h3>
          <p v-if="player.tel_number" class="player-phone">{{ player.tel_number }}</p>
        </div>
        <div class="player-stats">
          <div class="stat-badge" :class="profitClass(player.profit_rub)">
            <span class="stat-emoji">💲</span>
            <span class="stat-text">{{ player.profit }}</span>
          </div>
          <div class="stat-badge">
            <span class="stat-emoji">🎲</span>
            <span class="stat-text">{{ player.games }}</span>
          </div>
          <div class="stat-badge">
            <span class="stat-emoji">💍</span>
            <span class="stat-text">{{ player.wins }}</span>
          </div>
          <div class="stat-badge">
            <span class="stat-emoji">❌</span>
            <span class="stat-text">{{ player.losses }}</span>
          </div>
        </div>
        <div v-if="isOwnCard(player)" class="player-card-actions">
          <button class="mini-card-btn" type="button">Добавить телефон</button>
        </div>
      </article>
    </div>
    <p v-if="!loading && players.length > 1" class="players-hint">Свайп влево/вправо</p>
    <input
      ref="photoInput"
      class="visually-hidden-input"
      type="file"
      accept="image/*"
      @change="handlePhotoSelected"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getTelegramWebApp } from "../services/telegram";

type PlayerCardApi = {
  player_id: number;
  name: string;
  tel_number: string | null;
  games: number;
  wins: number;
  losses: number;
  profit_rub: number;
  photo_url: string | null;
};

type PlayerCard = {
  player_id: number;
  name: string;
  tel_number: string | null;
  games: number;
  wins: number;
  losses: number;
  profit_rub: number;
  profit: string;
  photo_url: string | null;
};

type WebAppBootstrap = {
  user_row_id?: number | null;
};

const loading = ref(true);
const players = ref<PlayerCard[]>([]);
const currentUserRowId = ref<number | null>(null);
const uploadingPhoto = ref(false);
const photoInput = ref<HTMLInputElement | null>(null);
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

function profitClass(amount: number): string {
  if (amount > 0) return "is-positive";
  if (amount < 0) return "is-negative";
  return "is-neutral";
}

function currentTelegramId(): number | null {
  const tgUserId = Number((getTelegramWebApp()?.initDataUnsafe?.user as { id?: number } | undefined)?.id);
  return Number.isFinite(tgUserId) ? tgUserId : null;
}

function isOwnCard(player: PlayerCard): boolean {
  return currentUserRowId.value === player.player_id;
}

function triggerPhotoPicker(): void {
  if (!currentTelegramId() || uploadingPhoto.value) return;
  photoInput.value?.click();
}

async function loadBootstrap(): Promise<void> {
  const tgUserId = currentTelegramId();
  if (!tgUserId) return;
  const res = await fetch(`/api/webapp/bootstrap/${tgUserId}`);
  if (!res.ok) return;
  const data = (await res.json()) as WebAppBootstrap;
  currentUserRowId.value = data.user_row_id ?? null;
}

async function loadPlayers(): Promise<void> {
  const res = await fetch("/api/webapp/players");
  if (!res.ok) return;
  const data = (await res.json()) as PlayerCardApi[];
  players.value = data.slice(0, 14).map((item) => ({
    player_id: item.player_id,
    name: item.name,
    tel_number: item.tel_number ?? null,
    games: item.games,
    wins: item.wins,
    losses: item.losses,
    profit_rub: item.profit_rub,
    profit: formatRub(item.profit_rub),
    photo_url: item.photo_url ?? null,
  }));
}

async function handlePhotoSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  const tgUserId = currentTelegramId();
  if (!file || !tgUserId) return;

  try {
    uploadingPhoto.value = true;
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`/api/webapp/users/${tgUserId}/photo`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) return;

    await loadPlayers();
  } finally {
    uploadingPhoto.value = false;
    input.value = "";
  }
}

onMounted(async () => {
  try {
    await loadBootstrap();
    await loadPlayers();
  } finally {
    loading.value = false;
  }
});
</script>
