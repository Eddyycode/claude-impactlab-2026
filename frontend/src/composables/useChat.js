import { ref } from 'vue';
import axios from 'axios';

const BASE_URL = 'http://localhost:8000'; // hardcodeado — sin depender de env

export function useChat() {
  const isTyping = ref(false);
  const messages = ref([]);
  const preferences = ref({ idioma: 'es' });

  const sendMessage = async (messageText) => {
    if (!messageText.trim()) return;

    // 1. Agregar mensaje del usuario
    messages.value.push({ role: 'user', content: messageText });
    isTyping.value = true;

    try {
      // Payload limpio — solo role y content (sin reportData)
      const payload = {
        messages: messages.value
          .filter(m => m.role === 'user' || m.role === 'assistant')
          .map(m => ({ role: m.role, content: m.content || '' })),
        preferences: preferences.value,
      };

      const res = await axios.post(`${BASE_URL}/chat`, payload, {
        timeout: 120000,
        headers: { 'Content-Type': 'application/json' },
      });

      const data = res.data;

      messages.value.push({
        role: 'assistant',
        content: data.content || 'Análisis completado.',
        reportData: data.reportData || null,
      });

    } catch (e) {
      console.error('[useChat] error:', e);
      const isTimeout = e.code === 'ECONNABORTED' || (e.message && e.message.includes('timeout'));
      const isNetwork = !e.response;

      let msg = '⚠️ Error al conectar con el servidor.';
      if (isTimeout) msg = '⏳ El análisis tarda ~60s. Por favor espera e intenta de nuevo.';
      else if (isNetwork) msg = '🔌 No se pudo conectar al gateway. ¿Está corriendo en localhost:8000?';

      messages.value.push({ role: 'assistant', content: msg });
    } finally {
      isTyping.value = false;
    }
  };

  return { isTyping, messages, sendMessage, preferences };
}
