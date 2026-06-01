<template>
  <div class="shell">
    <div class="table-bg" aria-hidden="true">
      <div class="table-rail">
        <div class="table-felt">
          <div class="ring">
            <div class="segment seg-1"></div>
            <div class="segment seg-2"></div>
            <div class="segment seg-3"></div>
            <div class="segment seg-4"></div>
            <div class="segment seg-5"></div>
            <div class="segment seg-6"></div>
            <div class="segment seg-7"></div>
            <div class="segment seg-8"></div>
            <div class="segment seg-9"></div>
            <div class="segment seg-10"></div>
          </div>
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
