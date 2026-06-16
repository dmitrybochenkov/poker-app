<template>
  <section class="simple-page white-page">
    <div v-if="loading" class="hint">Проверка доступа...</div>
    <div v-else-if="isAdmin" class="hint">Админ панель: тут будут кнопки как в реплай-клаве</div>
    <div v-else class="hint">Нет доступа: только для админа.</div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { buildBootstrapUrl, getPlatformBootstrap } from "../services/platform";

const loading = ref(true);
const isAdmin = ref(false);

onMounted(async () => {
  try {
    const { platform, userId } = getPlatformBootstrap();
    if (!Number.isFinite(userId)) return;
    const res = await fetch(buildBootstrapUrl(platform, userId));
    if (!res.ok) return;
    const data = (await res.json()) as { is_admin?: boolean };
    isAdmin.value = Boolean(data.is_admin);
  } finally {
    loading.value = false;
  }
});
</script>
