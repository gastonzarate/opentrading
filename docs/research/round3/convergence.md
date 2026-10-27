# Ronda 3 — Convergencia (K5, revisor)

> Autor: `k5-kiro` · Fecha: 2026-10-27 · Entrada: `round3/k1-derivados.md`,
> `round3/k2-timing-metadata.md`, `round3/k3-calendario-crossasset.md`,
> `round3/k4-defi-lag.md` (100 fichas) + `docs/research/signal-hypotheses.md` (rondas 1-2).
> Rol: deduplicar entre familias y contra el histórico, descartar lo que viole la
> línea roja o no tenga ruta de datos, **re-puntuar con criterio uniforme** (los
> autores inflan su propio score) y entregar un **top-10 para backtest**.
> No se edita `signal-hypotheses.md` ni ningún archivo de otra sesión. Sin commit/push.

---

## 0. TL;DR

- **Ideas recibidas:** 100 (K1 25 · K2 25 · K3 25 · K4 25).
- **Línea roja:** 0 violaciones. Las 100 usan solo datos públicos/observables.
- **Descartadas por redundancia dura con el histórico ya refutado:** 7.
- **Fusionadas (duplicados cross-familia): 9 fichas colapsan en 4 representantes → se
  eliminan 5 fichas del conteo de distintas** (se conserva la mejor especificada de cada grupo).
- **Ideas válidas y nuevas que sobreviven el filtro:** **88** (100 − 7 descartes − 5 fusionadas).
- **De esas 88, degradadas a "research-only / no ejecutable por el scheduler" (sub-minuto):** 6.
- **De esas 88, marcadas data-gated / forward-collect / underpowered (no "testeable esta semana"):** ~21.
- **Top-10 para backtest:** ver §5. Encabezan **señales de posicionamiento por
  derivados leídas por un canal/fuente nueva y con data gratis ya disponible**
  (COT CFTC, curva de funding, dispersión de funding entre venues, flujo OI por
  margen, residual beta-funding, HF de lending, cola de redención LST, FOMC drift,
  net-liquidity macro, concentración de OI en Hyperliquid).

**Criterio rector (del brief):** ordenar por **testeable-ya × mecanismo × novedad**,
sesgado por la lección meta del libro: *lo único con señal sostenida es el
posicionamiento apalancado por derivados; los flujos de oferta on-chain y la
topología de red dan null tras null.* Por eso una idea con mecanismo de
posicionamiento + data gratis ya bajada le gana a una idea "novel pero gated" o a
una de topología por más linda que suene.

---

## 1. Método de re-scoring uniforme

Reaplico las 6 dimensiones §1 del libro (Mecanismo 25% · Lag 20% · Falsabilidad 15% ·
Costo 15% · Novedad 15% · Retorno 10%) con **tres correcciones de calibración** que
los autores tendieron a saltarse:

1. **Costo = disponibilidad real de datos, no "existe un endpoint".** Si la historia
   exige *forward-collect* (Deribit OI-por-strike, opciones en general) o una key/pago
   (Amberdata, beaconcha.in, Chaos/Gauntlet), el Costo baja a ≤2.5 aunque el autor haya
   puesto 3-4. Lo que más mató candidatas en rondas previas fue exactamente esto.
2. **Novedad descontada por "primo cercano ya refutado".** Si la idea es una variante
   de algo que ya murió (base, OI-precio, peg, unlock, topología), la Novedad efectiva
   baja salvo que el *mecanismo* cambie de verdad (no solo la etiqueta).
3. **Retorno/Mecanismo descontados para sub-powered.** Eventos trimestrales/raros
   (triple witching, DSR, bad-debt, bridge-halt, onboarding) → N chico → el test no
   puede ser concluyente aunque el mecanismo sea real. Se nota en el ranking.

El score re-calibrado que uso en el top-10 es **mi** número; cuando difiere del autor
lo digo. No reescribo los 100; solo re-puntúo los candidatos serios y documento los
descartes.

---

## 2. Línea roja — chequeo

