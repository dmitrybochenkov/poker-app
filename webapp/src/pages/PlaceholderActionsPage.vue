<template>
  <section class="simple-page simple-page-centered white-page">
    <div class="hint">{{ title }}: тут будут кнопки как в реплай-клаве</div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string }>();
</script>
