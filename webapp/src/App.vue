<template>
  <div class="shell">
    <main class="content">
      <RouterView />
    </main>
    <footer v-if="!isHome" class="global-nav">
      <RouterLink class="menu-btn home-btn" to="/">На главный экран</RouterLink>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const isHome = computed(() => route.path === "/");
</script>
