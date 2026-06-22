<template>
  <section :class="pageClass">
    <div v-if="theme === 'poker'" class="table-bg" aria-hidden="true">
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

    <div v-else-if="theme === 'bets'" class="roulette-felt" aria-hidden="true">
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

    <InfoBookshelfBackground v-else-if="theme === 'info'" />

    <div v-if="resolvedContentHtml || menuItems.length" class="overlay-panel-layout">
      <article v-if="resolvedContentHtml" class="page-content-card" v-html="resolvedContentHtml"></article>

      <div v-if="menuItems.length" class="page-menu page-menu-overlay page-menu-overlay--compact">
        <RouterLink v-for="item in menuItems" :key="item.to" class="menu-btn" :to="item.to">
          {{ item.label }}
        </RouterLink>
      </div>
    </div>

    <div v-else class="submenu-placeholder">
      <div class="hint">{{ title }}: тут будут кнопки как в реплай-клаве</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import InfoBookshelfBackground from "../components/InfoBookshelfBackground.vue";

type MenuItem = {
  label: string;
  to: string;
};

const props = withDefaults(
  defineProps<{
    title: string;
    theme?: "plain" | "poker" | "bets" | "info";
    menuItems?: MenuItem[];
    contentHtml?: string;
    contentApi?: string;
  }>(),
  {
    theme: "plain",
    menuItems: () => [],
    contentHtml: "",
    contentApi: "",
  }
);

const numberRows = Array.from({ length: 12 }, (_, index) => [index * 3 + 1, index * 3 + 2, index * 3 + 3]);
const redNumbers = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

const pageClass = computed(() => {
  if (props.theme === "poker") return "poker-page";
  if (props.theme === "bets") return "bets-page";
  if (props.theme === "info") return "info-page";
  return "simple-page simple-page-centered white-page";
});

const menuItems = computed(() => props.menuItems);
const resolvedContentHtml = ref(props.contentHtml || "");

function numberColor(number: number): string {
  return redNumbers.has(number) ? "red" : "black";
}

watch(
  () => [props.contentApi, props.contentHtml] as const,
  async ([contentApi, contentHtml]) => {
    if (contentHtml) {
      resolvedContentHtml.value = contentHtml;
      return;
    }

    if (!contentApi) {
      resolvedContentHtml.value = "";
      return;
    }

    try {
      const response = await fetch(contentApi);
      if (!response.ok) {
        resolvedContentHtml.value = "Справка пока пустая.";
        return;
      }
      const payload = (await response.json()) as { body_html?: string };
      resolvedContentHtml.value = payload.body_html?.trim() || "Справка пока пустая.";
    } catch {
      resolvedContentHtml.value = "Справка пока пустая.";
    }
  },
  { immediate: true }
);
</script>
