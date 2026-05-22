# Plan de Desarrollo: Mejoras Profundas en el Plugin de Cashflow

Este documento detalla la arquitectura y el plan de desarrollo para implementar las mejoras profundas en el plugin de flujo de caja (**CCS Cashflow Assistant**) para Pinokio, con el fin de proporcionar una experiencia offline avanzada para PYMEs.

## 1. Objetivos del Rediseño

1. **Creación de Cashflow Mes a Mes con Notificaciones Contextuales**: El proceso de generación de flujo de caja ya no será un proceso de caja negra de una sola llamada larga. Se simulará mes a mes, y en cada paso se notificará al usuario sobre eventos específicos de su negocio (ej: "Simulando la compra de masa madre de nuevos clientes para el mes de Mayo").
2. **Entrevista Inteligente y Priorizada**: Un entrevistador financiero estructurado que cubra los 22 puntos críticos del negocio en un máximo de 8 preguntas por turno, proponiendo supuestos razonables cuando falte información y marcándolos explícitamente.
3. **Búsqueda de Mercado e Integración de Estacionalidad**: Capacidad para realizar búsquedas en internet sobre el mercado específico del usuario (ej: panaderías en Chile, tiendas de ropa en Colombia) para extraer tendencias de mercado, inflación y estacionalidad reales y aplicarlas a la proyección.
4. **Simulación Probabilística Monte Carlo y Métricas Robustas**: Motor financiero local avanzado que soporte simulaciones Monte Carlo, análisis de sensibilidad por variable, cálculo de runway, break-even operativo, margen bruto, margen EBITDA, necesidad máxima de financiamiento y probabilidad de insolvencia.
5. **Versionado de Escenarios y Comparación**: Capacidad para guardar múltiples versiones de escenarios, comparar el forecast original contra el forecast simulado probabilísticamente y sugerir opciones de financiamiento y optimización de caja.
6. **Interfaz Web Dinámica**: Visualizaciones ricas y dinámicas con gráficos interactivos (Chart.js) útiles para un comerciante, sin tecnicismos innecesarios.

---

## 2. Arquitectura del Motor Financiero Modular

El backend se dividirá en módulos bien definidos para garantizar el código limpio, mantenible y optimizado para hardware limitado:

```
server/
├── app.py                      # API principal FastAPI y endpoints
├── financial_engine/           # Motor financiero modular
│   ├── __init__.py
│   ├── core.py                 # Estructuras de datos y normalización básica
│   ├── monte_carlo.py          # Simulador probabilístico (Monte Carlo) y sensibilidad
│   └── metrics.py              # Cálculo de métricas avanzadas (Runway, Break-even, EBITDA)
├── interview_manager.py        # Gestor de la entrevista estructurada y supuestos
└── market_research.py          # Módulo de búsqueda en internet y extracción de estacionalidad
```

### 2.1. Métricas Financieras Soportadas

| Métrica | Definición / Fórmula | Utilidad para el Comerciante |
| :--- | :--- | :--- |
| **Caja Mínima** | El saldo mínimo proyectado en todo el período de 12 meses. | Identifica el momento de mayor tensión de liquidez. |
| **Mes de Caja Negativa** | Primer mes donde el saldo acumulado cae por debajo de cero. | Alerta temprana para buscar financiamiento preventivo. |
| **Break-Even Operativo** | Nivel de ventas donde Ingresos Operativos = Costos Fijos + Costos Variables. | Indica el mínimo de ventas necesario para no perder dinero. |
| **Runway** | Caja Inicial / Gasto Neto Mensual Promedio (si hay pérdidas). | Cuántos meses puede sobrevivir la empresa con la caja actual. |
| **Margen Bruto** | (Ventas - Costos Variables) / Ventas. | Eficiencia de la producción o compra de mercancía. |
| **Margen EBITDA** | EBITDA / Ventas. | Rentabilidad operativa pura antes de intereses, impuestos, depreciación. |
| **Necesidad Máxima de Financiamiento** | El valor absoluto del saldo negativo más profundo + un colchón de seguridad. | Cuánto dinero pedir prestado exactamente. |
| **Probabilidad de Insolvencia** | % de iteraciones de Monte Carlo donde la caja acumulada cae por debajo de 0. | Nivel de riesgo real del negocio ante la incertidumbre. |
| **Sensibilidad por Variable** | Impacto en la caja final al variar ±10% las ventas, costos, etc. | Identifica qué variable afecta más al negocio. |

