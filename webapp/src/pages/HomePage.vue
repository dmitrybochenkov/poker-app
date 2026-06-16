<template>
  <section class="home">
    <div v-if="loading" class="hint">Загрузка...</div>
    <div v-else class="menu-grid">
      <RouterLink class="menu-btn" to="/players">Игроки</RouterLink>
      <RouterLink class="menu-btn" to="/poker">Про покер</RouterLink>
      <RouterLink class="menu-btn" to="/bets">Про ставки</RouterLink>
      <RouterLink class="menu-btn" to="/info">Информация</RouterLink>

      <RouterLink class="menu-btn menu-btn-admin" to="/admin">
        Админ панель
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { buildBootstrapUrl, getPlatformBootstrap } from "../services/platform";

interface BootstrapState {
  is_registered: boolean;
  is_admin: boolean;
  is_approved: boolean;
  has_phone: boolean;
  has_active_poll: boolean;
}

const loading = ref(true);
const state = ref<BootstrapState | null>(null);

onMounted(async () => {
  try {
    const { platform, userId } = getPlatformBootstrap();
    if (!Number.isFinite(userId)) {
      state.value = {
        is_registered: false,
        is_admin: false,
        is_approved: false,
        has_phone: false,
        has_active_poll: false,
      };
      return;
    }
    const res = await fetch(buildBootstrapUrl(platform, userId));
    if (res.ok) {
      state.value = (await res.json()) as BootstrapState;
      return;
    }
    state.value = {
      is_registered: false,
      is_admin: false,
      is_approved: false,
      has_phone: false,
      has_active_poll: false,
    };
  } finally {
    loading.value = false;
  }
});
</script>
