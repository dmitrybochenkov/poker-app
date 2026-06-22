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
    <div class="overlay-panel-layout">
      <div class="page-menu page-menu-overlay page-menu-overlay--compact">
        <RouterLink class="menu-btn" to="/next-poker">🗓 Опрос</RouterLink>
        <RouterLink class="menu-btn" to="/poker/stat">🦑 Статистика покера</RouterLink>
        <RouterLink class="menu-btn" to="/poker/history">⌛ История</RouterLink>
        <RouterLink class="menu-btn" to="/">🏠 На главную</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
