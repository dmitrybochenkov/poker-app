<template>
  <section class="simple-page white-page">
    <div class="hint">{{ title }}: тут будут кнопки как в реплай-клаве</div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string }>();
</script>
