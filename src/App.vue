<script setup>
import Composer from "./composer/Composer.vue";
import Wallpaper from "./wallpaper/Wallpaper.vue";

const wall = window.location.hash.startsWith("#/wallpaper");
</script>

<template>
  <Wallpaper v-if="wall" />
  <Composer v-else />
</template>
