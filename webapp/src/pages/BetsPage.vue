<template>
  <section class="bets-page">
    <div class="roulette-felt" aria-hidden="true">
      <div class="roulette-board-wrap">
        <div class="roulette-board">
          <div class="roulette-top-row">
            <div class="zero-cell"><span>0</span></div>

            <div class="numbers-grid">
              <span v-for="number in topRow" :key="`top-${number}`" class="n" :class="numberColor(number)">
                <span>{{ number }}</span>
              </span>
              <span v-for="number in middleRow" :key="`mid-${number}`" class="n" :class="numberColor(number)">
                <span>{{ number }}</span>
              </span>
              <span v-for="number in bottomRow" :key="`bot-${number}`" class="n" :class="numberColor(number)">
                <span>{{ number }}</span>
              </span>
            </div>

            <div class="to1-col">
              <span class="to1-side">2 to 1</span>
              <span class="to1-side">2 to 1</span>
              <span class="to1-side">2 to 1</span>
            </div>
          </div>

          <div class="dozens-row">
            <span class="dozen-cell">1st 12</span>
            <span class="dozen-cell">2nd 12</span>
            <span class="dozen-cell">3rd 12</span>
          </div>

          <div class="outside-row">
            <span class="outside-cell">1 to 18</span>
            <span class="outside-cell">EVEN</span>
            <span class="outside-cell diamond red"></span>
            <span class="outside-cell diamond black"></span>
            <span class="outside-cell">ODD</span>
            <span class="outside-cell">19 to 36</span>
          </div>
        </div>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts">
const topRow = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36];
const middleRow = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35];
const bottomRow = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34];
const redNumbers = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

function numberColor(number: number): string {
  return redNumbers.has(number) ? "red" : "black";
}
</script>
