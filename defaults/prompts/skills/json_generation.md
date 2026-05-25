# Skill: Generación de JSON

## Objetivo
Generar respuestas en formato JSON válido y parseable para la comunicación entre agentes y el motor financiero.

## Reglas Estrictas

El JSON generado debe ser siempre válido según el estándar RFC 8259. No se permiten comentarios dentro del JSON. Todas las claves deben estar en snake_case. Los valores numéricos no deben tener comillas. Los arrays vacíos se representan como [] y los objetos vacíos como {}.

## Formato de Respuesta
La respuesta debe contener SOLO el JSON, sin texto adicional antes o después. No usar bloques de código markdown (```json). El JSON debe empezar con { y terminar con }.

## Manejo de Errores
Si no es posible generar un JSON válido con la información disponible, retornar:
```json
{"error": "descripción del problema", "partial_data": {...}}
```

## Validación
Antes de retornar, verificar mentalmente que el JSON sea parseable, que todos los campos requeridos estén presentes, y que los tipos de datos sean correctos.
