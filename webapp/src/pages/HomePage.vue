<template>
  <section class="home">
    <div v-if="loading" class="hint">Загрузка...</div>
    <div v-else class="menu-grid">
      <RouterLink
        v-if="state?.has_active_poll"
        class="menu-btn"
        to="/next-poker"
      >
        Следующий покер
      </RouterLink>

      <RouterLink class="menu-btn" to="/players">Игроки</RouterLink>
      <RouterLink class="menu-btn" to="/poker">Про покер</RouterLink>
      <RouterLink class="menu-btn" to="/bets">Про ставки</RouterLink>
      <RouterLink class="menu-btn" to="/info">Информация</RouterLink>

      <RouterLink
        v-if="state?.is_admin"
        class="menu-btn menu-btn-admin"
        to="/admin"
      >
        Админ панель
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getTelegramWebApp } from "../services/telegram";

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
    const tgUserId = Number((getTelegramWebApp()?.initDataUnsafe?.user as { id?: number } | undefined)?.id);
    if (!Number.isFinite(tgUserId)) {
      state.value = {
        is_registered: false,
        is_admin: false,
        is_approved: false,
        has_phone: false,
        has_active_poll: false,
      };
      return;
    }
    const res = await fetch(`/api/webapp/bootstrap/${tgUserId}`);
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
