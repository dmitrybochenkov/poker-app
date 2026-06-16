<template>
  <section class="simple-page white-page">
    <div class="page-menu page-menu-plain">
      <RouterLink class="menu-btn" to="/next-poker/vote">✅ Проголосовать</RouterLink>
      <RouterLink class="menu-btn" to="/next-poker/results">📊 Посмотреть результаты</RouterLink>
      <RouterLink class="menu-btn" to="/poker">🏠 На главную</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
