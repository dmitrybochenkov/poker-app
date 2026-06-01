<template>
  <div class="shell">
    <div class="table-bg" aria-hidden="true">
      <div class="seat seat-1"></div>
      <div class="seat seat-2"></div>
      <div class="seat seat-3"></div>
      <div class="seat seat-4"></div>
      <div class="seat seat-5"></div>
      <div class="seat seat-6"></div>
      <div class="seat seat-7"></div>
      <div class="seat seat-8"></div>
      <div class="seat seat-9"></div>
      <div class="seat seat-10"></div>
      <div class="board">
        <span class="card-slot"></span>
        <span class="card-slot"></span>
        <span class="card-slot"></span>
        <span class="card-slot"></span>
        <span class="card-slot"></span>
      </div>
    </div>
    <header class="topbar">
      <div>
        <h1>Poker App</h1>
        <p>Telegram Web App</p>
      </div>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts"></script>