Las 100 fichas declaran y respetan la restricción: solo feeds oficiales, on-chain
público, registries abiertos, APIs gratis/gated-declaradas. **Ninguna** usa
insider/MNPI, acceso no autorizado, explotación de vulnerabilidades ni MEV/sandwich.

Zonas que miré con lupa y por qué pasan:
- **K2-18 (EDGAR/filings timestamp)** y **K2-23 (CT-logs/job postings)** rozan el
  "grey-hat" de §4g, pero leen feeds oficiales públicos con timestamp; no hay acceso
  privilegiado. OK (con el caveat de datos, abajo).
- **K1-06 / K1-15 / K1-25 (Hyperliquid posiciones por wallet)**: usan la API pública de
  clearinghouse; es lectura de estado público, no copy-trading no-consentido ni ataque.
  OK. (L7 del libro ya sentó que mirar posiciones públicas es admisible.)
- Ninguna ficha propone adelantarse a órdenes de usuarios ni manipular. OK.

**Resultado: 0 descartes por línea roja.**

---

## 3. Deduplicación

### 3a. Descartes por redundancia dura con `signal-hypotheses.md` (7)

Estas repiten mecanismo *y* naturaleza de dato de algo ya refutado/validado, sin un
cambio de mecanismo que justifique re-testear. Se documentan como **descartadas**
(no entran al conteo de "nuevas"); varias igual sirven como confirmación barata si
alguien quiere cerrar el expediente.

| Ficha | Choca con | Motivo del descarte |
|---|---|---|
| K3-11 CME Basis Term-Structure | F3 base spot-perp (❌ refutado ambos signos) | Es basis/carry con fecha; F3 ya mostró que el basis no tiene edge direccional. Cambiar "retail perp" por "CME institucional" no cambia el *mecanismo* (carry), solo el participante. Prior ~null. Si se corre, es para cerrar F3, no por expectativa. |
| K3-03 Funding Reset × Expiry | #6 funding + "00:00 impulse" (❌) | Interacción funding×calendario; el propio autor admite "si no aporta sobre #6 se descarta". El libro ya mostró que el timing de settlement no agrega (00:00 murió por control 12:00). Prior muy bajo. |
| K3-24 Asia-Session Funding Asymmetry | #6 + #1 (⚠️ débil) | Misma confesión del autor ("si no supera a #6 se descarta"). Cruza dos cosas ya exprimidas (funding + sesión horaria). Score autor 2.9, el más bajo del bloque. |
| K1-20 Funding Streak (racha de signo) | #6 nivel + §4i-v8 aceleración | "Duración del signo" es casi colineal con nivel/aceleración ya probados; el partial-IC que pide probablemente ya está cubierto por v8. Redundante. |
| K1-03 Funding Jerk (2ª derivada) | §4i-v8 (1ª derivada, ya es mejora conocida) | La 2ª derivada de una serie ruidosa de funding es casi todo ruido; v8 (1ª derivada) ya captura "el crowding se da vuelta". Aporte marginal dudoso. Se mantiene *una* idea de forma-de-funding (ver top-10 K1-01), no tres. |
| K2-10 Stablecoin Mint/Redeem Timing | §4d stablecoin-supply-flow (🟡 débil/null) | "Cadencia de mints" vs "nivel de supply": mismo driver de oferta de stablecoin, ya probado débil. El autor exige aporte marginal; prior bajo por el patrón "oferta on-chain = null". |
| K2-09 Exchange Cold-to-Hot Reshuffle | §4b whale netflow (❌) | Movimiento interno de infra del exchange como proxy de flujo; score autor 2.6; la familia "flujo on-chain de exchange" ya dio null. Mecanismo blando. |

### 3b. Fusiones (duplicados cross-familia → se conserva la mejor especificada) (9 fichas → 4 representantes = 5 eliminadas del conteo)

