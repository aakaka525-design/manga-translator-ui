<template>
  <div class="halftone-bg" />
</template>

<style scoped>
.halftone-bg {
  position: fixed;
  inset: 0;
  z-index: -10;
  background-color: #0F0F11;
  background-image: radial-gradient(#333 1px, transparent 1px);
  background-size: 20px 20px;
}
</style>
