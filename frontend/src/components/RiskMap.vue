<script setup>
import { ref, onMounted, watch } from 'vue'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'

const props = defineProps({
  lat: { type: Number, required: true },
  lng: { type: Number, required: true },
  zoom: { type: Number, default: 15 }
})

const mapContainer = ref(null)
let map = null
let marker = null

const initMap = () => {
  if (!mapContainer.value) return
  
  // Wait a tick to ensure container is fully rendered
  setTimeout(() => {
    map = L.map(mapContainer.value, {
      zoomControl: false,
      attributionControl: false
    }).setView([props.lat, props.lng], props.zoom)

    // Dark theme map to match UI
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19
    }).addTo(map)

    // Custom marker with pulse effect
    const customIcon = L.divIcon({
      className: 'custom-map-marker',
      html: `<div class="marker-pin"></div><div class="marker-pulse"></div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    })

    marker = L.marker([props.lat, props.lng], { icon: customIcon }).addTo(map)
  }, 100)
}

onMounted(() => {
  initMap()
})

watch(() => [props.lat, props.lng], ([newLat, newLng]) => {
  if (map && marker) {
    map.setView([newLat, newLng], props.zoom)
    marker.setLatLng([newLat, newLng])
  }
})
</script>

<template>
  <div class="map-wrapper">
    <div ref="mapContainer" class="map-container"></div>
    <div class="map-overlay"></div>
  </div>
</template>

<style scoped>
.map-wrapper {
  width: 100%;
  height: 250px;
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-top: 16px;
  background: #1e293b;
}

.map-container {
  width: 100%;
  height: 100%;
  z-index: 1;
}

.map-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  box-shadow: inset 0 0 40px rgba(15, 23, 42, 0.8);
  z-index: 2;
}

:deep(.custom-map-marker) {
  display: flex;
  justify-content: center;
  align-items: center;
}

:deep(.marker-pin) {
  width: 16px;
  height: 16px;
  background: #3b82f6;
  border: 2px solid white;
  border-radius: 50%;
  z-index: 2;
  box-shadow: 0 2px 5px rgba(0,0,0,0.5);
}

:deep(.marker-pulse) {
  position: absolute;
  width: 30px;
  height: 30px;
  background: rgba(59, 130, 246, 0.4);
  border-radius: 50%;
  z-index: 1;
  animation: pulse-ring 2s ease-out infinite;
}

@keyframes pulse-ring {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2.5); opacity: 0; }
}
</style>
