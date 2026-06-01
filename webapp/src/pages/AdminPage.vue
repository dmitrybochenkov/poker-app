<template>
  <section class="simple-page white-page">
    <div v-if="loading" class="hint">Проверка доступа...</div>
    <div v-else-if="isAdmin" class="hint">Админ панель: тут будут кнопки как в реплай-клаве</div>
    <div v-else class="hint">Нет доступа: только для админа.</div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getTelegramWebApp } from "../services/telegram";

const loading = ref(true);
const isAdmin = ref(false);

onMounted(async () => {
  try {
    const tgUserId = Number((getTelegramWebApp()?.initDataUnsafe?.user as { id?: number } | undefined)?.id);
    if (!Number.isFinite(tgUserId)) return;
    const res = await fetch(`/api/webapp/bootstrap/${tgUserId}`);
    if (!res.ok) return;
    const data = (await res.json()) as { is_admin?: boolean };
    isAdmin.value = Boolean(data.is_admin);
  } finally {
    loading.value = false;
  }
});
</script>
