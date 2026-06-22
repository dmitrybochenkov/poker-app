<template>
  <section class="info-page">
    <InfoBookshelfBackground />
    <div class="overlay-panel-layout">
      <div class="page-menu page-menu-overlay page-menu-overlay--compact">
        <RouterLink class="menu-btn" to="/info/poker">ℹ️💍 Про покер</RouterLink>
        <RouterLink class="menu-btn" to="/info/bets">ℹ️🍀 Про ставки</RouterLink>
        <RouterLink class="menu-btn" to="/">🏠 На главную</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
import InfoBookshelfBackground from "../components/InfoBookshelfBackground.vue";
</script>
