<template>
  <section class="stack">
    <h2>Главная</h2>
    <p class="muted">Пока оставили только одно действие для Mini App.</p>
    <div class="card stack">
      <button class="primary-btn" type="button" @click="onPrimaryAction">
        {{ primaryButtonLabel }}
      </button>
      <p v-if="loading" class="muted">Проверяю профиль...</p>
      <p v-else-if="error" class="muted">{{ error }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getTelegramWebApp } from "../services/telegram";

interface UserRead {
  row_id: number;
  telegram_id: number | null;
  tel_number: string | null;
}

const loading = ref(true);
const error = ref("");
const isRegistered = ref(false);
const hasPhone = ref(false);
const telegramId = ref<number | null>(null);

const primaryButtonLabel = computed(() => {
  if (!isRegistered.value) {
    return "Регистрация";
  }
  if (!hasPhone.value) {
    return "Добавить телефон";
  }
  return "Телефон добавлен";
});

async function fetchUserState(): Promise<void> {
  loading.value = true;
  error.value = "";

  const webApp = getTelegramWebApp();
  const tgUserId = webApp?.initDataUnsafe?.user && typeof webApp.initDataUnsafe.user === "object"
    ? Number((webApp.initDataUnsafe.user as Record<string, unknown>).id)
    : Number.NaN;
  if (!Number.isFinite(tgUserId)) {
    loading.value = false;
    error.value = "Не удалось получить Telegram ID";
    return;
  }

  telegramId.value = tgUserId;

  const response = await fetch(`/users/by-telegram/${tgUserId}`);
  if (response.status === 404) {
    isRegistered.value = false;
    hasPhone.value = false;
    loading.value = false;
    return;
  }
  if (!response.ok) {
    loading.value = false;
    error.value = "Ошибка загрузки профиля";
    return;
  }

  const user = (await response.json()) as UserRead;
  isRegistered.value = true;
  hasPhone.value = Boolean(user.tel_number && String(user.tel_number).trim());
  loading.value = false;
}

function onPrimaryAction(): void {
  if (!isRegistered.value) {
    window.alert("Тут будет экран регистрации.");
    return;
  }
  if (!hasPhone.value) {
    window.alert("Тут будет форма добавления телефона.");
    return;
  }
  window.alert("Телефон уже добавлен.");
}

onMounted(async () => {
  try {
    await fetchUserState();
  } catch {
    loading.value = false;
    error.value = "Не удалось связаться с сервером";
  }
});
</script>