| Grupo | Fichas | Se conserva | Motivo |
|---|---|---|---|
| On-chain vs CEX funding spread | **K4-20** / K1-16 | **K4-20** | Idéntico mecanismo (borrow-rate Aave anualizado vs funding perp). K4-20 lo especifica mejor (control explícito por #6, data ya bajada). K1-16 (DEX funding vs CEX) es la variante GMX/HL → se absorbe como test secundario. |
| Max-pain pin drift | **K3-01** / K1-09 | **K3-01** | Misma idea (deriva hacia max-pain pre-expiry). K3-01 está mejor especificada (centro de masa de OI, ciclo mensual, placebo). K1-09 se funde. |
| Index reconstitution | **K3-19** / K2-12 | **K3-19** | Front-running de rebalanceo de índices. K3-19 trae el placebo tipo-F4 explícito (clave). K2-12 se funde. |
| Dealer-gamma / OI-por-strike | K1-08 (GEX) / K3-02 (gamma flip) / K3-06 (OI migration) | **K3-02** como representante operable | Los tres dependen de OI de opciones por strike. K3-02 (régimen de vol post-trimestral) es el único que NO necesita OI-por-strike histórico (usa solo el calendario de expiry + klines) → es el testeable-ya del grupo. K1-08/K3-06 quedan como "gated/forward-collect" (abajo). |

### 3c. Degradadas a research-only (horizonte sub-minuto; el scheduler no las ejecuta) (6)

No se descartan como *ideas* (varias tienen mecanismo real), pero **no entran al
top-10** porque el bot corre en scheduler de minutos. Quedan como "research-only" o,
a lo sumo, feature de régimen si su pata de horas es operable.

- **K4-06** Pre-Heartbeat Liquidation Clustering (minutos).
- **K4-16** Sequencer-Downtime Dislocation (minutos; la pata de "riesgo acumulado" es régimen).
- **K1-13** Taker buy/sell imbalance (4-24h; límite, más research que gatillo).
- **K3-09** CME Settlement-Window Drift (1-2h alrededor del fixing).
- **K2-25 / K1-18** funding-settlement microtiming (la pata de horas es dudosa; ver 3a).
- **K4-05 / K4-07** oracle staleness / cross-oracle (la señal operable es el *estado*
  "DeFi rezagado"; la ejecución fina es sub-minuto → se las puede re-encuadrar como
  feature de régimen de 1-4h, pero con prior de "coincidente" tipo peg #2).

### 3d. Data-gated / forward-collect (no "testeable esta semana") (21)

Honestamente marcadas para que NO encabecen el top-10 aunque su novedad sea alta. El
muro es el mismo que mató a F1/F2: snapshot sí, historia no (sin pagar o sin
forward-collectar meses).

- **Opciones (Deribit OI-por-strike / IV por tenor):** K1-07, K1-08, K1-09(→fundida),
  K1-10, K1-23, K3-01(fwd), K3-05, K3-06. Snapshot gratis; historia = forward-collect o
  Amberdata/Laevitas (pago).
- **Hyperliquid/DEX posiciones agregadas:** K1-15, K1-25, K1-17, K4-23 (API pública pero
  historia densa = forward-collect de snapshots).
- **CME settlements histórico fino:** K3-04, K3-08, K3-11(→descartada). Gratis con delay;
  histórico limpio puede ser gated.
- **ETF (historia ~2a):** K3-17, K3-18 — no gated pero *underpowered* por historia corta.
- **Gated-free con key:** K2-13 (beaconcha.in), K2-14 (CoinMarketCal).
- **Forward-collect puro:** K2-23 (CT-logs parcial), K4-11 (LRT cliffs), K2-08 (TGE pre-market).

---

## 4. Conteo final

| Categoría | N |
|---|---|
| Fichas recibidas | 100 |
| Descartadas por redundancia dura con histórico (3a) | 7 |
| Fusionadas en otra (3b): K1-16, K1-09, K2-12, K1-08, K3-06 | 5 |
| **Ideas válidas y nuevas que quedan** | **88** |
| — de ellas, degradadas a research-only (3c, no top-10) | 6 |
| — de ellas, data-gated/forward-collect/underpowered (3d, no top-10) | ~21 |
| **Pool realista para backtest ya (gratis + horas/días + no redundante)** | **~40** |

> Nota: 100 − 7 (descartes) − 5 (fusionadas como duplicado) = **88 ideas distintas y
> válidas**. Las 6 research-only y las ~21 gated siguen siendo "válidas" como ideas,
> pero no son candidatas de backtest inmediato. El **top-10** sale del pool de ~40
> testeables-ya.

---

## 5. TOP-10 para backtest

Ordenado por **testeable-ya (data gratis ya disponible) × mecanismo (posicionamiento,
no oferta/topología) × novedad (canal/fuente nuevos)**. El score es **mi** re-cálculo
calibrado (col. "K5"), con el del autor entre paréntesis cuando difiere.

| # | id | Nombre | K5 (autor) | Datos | Fit bot |
|---|---|---|---|---|---|
| 1 | **K3-07** | CFTC COT Leveraged-Funds Net Position | **3.8** (3.8) | CFTC TFF CSV, 2018→hoy [gratis] | ✅ alto (semanal) |
| 2 | **K1-01** | Pendiente curva de funding (perp vs trimestral) | **3.7** (3.95) | Binance/Bybit funding+mark [gratis] | ✅ alto |
| 3 | **K1-02** | Dispersión de funding entre venues | **3.6** (3.93) | funding multi-venue [gratis] | ✅ alto |
| 4 | **K4-01** | Lending Liquidation Cascade Proximity (dist. de HF) | **3.6** (3.68) | Aave subgraph free-tier | ✅ alto (1-3d) |
| 5 | **K1-21** | Residual idiosincrático de beta-funding vs BTC | **3.5** (3.60) | funding BTC+alts [gratis] | ✅ alto |
| 6 | **K3-12** | FOMC Pre-Announcement Drift | **3.5** (3.7) | FOMC cal. + klines [gratis] | ✅ alto (~24h) |
| 7 | **K4-08** | LST Redemption-Queue Overhang | **3.5** (3.68) | Lido withdrawals RPC/subgraph | ✅ alto (1-5d) |
| 8 | **K1-11** | Flujo de OI por tipo de margen (coin-M vs USDT) | **3.4** (3.55) | Bybit/Binance OI [gratis] | ✅ alto |
| 9 | **K3-15** | Fed Net-Liquidity Weekly Delta | **3.4** (3.3) | FRED WALCL/RRP/TGA [gratis] | ✅ alto (1-2sem) |
| 10 | **K1-15** | Hyperliquid: concentración (HHI) del OI por wallet | **3.3** (3.68) | Hyperliquid info API [gratis/fwd] | ✅ alto |

**Por qué estas y no las de score-autor más alto:** K1-25 (3.63) y K1-08 (3.58) caen
por el muro de datos (Hyperliquid historia densa = forward-collect; GEX = OI-opciones
gated). Varias de opciones con novedad 4+ quedan fuera por el mismo motivo (lección
F1/F2). Entra en cambio K4-01/K4-08 (lending/LST) porque, pese a necesitar subgraph
free-tier, tienen **reloj de protocolo duro + oferta forzada endógena** — justo el
perfil que el insight meta marca como el de mayor prior.

### Plan de test por candidata

Batería común a todas (no la repito): **IC continuo con muestras NO-solapadas**
(una obs por período independiente), **placebo/permutación** (barajar fechas de la
señal vs retornos; exigir p<0.05), **OOS por mitades**, y **control por la señal
rápida equivalente** (funding de #6 y/o vol realizada) para probar aporte marginal.
Neto de fees donde haya P&L.

1. **K3-07 — COT Leveraged-Funds.** Bajar el CSV TFF de la CFTC (Bitcoin CME, ~400
   semanas). Señal = z-score del neto de *leveraged funds*. IC vs retorno fwd 1-2
   semanas (el dato es semanal → casi sin solape nativo). Control clave: funding de
   Binance de la misma semana (probar que el COT institucional aporta sobre el funding
   retail). Placebo: shuffle de la serie. Riesgo: lag de publicación de 3 días → usar
   SOLO el corte ya publicado (sin look-ahead). *El candidato nº1: posicionamiento, fuente
   regulatoria nueva, data gratis, horizonte compatible.*

2. **K1-01 — Curva de funding (perp vs trimestral).** Diferencial = funding perp
   anualizado − base anualizada del trimestral más cercano (mismo activo), z-score 30d.
   Event-study por terciles + IC no-solapado 1/2/3d. Control: separar de #6 (dispersión
   cross-sectional) y de F3 (base spot-perp) por construcción. Data ya bajable de
   Binance (`fundingRate` + `premiumIndexKlines` del trimestral). Baja el score del
   autor por el ajuste de novedad (es "forma de funding", primo de #6).

3. **K1-02 — Dispersión de funding entre venues.** σ (o rango) del funding del *mismo*
   símbolo across ≥4 venues (Binance/Bybit/OKX/Hyperliquid), z-score. **Control
   obligatorio por el nivel medio de funding** para aislar dispersión-entre-venues de
   nivel (que ya es #6). Si no sobrevive ese partial, se degrada. Eje genuinamente
   ortogonal a #6 (geografía del apalancamiento, no mix de activos).

4. **K4-01 — Densidad de HF en lending.** Reconstruir con el subgraph Aave V3 la
   distribución de precios-de-liquidación; densidad de colateral USD con liq-price
   dentro de −5/−10% del spot, normalizada por TVL. Event-study de retorno fwd 1/2/3d de
   WETH por decil de densidad. **Control por vol realizada 7d** (que la densidad no sea
   un proxy de vol). Placebo de fechas. Oferta forzada *endógena al precio* con gatillo
   contractual (HF=1) — mecanismo nuevo y limpio; el riesgo es el costo de indexar
   posiciones (subgraph free-tier alcanza para un primer corte en mainnet 2023→hoy).

5. **K1-21 — Residual de beta-funding vs BTC.** Regresión rolling del funding de cada
   alt contra el funding de BTC; el residual idiosincrático z-scoreado es la señal
   (short la alt con residual extremo). Descompone crowding en sistemático vs
   idiosincrático — más fino que el cross-section de nivel (#6-v5, que empeoró
   full-cycle). Control por retorno reciente de la alt. Data = funding BTC+15-20 alts
   (ya bajada para #6).

6. **K3-12 — FOMC Pre-Announcement Drift.** Long BTC en [anuncio−24h, anuncio], cerrar
   en el anuncio; ~90 reuniones 2015→hoy. Media del retorno de ventana vs 90 placebos
   aleatorios de 24h + permutación; **OOS por mitades** (el drift de equities se debilitó
   post-2011 → chequear decaimiento en cripto). Puro calendario, data gratis. Efecto
   documentado en equities (Lucca-Moench) → mecanismo prestado con prior razonable;
   el riesgo es N moderado y posible decaimiento.

7. **K4-08 — Cola de redención de LST.** Tamaño de la cola de retiro de Lido (ETH
   pendientes vía eventos `WithdrawalRequested`, RPC/subgraph) + su derivada, z-score.
   IC vs retorno fwd 1/3/5d del ratio stETH/ETH y de ETH, no-solapado, control por
   funding de ETH. **Reloj de protocolo literal** (delay de salida de beacon) → oferta
   futura datada; ruta de datos vía Lido evita la key de beaconcha.in que bloqueó a L3.
   Desde Shapella (abr-2023).

8. **K1-11 — Flujo de OI por tipo de margen.** d(OI_coinM)/dt − d(OI_usdtM)/dt
   normalizado (Bybit inverse vs linear + Binance coin-M vs USDT-M), z-score. **Partial
   explícito vs el nivel de #7** (que decayó en 2024+): probar que el *flujo* aporta
   sobre el *nivel* ya decaído. Split por régimen (reportar si el flujo también decae).
   Si no bate al nivel en partial-IC, se descarta. Data gratis ya accesible.

9. **K3-15 — Fed Net-Liquidity.** Liquidez neta = balance Fed (WALCL) − RRP (RRPONTSYD)
   − TGA (WTREGEN), de FRED; cambio semanal z-score vs retorno BTC fwd 5-10d. **Usar
   diferencias, no niveles** (evitar espurio por tendencia común) y controlar por DXY.
   Macro-liquidez TradFi como driver cross-asset — distinto de Gold→BTC (nivel de metal,
   refutado) y de stablecoin-flow (oferta on-chain). Frecuencia semanal → poco solape.

10. **K1-15 — Hyperliquid HHI del OI.** Concentración (HHI o top-5 share) del OI long vs
    short por activo, z-score; alto desbalance de concentración → sesgo contra el lado
    concentrado (fragilidad, NO copy-trading). IC no-solapado + placebo permutando
    asignación de OI a wallets + control por OI total. Es el único de la familia
    Hyperliquid que mide *estructura de posicionamiento* (no skill tipo L7) y tiene un
    mecanismo contrarian claro; entra pese al forward-collect de snapshots porque el
    mecanismo es fuerte y la fuente, pública y nueva.

### Suplentes (si cae alguna del top-10 al intentar bajar la data)
- **K4-20** On-chain vs CEX-perp funding spread (aporte marginal sobre #6, data ya bajada).
- **K3-19** Index Rebalance Front-Running (demanda forzada por indexación; placebo tipo-F4 central).
- **K1-04 / K4-02** Liquidaciones como flujo → reversión (CEX / lending) — mecanismo de
  flujo forzado observable; CEX necesita forward-collect del WS, lending sale de logs RPC.
- **K2-06** Governance Pass-to-Execute (timelock) — lag *contractual* (no de atención),
  el más robusto de la familia timing; data gratis (Tally/Snapshot + logs).

---

## 6. Lecturas para el TL

- **El top-10 es deliberadamente conservador con la data.** Prioricé "testeable esta
  semana con lo que ya tenemos o casi" por encima de novedad pura, porque el historial
  muestra que la *disponibilidad de datos* es lo que más candidatas mató (F1/F2/L3/GPU).
  Las ideas más originales (opciones GEX/OI-strike, Hyperliquid denso) quedaron como
  gated/forward-collect a propósito.
- **Coherencia con el insight meta del libro:** 7 de 10 son posicionamiento por
  derivados leído por un **canal/fuente nuevo** (COT, curva/dispersión/flujo de funding,
  HHI de OI), 2 son macro-liquidez/calendario (FOMC, Fed net-liquidity) y 1 es la pata
  más limpia de "oferta forzada con reloj de protocolo" (cola de redención LST + HF de
  lending). Ninguna es topología/entropía de red (familia muerta) ni oferta on-chain
  blanda (unlocks/stablecoin-supply).
- **Las dos puntas (K3-07 y K3-12)** son las de mejor relación prior/esfuerzo: CSV de la
  CFTC y calendario del FOMC, ambos gratis, mecanismo estructural, y *fuente de dato que
  el cripto-trader no mira*. Sugiero arrancar el backtest por ahí.
- **Riesgo transversal del top-10:** K4-01/K4-08/K1-15 dependen de subgraph free-tier /
  RPC / snapshots (gated-lite). Si eso traba, los suplentes K4-20/K3-19/K2-06 son
  klines/funding/logs puros y entran sin fricción de datos.
- **Qué NO re-testear salvo para cerrar expediente:** K3-11 (basis, = F3), K3-03/K3-24
  (funding×calendario, = #6), K1-20/K1-03 (forma de funding redundante con v8),
  K2-10/K2-09 (oferta/flujo on-chain, familia null).

---

*Entregado por k5-kiro. Convergencia sobre 100 fichas (K1-K4). El TL integra en
`signal-hypotheses.md` y abre el PR.*
