<template>
  <!-- 希亚思考中的加载动画 -->
  <div class="typing" aria-label="希亚思考中">
    <span class="typing__avatar">💗</span>
    <div class="typing__bubble">
      <span class="typing__text">希亚思考中</span>
      <span class="typing__dots">
        <i></i><i></i><i></i>
      </span>
    </div>
  </div>
</template>

<style scoped>
.typing {
  display: flex;
  align-items: center;
  gap: 8px;
}

.typing__avatar {
  font-size: 20px;
}

.typing__bubble {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 18px;
  border-bottom-left-radius: 6px;
  background: var(--bubble-bot);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}

.typing__text {
  font-size: 13px;
  color: var(--text-soft);
}

.typing__dots {
  display: inline-flex;
  gap: 4px;
}

.typing__dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing__dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.typing__dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}
</style>
