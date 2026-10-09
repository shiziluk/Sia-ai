<script setup lang="ts">
// 希亚立绘组件：轻量装饰，展示默认头像图
withDefaults(defineProps<{ src?: string; size?: number }>(), {
  src: '/avatars/00000-3450677638.png',
  size: 120
})
</script>

<template>
  <div class="sprite" :style="{ width: `${size}px`, height: `${size}px` }">
    <img class="sprite__img" :src="src" alt="希亚立绘" draggable="false" />
  </div>
</template>

<style scoped>
.sprite {
  position: relative;
  border-radius: 50%;
  padding: 3px;
  background: var(--sprite-ring);
  box-shadow: var(--shadow);
  animation: sprite-float 5s ease-in-out infinite;
}

.sprite__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  display: block;
  user-select: none;
}

@keyframes sprite-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-6px);
  }
}
</style>
