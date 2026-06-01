<template>
  <section class="stack">
    <h2>Главная</h2>
    <p class="muted">Подготовили основу. Дальше будем добавлять кнопки и действия по одной.</p>
    <div class="card">
      <p v-if="loading" class="muted">Проверяю профиль...</p>
      <p v-else-if="error" class="muted">{{ error }}</p>
      <p v-else class="muted">
        Статус: {{ isRegistered ? "пользователь найден" : "пользователь не найден" }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getTelegramWebApp } from "../services/telegram";

interface UserRead {
  row_id: number;
  telegram_id: number | null;
}

const loading = ref(true);
const error = ref("");
const isRegistered = ref(false);
const telegramId = ref<number | null>(null);

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
  void user;
  loading.value = false;
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
