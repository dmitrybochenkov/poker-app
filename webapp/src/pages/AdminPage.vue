<template>
  <section class="admin-page">
    <AdminConsoleBackground />
    <div v-if="loading" class="admin-page__state hint">Проверка доступа...</div>
    <div v-else-if="isAdmin" class="page-menu page-menu-overlay">
      <RouterLink class="menu-btn" to="/admin/create-poll">🗓 Создать опрос</RouterLink>
      <RouterLink class="menu-btn" to="/admin/start-poker">🎲 Старт покера</RouterLink>
      <RouterLink class="menu-btn" to="/admin/make-admin">👨🏻‍💻 Добавить админа</RouterLink>
      <RouterLink class="menu-btn" to="/">🏠 На главную</RouterLink>
    </div>
    <div v-else class="admin-page__state hint">Нет доступа: только для админа.</div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import AdminConsoleBackground from "../components/AdminConsoleBackground.vue";
import { buildBootstrapUrl, getPlatformBootstrap } from "../services/platform";

const loading = ref(true);
const isAdmin = ref(false);

onMounted(async () => {
  try {
    const { platform, userId } = getPlatformBootstrap();
    if (userId === null || !Number.isFinite(userId)) return;
    const safeUserId = userId;
    const res = await fetch(buildBootstrapUrl(platform, safeUserId));
    if (!res.ok) return;
    const data = (await res.json()) as { is_admin?: boolean };
    isAdmin.value = Boolean(data.is_admin);
  } finally {
    loading.value = false;
  }
});
</script>
