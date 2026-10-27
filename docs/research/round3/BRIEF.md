# Ronda 3 — 100 hacks nuevos de trading (brief del equipo)

> Canal del Hub: `opentrading-100-hacks` · Coordinador (TL): `sockeye-tl`
> Fecha de arranque: 2026-10-27

## Objetivo

Generar **100 hipótesis nuevas** de edge informacional en cripto, en la línea de
`docs/research/signal-hypotheses.md` (léelo completo antes de empezar), y
converger a un **top-10 para backtest**.

"Nueva" significa: no repetida ni reempaquetada de lo que ya está en
`signal-hypotheses.md` (rondas 1-2, §4b-§4i: entropía/percolación, peg de
stablecoins, blob-fee, builders, whales, unlocks, base spot-perp, OI-precio,
DVOL, Tether, cola de validadores, Hyperliquid smart-money, variantes de #6…).
Una variante solo cuenta si cambia el **mecanismo** o la **fuente de datos**, y
debe decir explícitamente en qué se diferencia de la idea previa.

## Línea roja (no negociable)

Solo datos **públicos/observables**. Nada de insider/MNPI, acceso no
autorizado, explotar vulnerabilidades, ni MEV/sandwich contra usuarios.
"Hack" = lectura astuta de información pública, no un ataque.

## Lecciones previas que deben guiar la ideación

- Lo único con señal hasta ahora: **posicionamiento apalancado por derivados**
  (#6 funding, F5 vol implícita). Flujos de oferta on-chain y topología: null tras null.
- El bot corre en un *scheduler* de minutos: preferir horizontes de **horas/días**.
  Microestructura sub-minuto se marca como "research-only".
- Lo que más mató candidatas fue la **disponibilidad de datos**: cada idea debe
  traer ruta de datos concreta (endpoint, dataset, rango histórico) y si es
  gratis, gated (requiere key/pago) o requiere *forward-collection*.
- Cuidado con espejismos de ventanas solapadas: proponer el test no-solapado +
  placebo/permutación desde la ficha.

## Reparto

| Sesión | Modelo Kiro | Familia | Archivo de salida | Cantidad |
|---|---|---|---|---|
| K1 | claude-sonnet-5.5 | Derivados / posicionamiento (funding, opciones, liquidaciones, OI por venue, perps en DEX) | `round3/k1-derivados.md` | 25 |
| K2 | claude-sonnet-5.5 | Timing / metadata pública (listings, mantenimientos, status pages, GitHub, gobernanza, anuncios) | `round3/k2-timing-metadata.md` | 25 |
| K3 | claude-sonnet-5.5 | Calendario y cross-asset (vencimientos, CME, macro, ETF/índices, horario TradFi) | `round3/k3-calendario-crossasset.md` | 25 |
| K4 | claude-sonnet-5.5 | Mecanismos DeFi con lag estructural (liquidaciones lending, oráculos, bridges, LST, L2) | `round3/k4-defi-lag.md` | 25 |
| K5 | claude-opus-5.5 | Revisor / convergencia | `round3/convergence.md` | top-10 |

Cada sesión escribe **solo en su archivo**. Nadie edita `signal-hypotheses.md`:
lo integra el TL al final.

## Formato de cada ficha (K1-K4)

```markdown
### K1-07 — <Nombre corto>
- **Mecanismo:** por qué debería funcionar (razón estructural, no data-mining).
- **Lag / persistencia:** por qué no se arbitra al instante.
- **Señal y horizonte:** qué se mide, cuándo dispara, horizonte (h/días), long/short.
- **Datos:** fuente concreta + rango histórico + [gratis | gated | forward-collect].
- **Test de refutación:** event-study / IC no-solapado / placebo o permutación / OOS.
- **Diferencia con lo ya probado:** idea previa más cercana y en qué cambia (o "ninguna").
- **Fuentes:** enlaces verificables (docs de API, papers, posts). Si no hay, decirlo.
- **Score §1:** Mecanismo x · Lag x · Falsabilidad x · Costo x · Novedad x · Retorno x → **ponderado x.x**
```

Al final del archivo, una tabla resumen (id, nombre, score, datos, fit bot).

## K5 — revisor

1. Espera a que K1-K4 reporten `completed` en el hilo (no empieces antes).
2. Deduplica entre familias y contra `signal-hypotheses.md`; descarta las que
   violen la línea roja o no tengan ruta de datos.
3. Re-puntúa con criterio uniforme (los autores tienden a inflar su score).
4. Entrega `round3/convergence.md`: conteo final de ideas válidas, descartes con
   motivo, y **top-10 para backtest** ordenado por testeable-ya × mecanismo × novedad,
   con el plan de test de cada una.

## Coordinación (por archivos; el canal del Hub no admite sesiones Kiro)

El Hub solo incorpora al canal a trabajadores lanzados por su flota (Claude
Code/Codex), así que las sesiones Kiro **no** se suman al canal ni llaman a
`memory_chat_*`. La coordinación pasa por el repo:

- **Estado:** cada sesión mantiene `round3/status/<ID>.md` (p. ej.
  `status/K1.md`) con una línea por evento:
  `<ISO-8601> | STARTED|PROGRESS n/25|BLOCKED <motivo>|DELIVERED <n> ideas`.
  Escribir `STARTED` al empezar y `DELIVERED` solo cuando el archivo de salida
  esté completo, con su tabla resumen.
- **Dudas para el TL:** agrégalas al final de tu `status/<ID>.md` como
  `QUESTION: ...`. El TL responde en `round3/status/TL.md`, que debes releer
  antes de cerrar.
- **K5:** arranca cuando los cuatro `status/K1..K4.md` tengan `DELIVERED`.
  Mientras tanto puede leer `signal-hypotheses.md` y preparar su criterio de
  deduplicación.
- No commitear ni pushear: el TL integra y abre el PR.
