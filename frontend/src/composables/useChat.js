import { ref } from 'vue';
import axios from 'axios';

// MOCK DE NARVARTE PONIENTE (FIXTURE API_CONTRACT)
const MOCK_RESPONSE = {
  direccion: "Narvarte Poniente, Ciudad de México",
  lat: 19.3934,
  lng: -99.155,
  scores: {
    global: 7.6,
    etiqueta_global: "Bueno",
    dimensiones: [
      {
        id: "seguridad",
        nombre: "Seguridad",
        score: 7.8,
        peso_aplicado: 20,
        fuente: "FGJ CDMX",
        dataset_id: "fgj",
        consultado_en: "2026-04-18",
        dato_bruto: "48 delitos / 1000 hab últimos 12m",
        detalle: "Tendencia estable vs. trimestre previo"
      },
      {
        id: "aire",
        nombre: "Calidad del Aire",
        score: 6.4,
        peso_aplicado: 12,
        fuente: "SIMAT",
        dataset_id: "aire",
        consultado_en: "2026-04-18",
        dato_bruto: "PM2.5 alto de manera recurrente",
        detalle: "Estación más cercana: Benito Juárez"
      },
      {
        id: "sismico",
        nombre: "Riesgo sísmico",
        score: 6.0,
        peso_aplicado: 18,
        fuente: "Atlas Riesgo CDMX",
        dataset_id: "atlas-riesgo-sismico",
        consultado_en: "2026-04-18",
        dato_bruto: "Zona de transición (Zona II)",
        detalle: "Aceleración sísmica media"
      },
      {
        id: "inundacion",
        nombre: "Riesgo de inundación",
        score: 9.0,
        peso_aplicado: 8,
        fuente: "Atlas Riesgo CDMX",
        dataset_id: "atlas-riesgo-inundaciones",
        consultado_en: "2026-04-18",
        dato_bruto: "Bajo riesgo de encharcamiento profundo",
        detalle: "Buen drenaje en la mayoría de calles"
      },
      {
        id: "agua",
        nombre: "Confiabilidad del Agua",
        score: 7.2,
        peso_aplicado: 14,
        fuente: "SACMEX",
        dataset_id: "reportes-de-agua",
        consultado_en: "2026-04-18",
        dato_bruto: "Reportes moderados/bajos",
        detalle: "Suministro estable sin tandeo severo interanual"
      },
      {
        id: "transporte",
        nombre: "Transporte Público",
        score: 9.5,
        peso_aplicado: 14,
        fuente: "GTFS CDMX",
        dataset_id: "gtfs",
        consultado_en: "2026-04-18",
        dato_bruto: "Acceso a Metrobús (Larga) y Metro (Etiopía)",
        detalle: "Múltiples opciones en un radio de 800m."
      },
      {
        id: "integridad_2017",
        nombre: "Integridad 2017",
        score: 8.0,
        peso_aplicado: 8,
        fuente: "Plataforma CDMX",
        dataset_id: "inmuebles-danados-2017",
        consultado_en: "2026-04-18",
        dato_bruto: "2 inmuebles afectados en radio 300m",
        detalle: "Severidad de afectación menor a demolición"
      },
      {
        id: "servicios",
        nombre: "Servicios Cercanos",
        score: 7.5,
        peso_aplicado: 4,
        fuente: "DENUE INEGI",
        dataset_id: "denue",
        consultado_en: "2026-04-18",
        dato_bruto: "Excelente cobertura médica, escolar y súper",
        detalle: "Todo a menos de 10 min caminando"
      }
    ],
    faltantes: [
      { id: "ecobici", razon: "Fallo conexión GBFS (Simulado)" }
    ]
  },
  resumen: "<h3>Resumen Ejecutivo: Narvarte Poniente</h3><p>Evaluación general sólida (7.6). Es una zona céntrica, famosa por su inmejorable acceso a transporte y oferta comercial (taquerías, supers, servicios). Los mayores compromisos a considerar de este punto de la CDMX son en general el riesgo sísmico por ser zona de transición y episodios de mala calidad del aire arrastrada al centro-sur de la ciudad.</p>"
};

export function useChat() {
  const isTyping = ref(false);
  const messages = ref([]);
  // preferences simulados
  const preferences = ref({
    idioma: 'es',
    prioridad_weights: {
      seguridad: 20,
      sismico: 18,
    }
  });

  const sendMessage = async (messageText) => {
    // 1. Agregar el msg del usuario al history
    messages.value.push({ role: 'user', content: messageText });
    isTyping.value = true;

    try {
      const isMock = import.meta.env.VITE_MOCK === '1';

      if (isMock) {
        // Simular retraso de MCP
        await new Promise(r => setTimeout(r, 1200));

        // Regresar el Mock Fixture
        messages.value.push({
          role: 'assistant',
          content: "Aquí tienes la evaluación del lugar:",
          reportData: MOCK_RESPONSE
        });
      } else {
        // Modo real API Gateway!
        const BASE_URL = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8000';
        const res = await axios.post(`${BASE_URL}/chat`, {
          messages: messages.value.map(m => ({ role: m.role, content: m.content })),
          preferences: preferences.value
        }, {
          timeout: 120000,   // 2 min — Claude tool-use loop puede tardar ~75s
          headers: { 'Content-Type': 'application/json' }
        });
        
        messages.value.push({
          role: 'assistant',
          content: res.data.content || "Reporte generado.",
          reportData: res.data.reportData || null
        });
      }
    } catch (e) {
      console.error(e);
      const isTimeout = e.code === 'ECONNABORTED' || e.message?.includes('timeout');
      messages.value.push({
        role: 'assistant',
        content: isTimeout
          ? '⏳ La consulta tardó más de lo esperado. El análisis de Claude puede tomar hasta 90 segundos — intenta de nuevo.'
          : '⚠️ Hubo un error al contactar al servidor. Verifica que el gateway esté corriendo en localhost:8000.'
      });
    } finally {
      isTyping.value = false;
    }
  };

  return { isTyping, messages, sendMessage, preferences };
}
