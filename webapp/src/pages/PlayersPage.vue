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
              <span class="photo-action-circle photo-action-circle--small">
                <img :src="cameraIconUrl" alt="" class="photo-action-icon photo-action-icon--small" />
              </span>
            </button>
            <button
              v-else-if="isOwnCard(player)"
              class="player-photo-upload-btn"
              type="button"
              :disabled="uploadingPhoto"
              @click="triggerPhotoPicker"
            >
              <span class="photo-action-circle photo-action-circle--large">
                <img :src="cameraIconUrl" alt="" class="photo-action-icon photo-action-icon--large" />
              </span>
            </button>
          </div>
        </div>
        <div class="player-meta">
          <h3>{{ player.name }}</h3>
          <p class="player-phone-line">
            <span class="player-phone-marker">📞</span>
            <button
              class="player-phone"
              :class="{
                'is-empty': !player.tel_number,
                'is-copied': Boolean(player.tel_number) && copiedPhone === player.tel_number
              }"
              type="button"
              :disabled="!player.tel_number"
              @click="copyPhone(player.tel_number)"
            >
              {{ player.tel_number || "не указан" }}
            </button>
            <button
              v-if="isOwnCard(player)"
              class="player-phone-edit-trigger"
              type="button"
              @click="openPhoneEditor(player)"
            >
              🔧
            </button>
          </p>
          <p class="player-phone-line">
            <span class="player-phone-marker">🏦</span>
            <span class="player-phone" :class="{ 'is-empty': !player.bank_name }">
              {{ player.bank_name || "не указан" }}
            </span>
            <button
              v-if="isOwnCard(player)"
              class="player-phone-edit-trigger"
              type="button"
              @click="openBankEditor(player)"
            >
              🔧
            </button>
          </p>
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
      </article>
    </div>
    <p v-if="!loading && players.length > 1" class="players-hint">Свайп влево/вправо</p>
    <div v-if="phoneEditorFor !== null" class="player-phone-modal-backdrop" @click.self="closePhoneEditor">
      <form class="player-phone-modal" @submit.prevent="savePhone">
        <p class="player-phone-modal-title">Добавить / изменить телефон</p>
        <input
          v-model="phoneDraft"
          class="player-phone-input"
          type="tel"
          inputmode="numeric"
          maxlength="11"
          placeholder="Введи номер телефона начиная с 7"
        />
        <p v-if="phoneError" class="player-phone-error">{{ phoneError }}</p>
        <div class="player-phone-modal-actions">
          <button class="phone-decision-btn phone-decision-btn--confirm" type="submit" :disabled="savingPhone">✅</button>
          <button class="phone-decision-btn phone-decision-btn--cancel" type="button" @click="closePhoneEditor">❌</button>
        </div>
      </form>
    </div>
    <div v-if="bankEditorFor !== null" class="player-phone-modal-backdrop" @click.self="closeBankEditor">
      <form class="player-phone-modal" @submit.prevent="saveBank">
        <p class="player-phone-modal-title">Добавить / изменить банк</p>
        <input
          v-model="bankDraft"
          class="player-phone-input"
          type="text"
          maxlength="100"
          placeholder="Введи название банка"
        />
        <p v-if="bankError" class="player-phone-error">{{ bankError }}</p>
        <div class="player-phone-modal-actions">
          <button class="phone-decision-btn phone-decision-btn--confirm" type="submit" :disabled="savingBank">✅</button>
          <button class="phone-decision-btn phone-decision-btn--cancel" type="button" @click="closeBankEditor">❌</button>
        </div>
      </form>
    </div>
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
import {
  buildBankUpdateUrl,
  buildBootstrapUrl,
  buildPhotoUploadUrl,
  buildPhoneUpdateUrl,
  getPlatformBootstrap,
} from "../services/platform";

