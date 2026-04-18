<script setup>
import ChatInterface from './components/ChatInterface.vue';
</script>

<template>
  <!-- Animated background bubbles -->
  <div class="bubble-bg">
    <div class="bubble bubble-orange"></div>
    <div class="bubble bubble-green"></div>
  </div>

  <!-- App shell -->
  <main class="app-shell">
    <!-- Header -->
    <header class="top-bar">
      <div class="logo">
        <span class="logo-icon">🏙️</span>
        <span class="logo-name">Colon<span class="logo-ia">IA</span></span>
      </div>
      <p class="logo-tagline">Inteligencia para elegir dónde vivir en CDMX</p>
    </header>

    <!-- Chat -->
    <div class="chat-wrapper">
      <ChatInterface />
    </div>
  </main>
</template>

<style>
@import './assets/main.css';

.app-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
  z-index: 1;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 28px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid #1a1a1a22;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #1a1a1a;
}

.logo-icon {
  font-size: 1.4rem;
}

.logo-ia {
  color: #f97316;
}

.logo-tagline {
  font-size: 0.8rem;
  color: #6b7280;
  border-left: 1px solid #d1d5db;
  padding-left: 16px;
  margin: 0;
  font-weight: 400;
}

.chat-wrapper {
  flex: 1;
  overflow: hidden;
  position: relative;
}
</style>
