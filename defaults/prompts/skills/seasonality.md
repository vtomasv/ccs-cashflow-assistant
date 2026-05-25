# Skill: Estacionalidad

## Objetivo
Modelar correctamente los patrones estacionales del negocio para proyecciones más realistas.

## Patrones por Industria

### Retail / Comercio
| Mes | Factor | Razón |
|-----|--------|-------|
| Ene | 0.7 | Post-navidad, menor gasto |
| Feb | 0.7 | Vuelta a clases |
| Mar | 0.9 | Normalización |
| Abr | 0.9 | Estable |
| May | 1.0 | Día de la madre |
| Jun | 0.9 | Invierno |
| Jul | 0.8 | Vacaciones invierno |
| Ago | 0.9 | Estable |
| Sep | 1.1 | Fiestas patrias |
| Oct | 1.0 | Estable |
| Nov | 1.2 | Black Friday |
| Dic | 1.5 | Navidad |

### Alimentos / Panadería
| Mes | Factor | Razón |
|-----|--------|-------|
| Ene | 0.8 | Vacaciones |
| Feb | 0.8 | Verano, menos consumo pan |
| Mar | 1.0 | Vuelta a rutina |
| Abr-May | 1.1 | Otoño, más consumo |
| Jun-Ago | 1.2 | Invierno, más pan/pasteles |
| Sep | 1.3 | Fiestas patrias |
| Oct-Nov | 1.0 | Estable |
| Dic | 1.2 | Fiestas, pasteles navideños |

### Servicios Profesionales
| Mes | Factor |
|-----|--------|
| Ene-Feb | 0.6 (vacaciones) |
| Mar-Jun | 1.1 (alta demanda) |
| Jul | 0.8 (vacaciones invierno) |
| Ago-Nov | 1.1 (alta demanda) |
| Dic | 0.7 (cierre de año) |

## Fuentes de Datos
- Información directa del usuario sobre meses altos/bajos
- Búsqueda de mercado online para el sector
- Patrones históricos de la industria
- Eventos locales (fiestas patrias, navidad, etc.)

## Aplicación
El factor de estacionalidad se multiplica directamente por los ingresos base del mes:
```
Ingresos_Mes = Ingresos_Base × Factor_Estacionalidad[mes]
```