type PlayerCardApi = {
  player_id: number;
  name: string;
  tel_number: string | null;
  bank_name: string | null;
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
  bank_name: string | null;
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
const savingPhone = ref(false);
const photoInput = ref<HTMLInputElement | null>(null);
const phoneEditorFor = ref<number | null>(null);
const phoneDraft = ref("");
const phoneError = ref("");
const savingBank = ref(false);
const bankEditorFor = ref<number | null>(null);
const bankDraft = ref("");
const bankError = ref("");
const copiedPhone = ref<string | null>(null);
const cameraIconUrl = `${import.meta.env.BASE_URL}icons/camera-add.png`;
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

function deckCard(index: number) {
  return deck[Math.min(index, deck.length - 1)] ?? deck[deck.length - 1];
}

function formatRub(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return `${sign}${amount.toLocaleString("ru-RU")} ₽`;
}

function cardTitle(index: number): string {
  return deckCard(index).title;
}

function cardRole(index: number): string {
  return deckCard(index).role;
}

function cardRank(index: number): string {
  return deckCard(index).rank;
}

function cardSuit(index: number): string {
  return deckCard(index).suit;
}

function cardTheme(index: number): string {
  return "theme-black";
}

function profitClass(amount: number): string {
  if (amount > 0) return "is-positive";
  if (amount < 0) return "is-negative";
  return "is-neutral";
}

function currentPlatformUserId(): number | null {
  return getPlatformBootstrap().userId;
}

function isOwnCard(player: PlayerCard): boolean {
  return currentUserRowId.value === player.player_id;
}

function triggerPhotoPicker(): void {
  if (!currentPlatformUserId() || uploadingPhoto.value) return;
  photoInput.value?.click();
}

function openPhoneEditor(player: PlayerCard): void {
  phoneEditorFor.value = player.player_id;
  phoneDraft.value = (player.tel_number ?? "").replace(/\D/g, "");
  phoneError.value = "";
}

function openBankEditor(player: PlayerCard): void {
  bankEditorFor.value = player.player_id;
  bankDraft.value = player.bank_name ?? "";
  bankError.value = "";
}

function closePhoneEditor(): void {
  phoneEditorFor.value = null;
  phoneDraft.value = "";
  phoneError.value = "";
}

function closeBankEditor(): void {
  bankEditorFor.value = null;
  bankDraft.value = "";
  bankError.value = "";
}

async function copyPhone(phone: string | null): Promise<void> {
  if (!phone) return;
  try {
    await navigator.clipboard.writeText(phone);
    copiedPhone.value = phone;
    window.setTimeout(() => {
      if (copiedPhone.value === phone) copiedPhone.value = null;
    }, 1400);
  } catch {
    copiedPhone.value = null;
  }
}

async function loadBootstrap(): Promise<void> {
  const { platform, userId } = getPlatformBootstrap();
  if (!userId) return;
  const res = await fetch(buildBootstrapUrl(platform, userId));
  if (!res.ok) return;
  const data = (await res.json()) as WebAppBootstrap;
  currentUserRowId.value = data.user_row_id ?? null;
}

async function loadPlayers(): Promise<void> {
  const res = await fetch("/api/webapp/players");
  if (!res.ok) return;
  const data = (await res.json()) as PlayerCardApi[];
  players.value = data.map((item) => ({
    player_id: item.player_id,
    name: item.name,
    tel_number: item.tel_number ?? null,
    bank_name: item.bank_name ?? null,
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
  const { platform, userId } = getPlatformBootstrap();
  if (!file || !userId) return;

  try {
    uploadingPhoto.value = true;
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(buildPhotoUploadUrl(platform, userId), {
      method: "POST",
      body: formData,
    });
    if (!res.ok) return;
    const data = (await res.json()) as { photo_url?: string };
    const ownCard = players.value.find((item) => item.player_id === currentUserRowId.value);
    if (ownCard && data.photo_url) {
      ownCard.photo_url = data.photo_url;
    }

    await loadPlayers();
  } finally {
    uploadingPhoto.value = false;
    input.value = "";
  }
}

async function savePhone(): Promise<void> {
  const { platform, userId } = getPlatformBootstrap();
  const digits = phoneDraft.value.replace(/\D/g, "");
  if (!userId) return;
  if (!digits.startsWith("7") || digits.length !== 11) {
    phoneError.value = "Номер должен содержать 11 цифр и начинаться с 7";
    return;
  }

  try {
    savingPhone.value = true;
    phoneError.value = "";
    const res = await fetch(buildPhoneUpdateUrl(platform, userId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ tel_number: digits }),
    });
    if (!res.ok) {
      phoneError.value = "Не удалось сохранить номер";
      return;
    }

    closePhoneEditor();
    await loadPlayers();
  } finally {
    savingPhone.value = false;
  }
}

async function saveBank(): Promise<void> {
  const { platform, userId } = getPlatformBootstrap();
  const normalized = bankDraft.value
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase()
    .replace(/(^|\s|-)([a-zа-яё])/g, (_, prefix: string, letter: string) => `${prefix}${letter.toUpperCase()}`);
  if (!userId) return;
  if (!normalized) {
    bankError.value = "Введи название банка";
    return;
  }

  try {
    savingBank.value = true;
    bankError.value = "";
    const res = await fetch(buildBankUpdateUrl(platform, userId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ bank_name: normalized }),
    });
    if (!res.ok) {
      bankError.value = "Не удалось сохранить банк";
      return;
    }

    closeBankEditor();
    await loadPlayers();
  } finally {
    savingBank.value = false;
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
