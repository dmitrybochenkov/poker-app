<template>
  <section class="poker-page">
    <div class="table-bg" aria-hidden="true">
      <div class="table-rail">
        <div class="table-felt">
          <div class="ring"></div>
          <div class="board">
            <span class="card-slot"></span>
            <span class="card-slot"></span>
            <span class="card-slot"></span>
            <span class="card-slot"></span>
            <span class="card-slot"></span>
          </div>
        </div>
      </div>
    </div>
    <div class="overlay-actions">
      <div class="page-menu page-menu-overlay">
        <RouterLink
          v-if="state?.has_active_poll"
          class="menu-btn"
          to="/next-poker"
        >
          📅 Следующий покер
        </RouterLink>
        <RouterLink class="menu-btn" to="/poker/stat">🦑 Статистика покера</RouterLink>
        <RouterLink class="menu-btn" to="/poker/history">⌛ История</RouterLink>
        <RouterLink class="menu-btn" to="/">🏠 На главную</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { buildBootstrapUrl, getPlatformBootstrap } from "../services/platform";

interface BootstrapState {
  has_active_poll: boolean;
}

const state = ref<BootstrapState | null>(null);

onMounted(async () => {
  const { platform, userId } = getPlatformBootstrap();
  if (userId === null || !Number.isFinite(userId)) return;
  const safeUserId = userId;
  const res = await fetch(buildBootstrapUrl(platform, safeUserId));
  if (res.ok) {
    state.value = (await res.json()) as BootstrapState;
  }
});
</script>
