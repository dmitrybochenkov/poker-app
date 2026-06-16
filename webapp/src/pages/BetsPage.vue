<template>
  <section class="bets-page">
    <div class="roulette-felt" aria-hidden="true">
      <div class="roulette-board">
        <div class="board-top-gap"></div>
        <div class="zero-cell"><span>0</span></div>

        <div class="left-panel">
          <div class="outside-col">
            <span class="outside-cell"><span>1 to 18</span></span>
            <span class="outside-cell"><span>EVEN</span></span>
            <span class="outside-cell diamond red"></span>
            <span class="outside-cell diamond black"></span>
            <span class="outside-cell"><span>ODD</span></span>
            <span class="outside-cell"><span>19 to 36</span></span>
          </div>

          <div class="dozens-col">
            <span class="dozen-cell"><span>1st 12</span></span>
            <span class="dozen-cell"><span>2nd 12</span></span>
            <span class="dozen-cell"><span>3rd 12</span></span>
          </div>
        </div>

        <div class="numbers-grid">
          <span v-for="row in numberRows" :key="`row-${row[0]}`" class="number-row">
            <span v-for="number in row" :key="number" class="n" :class="numberColor(number)">
              <span>{{ number }}</span>
            </span>
          </span>
        </div>

        <div class="to1-row">
          <span class="to1-cell">2 to 1</span>
          <span class="to1-cell">2 to 1</span>
          <span class="to1-cell">2 to 1</span>
        </div>
      </div>
    </div>
    <div class="overlay-actions">
      <div class="page-menu page-menu-overlay">
        <RouterLink class="menu-btn" to="/bets/make">🐔 Сделать ставку</RouterLink>
        <RouterLink class="menu-btn" to="/bets/pay">🤝 Оплатить ставку</RouterLink>
        <RouterLink class="menu-btn" to="/bets/current">🎰 Текущие турниры</RouterLink>
        <RouterLink class="menu-btn" to="/bets/stat">🍀 Статистика ставок</RouterLink>
        <RouterLink class="menu-btn" to="/">🏠 На главную</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";

const numberRows = Array.from({ length: 12 }, (_, index) => [index * 3 + 1, index * 3 + 2, index * 3 + 3]);
const redNumbers = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

function numberColor(number: number): string {
  return redNumbers.has(number) ? "red" : "black";
}
</script>
