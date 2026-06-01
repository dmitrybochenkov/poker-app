<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <h1>Poker App</h1>
        <p>Telegram Web App</p>
      </div>
      <nav class="tabs">
        <RouterLink to="/">Главная</RouterLink>
        <RouterLink to="/poker">Покер</RouterLink>
        <RouterLink to="/bets">Ставки</RouterLink>
      </nav>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>
