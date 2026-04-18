# Demo Questions - Analizador Urbano CDMX

Durante el pitch y el demo final de 90 segundos, ejecutaremos las siguientes 3 preguntas EXACTAS para mostrar las capacidades de puntuación de la aplicación:

### PREGUNTA 1: "El caso ideal"
> *"¿Qué tan buena zona para vivir es la colonia Narvarte Poniente?"*
- **Objetivo:** Demuestra el caso base donde vemos un puntaje "Bueno" (verde), un excelente sistema de transporte público (GTFS) pero con algunas áreas de oportunidad mitigables como el riesgo sísmico.

### PREGUNTA 2: "El caso extremo"
> *"Quiero rentar en Polanco, ¿me conviene?"*
- **Objetivo:** Mostrar los contrastes brutales. Seguramente altos servicios y movilidad, pero costos y gentrificación / densidad que bajan la calidad. (Nota: Esto depende de cómo la API haya analizado Polanco, pero la intención es contrastar con Narvarte).

### PREGUNTA 3: "La falla degradada elegante"
> *"¿Cómo está la seguridad en la zona metropolitana / Naucalpan?"*
- **Objetivo:** Enseñar qué pasa cuando salimos del radar de CDMX. El MCP probablemente no encuentre o no reciba respuesta de SIMAT/CKAN. Demostraremos cómo los datos se enmarcan en `["faltantes"]` y el sistema recalcula los pesos de las gráficas equitativamente entre las dimensiones restantes, ofreciendo una métrica a pesar de los bloqueos de información.
