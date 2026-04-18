<script setup>
import ChatInterface from './components/ChatInterface.vue';
</script>

<template>
  <main>
    <ChatInterface />
  </main>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,100..900&display=swap');

html, body, #app, main {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  font-family: 'Inter', sans-serif;
  background-color: #0f172a;
  overflow: hidden;
}

* {
  box-sizing: border-box;
}
</style>
