<template>
  <section class="simple-page simple-page-centered white-page">
    <div v-if="loading" class="hint">Загрузка...</div>
    <div v-else class="hint">
      {{ state?.has_active_poker ? "Покер рум открыт." : "Сейчас покер рум закрыт." }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { buildBootstrapUrl, getPlatformBootstrap } from "../services/platform";

interface BootstrapState {
  has_active_poker: boolean;
}

const loading = ref(true);
const state = ref<BootstrapState | null>(null);

onMounted(async () => {
  try {
    const { platform, userId } = getPlatformBootstrap();
    if (userId === null || !Number.isFinite(userId)) {
      state.value = { has_active_poker: false };
      return;
    }
    const safeUserId = userId;
    const res = await fetch(buildBootstrapUrl(platform, safeUserId));
    if (res.ok) {
      state.value = (await res.json()) as BootstrapState;
      return;
    }
    state.value = { has_active_poker: false };
  } finally {
    loading.value = false;
  }
});
</script>