---

## 3. Plan de Implementación por Fases

### Fase 1: Implementación del Motor Financiero Modular (`financial_engine/`)
- Crear `financial_engine/core.py` para representar el modelo de datos mensual.
- Crear `financial_engine/metrics.py` para calcular de manera determinista el Runway, Break-Even, EBITDA, Margen Bruto, Caja Mínima y Necesidad de Financiamiento.
- Crear `financial_engine/monte_carlo.py` para realizar simulación probabilística (1,000 iteraciones) variando de forma aleatoria (distribución normal/triangular) las ventas y costos variables según el nivel de incertidumbre, calculando la probabilidad de insolvencia y la sensibilidad de las variables.

### Fase 2: Rediseño de la Entrevista y Gestor de Supuestos
- Modificar el prompt de `financial_interviewer.md` para aplicar el límite estricto de máximo 8 preguntas por turno.
- Implementar un parser en `server/interview_manager.py` que analice las respuestas del usuario y determine qué datos de los 22 puntos críticos ya se tienen, cuáles faltan y proponga supuestos razonables para los faltantes (marcando explícitamente `"is_assumption": true`).

### Fase 3: Búsqueda de Mercado y Estacionalidad
- Implementar en `server/market_research.py` una función de búsqueda en internet usando consultas estructuradas según el sector y país del usuario.
- Extraer datos de estacionalidad (ej: meses de alta y baja demanda para panaderías) y factores macroeconómicos (inflación local esperada).
- Integrar estos datos como factores multiplicadores en la proyección del flujo de caja.

### Fase 4: Simulación Mes a Mes con Notificaciones de Progreso
- Implementar un generador paso a paso en el backend. En lugar de generar los 12 meses de golpe con el LLM, el backend iterará mes a mes.
- Para cada mes, se generará un mensaje contextualizado del negocio (ej: "Mes 3 (Marzo): Simulando la estacionalidad de venta de masa madre por inicio de otoño").
- El frontend hará polling y mostrará estas notificaciones en tiempo real con una barra de progreso dinámica.

### Fase 5: Interfaz Web Dinámica, Versionado y Comparación
- Actualizar `app/index.html` para incluir:
  - Dashboard con métricas clave y semáforos de riesgo.
  - Gráfico de líneas interactivo que compare el **Forecast Creado (Base)** vs el **Forecast Simulado (Monte Carlo / Escenario)**.
  - Gráfico de barras de sensibilidad (Tornado Chart) para mostrar qué variables afectan más.
  - Sección de recomendaciones de financiamiento y optimización de caja basadas en las métricas obtenidas.
  - Panel de gestión de versiones para guardar, cargar y borrar múltiples escenarios.

---

## 4. Cronograma Estimado

| Tarea | Duración Estimada | Estado |
| :--- | :--- | :--- |
| **Diseño y Arquitectura** | 1 hora | Completado |
| **Motor Financiero (Métricas y Monte Carlo)** | 3 horas | Pendiente |
| **Entrevista Inteligente y Supuestos** | 2 horas | Pendiente |
| **Búsqueda de Mercado e Internet** | 2 horas | Pendiente |
| **Generación Paso a Paso y Notificaciones** | 2 horas | Pendiente |
| **Frontend UI (Dashboard, Gráficos, Escenarios)** | 4 horas | Pendiente |
| **Pruebas de Integración y Depuración** | 2 horas | Pendiente |
| **Documentación y Entrega** | 1 hora | Pendiente |
