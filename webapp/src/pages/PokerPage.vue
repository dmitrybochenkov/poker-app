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
      <RouterLink class="menu-btn" to="/poker/actions">Открыть действия</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts"></script>
