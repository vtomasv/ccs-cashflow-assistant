# CCS Cashflow Assistant

Herramienta de flujo de caja inteligente con IA local para PYMEs, desarrollada como plugin para [Pinokio](https://pinokio.computer). Utiliza agentes conversacionales basados en **Ollama** y modelos **Meta Llama** para crear, analizar y proyectar flujos de caja de manera completamente offline.

## Descripción

CCS Cashflow Assistant permite a las pequeñas y medianas empresas entender su situación financiera, construir escenarios de negocio y tomar mejores decisiones. El sistema funciona mediante una interfaz conversacional donde un agente financiero local guía al usuario para recopilar la información necesaria y construir un flujo de caja personalizado.

### Funcionalidades principales

| Funcionalidad | Descripción |
|---|---|
| **Entrevista guiada** | Un agente conversacional recopila datos financieros de la empresa mediante preguntas simples y progresivas |
| **Generación automática** | Construye un flujo de caja mensual proyectado a 12 meses basado en la entrevista |
| **Dashboard inteligente** | Visualiza ingresos, egresos, márgenes, saldo acumulado y alertas financieras |
| **Simulador de escenarios** | Ajusta variables (ventas, costos, inflación, contrataciones) y observa el impacto en tiempo real |
| **Simulación conversacional** | Escribe instrucciones en lenguaje natural como "sube los precios un 8% desde marzo" |
| **Exportación** | Descarga el flujo de caja completo en formato Excel o CSV |

## Arquitectura

```
ccs-cashflow-assistant/
├── pinokio.js          # Configuración y menú del plugin (único .js)
├── icon.png            # Icono del plugin 512x512
├── install.json        # Instalación automática 1-click
├── start.json          # Inicio del servidor como daemon
├── stop.json           # Parada del servidor
├── reset.json          # Desinstalación (conserva datos)
├── requirements.txt    # Dependencias Python
├── app/
│   ├── index.html      # Frontend autocontenido (HTML/CSS/JS)
│   ├── logo-ccs.svg    # Logo CCS
│   └── fonts/          # Tipografía DM Sans
├── server/
│   └── app.py          # Backend FastAPI
├── defaults/
│   ├── agents.json     # Configuración base de agentes
│   └── prompts/        # Prompts de sistema para cada agente
├── tests/
│   └── test_app.py     # Pruebas unitarias y de integración
└── data/               # Datos del usuario (no incluido en git)
```

## Requisitos del sistema

| Requisito | Mínimo | Recomendado |
|---|---|---|
| RAM | 4 GB | 8 GB o más |
| Disco | 5 GB libres | 10 GB libres |
| SO | Windows 10, macOS 12, Ubuntu 20.04 | Última versión |
| Pinokio | v2.0+ | Última versión |

## Modelos de IA según RAM

| RAM disponible | Modelo descargado | Uso |
|---|---|---|
| Menos de 6 GB | `llama3.2:1b` | Tareas simples |
| 6-12 GB | `llama3.2:3b` | Uso general |
| Más de 12 GB | `llama3.1:8b` | Análisis complejo |

## Instalación

1. Abre **Pinokio** en tu computador.
2. Ve a la sección de descarga de plugins.
3. Ingresa la URL de este repositorio.
4. Haz click en **Instalar**. El proceso es completamente automático e incluye:
   - Verificación e instalación de Ollama
   - Descarga del modelo de IA apropiado según tu RAM
   - Creación del entorno virtual Python
   - Instalación de dependencias
   - Inicialización de datos
5. Una vez instalado, haz click en **Iniciar**.

## Uso

### Paso 1: Crear una empresa
Haz click en "Crear nueva empresa" e ingresa los datos básicos (nombre, sector, tamaño).

### Paso 2: Entrevista financiera
El agente te hará preguntas sobre tu negocio: ingresos, costos, gastos, deudas, impuestos, etc. No necesitas ser experto financiero.

### Paso 3: Generar flujo de caja
Una vez que el agente tenga suficiente información, presiona "Generar Flujo de Caja" para crear la proyección a 12 meses.

### Paso 4: Analizar en el dashboard
Revisa los gráficos de ingresos vs gastos, distribución de costos, alertas financieras y recomendaciones.

### Paso 5: Simular escenarios
Usa los sliders o escribe instrucciones en lenguaje natural para simular cambios y ver su impacto.

### Paso 6: Exportar
Descarga tu flujo de caja en Excel o CSV para compartir con socios, contadores o bancos.

## Agentes de IA

| Agente | Rol | Modelo sugerido |
|---|---|---|
| Entrevistador Financiero | Recopila datos de la empresa mediante conversación guiada | `llama3.2:3b` |
| Analista de Flujo de Caja | Construye la estructura financiera a partir de los datos | `llama3.1:8b` |
| Simulador de Escenarios | Calcula el impacto de cambios en variables | `llama3.1:8b` |

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Plataforma | Pinokio |
| Backend | FastAPI (Python) |
| Frontend | HTML/CSS/JS Vanilla |
| Gráficos | Chart.js |
| IA Local | Ollama + Meta Llama |
| Persistencia | JSON en disco |
| Exportación | openpyxl (Excel), CSV nativo |

## Desarrollo

### Ejecutar tests

```bash
cd ccs-cashflow-assistant
pip install pytest
python -m pytest tests/test_app.py -v
```

### Ejecutar servidor en desarrollo

```bash
cd ccs-cashflow-assistant
pip install -r requirements.txt
python server/app.py --port 7860
```

## Licencia

MIT License

## Créditos

Desarrollado para la **Cámara de Comercio de Santiago (CCS)** como parte del programa de digitalización de PYMEs con inteligencia artificial local.
