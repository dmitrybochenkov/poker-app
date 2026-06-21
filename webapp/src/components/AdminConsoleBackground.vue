<template>
  <div class="admin-console-bg" aria-hidden="true">
    <div class="admin-console">
      <div class="admin-console__header">
        <div class="admin-console__grill">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="admin-console__title-wrap">
          <div class="admin-console__title">ADMIN</div>
          <div class="admin-console__title-mark">♠</div>
        </div>
        <div class="admin-console__grill admin-console__grill--right">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>

      <div class="admin-console__stack">
        <div
          v-for="section in sections"
          :key="section.label"
          class="admin-module"
          :class="`tone-${section.tone}`"
        >
          <div class="admin-module__icon">{{ section.icon }}</div>
          <div class="admin-module__slider">
            <div class="admin-module__ticks">
              <span v-for="n in 9" :key="n"></span>
            </div>
            <div class="admin-module__rail">
              <div class="admin-module__thumb"></div>
            </div>
          </div>
          <div class="admin-module__lamp"></div>
        </div>
      </div>

      <div class="admin-console__progress">
        <span
          v-for="n in 12"
          :key="`load-${n}`"
          class="admin-console__bar"
          :class="{ 'is-active': n > 3 }"
          :style="{ height: `${32 + n * 6}%` }"
        ></span>
      </div>

      <div class="admin-console__danger">
        <div class="admin-console__danger-ring">
          <div class="admin-console__danger-core"></div>
        </div>
      </div>

      <div class="admin-console__footer">
        <span v-for="n in 6" :key="`lamp-${n}`" class="admin-console__footer-lamp"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const sections = [
  { label: "users", icon: "👤", tone: "olive" },
  { label: "poker", icon: "♠", tone: "blue" },
  { label: "bets", icon: "◉", tone: "red" },
  { label: "trophy", icon: "🏆", tone: "purple" },
];
</script>
