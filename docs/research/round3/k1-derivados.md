# Ronda 3 — K1: Derivados / posicionamiento (25 hipótesis nuevas)

> Sesión K1 · Familia: derivados y posicionamiento apalancado (funding, opciones,
> liquidaciones, OI por venue, perps en DEX).
> Escribo solo en este archivo. No commiteo ni pusheo (integra el TL).
> Línea roja respetada: solo datos públicos/observables. Nada de insider/MNPI,
> acceso no autorizado, vulnerabilidades ni MEV/sandwich contra usuarios.

## Nota de alcance y anti-repetición

El libro `signal-hypotheses.md` ya dejó territorio quemado en esta familia. Para que
cada ficha cuente como **nueva** evito reempaquetar:

- **#6 Funding Dispersion Collapse** y sus 10 variantes de §4i (gate de régimen, stop,
  aceleración de funding/rollover, tamaño por convicción, cross-sectional, canasta,
  ablación de dispersión, filtro DVOL, vol-targeting) y #6.1 two-sided (§4h).
- **F2 skew 25Δ** (Deribit, data-gated snapshot).
- **F3 base spot-perp** (premiumIndexKlines, refutado ambos signos).
- **F5 DVOL / VRP** (Deribit volatility index — débil-real, ya es feature conocida).
- **F6 divergencia OI-precio** (Bybit V5 OI, refutado).
- **#7 coin-M convexity** (Bybit inverse vs linear OI share — confirmado pero decaído).
- **L7 mirror Hyperliquid smart-money** por leaderboard/PnL (débil/underpowered).

Donde una idea roza algo previo, el campo **"Diferencia con lo ya probado"** dice
exactamente qué mecanismo o fuente cambia. Todo lo demás es terreno nuevo: estructura
de término de funding, opciones (más allá de skew/DVOL), liquidaciones como flujo,
fragmentación de OI entre venues, basis de perps en DEX, y señales de posicionamiento
que no son "nivel de funding".

> **Scores:** a priori, para ordenar qué probar. Dimensiones §1 del libro
> (Mecanismo 25% · Lag 20% · Falsabilidad 15% · Costo 15% · Novedad 15% · Retorno 10%).
> Todas las fichas traen test **no-solapado + placebo/permutación** por el espejismo
> de ventanas solapadas que mató a #6-blob, memecoin-percolation, builder, etc.

---

## A. Estructura de término y curva de funding (no "nivel" de funding)

### K1-01 — Pendiente de la curva de funding (perp vs trimestral anualizado)
- **Mecanismo:** el funding del perpetuo y la base anualizada del futuro trimestral
  son dos precios del *mismo* carry, pero los arma gente distinta (perp = retail
  apalancado minuto a minuto; trimestral = basis-traders/mesas de carry con horizonte
  de semanas). Cuando el perp paga mucho más caro que lo que implica el trimestral, el
  apalancamiento de corto está adelantado a la convicción de plazo → techo local. El
  diferencial es una medida de *impaciencia* del apalancamiento que el nivel de funding
  solo no captura.
- **Lag / persistencia:** el basis-trade que cierra el gap (vender perp / comprar
  trimestral) tiene fricción de margen cruzado y límites de inventario de las mesas →
  el gap persiste horas a 1-2 días antes de converger.
- **Señal y horizonte:** señal = funding perp anualizado − base anualizada del
  trimestral más cercano; z-score 30d. Dispara cuando z supera +2σ (perp caro →
  short) o −2σ (perp barato → sesgo long sólo como filtro). Horizonte 1-3 días.
- **Datos:** Binance `fapi` fundingRate (perp) + `premiumIndexKlines`/mark del
  futuro **trimestral** (COIN-margined y USDT quarterly, p.ej. BTCUSDT_250926), o
  Bybit V5 `/market/tickers` por contrato. Historia 2020→hoy. [gratis]
- **Test de refutación:** IC continuo no-solapado del diferencial vs retorno fwd
  1/2/3d; event-study por terciles del z; placebo barajando las fechas del diferencial
  contra los retornos (debe matar la señal); OOS por mitades.
- **Diferencia con lo ya probado:** #6 usa *dispersión del funding del perp entre
  monedas*; F3 usa *base spot-perp*. Esto es la **pendiente temporal perp↔trimestral
  del mismo activo** — ni dispersión cross-sectional ni base spot. Mecanismo y par de
  series distintos.
- **Fuentes:** Binance Futures API docs (fundingRate, premiumIndexKlines):
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api ·
  Bybit V5 market/tickers: https://bybit-exchange.github.io/docs/v5/market/tickers
- **Score §1:** Mecanismo 4 · Lag 3.5 · Falsabilidad 4.5 · Costo 4 · Novedad 4 · Retorno 3.5 → **ponderado 3.95**

### K1-02 — Dispersión de funding *entre venues* del mismo activo (fragmentación)
- **Mecanismo:** el mismo BTC-perp cotiza en Binance, Bybit, OKX, Hyperliquid, dYdX.
  En calma, el arbitraje de funding mantiene los fundings casi pegados. Cuando el
  apalancamiento se concentra en un venue (p.ej. retail asiático en un exchange)
  mientras otros no lo siguen, la **dispersión del funding entre venues** se dispara →
  posicionamiento local sobre-extendido que el arbitraje aún no niveló. Mide crowding
  por *lugar*, no por moneda.
- **Lag / persistencia:** mover colateral entre exchanges tiene fricción (transfer,
  KYC, límites) → la dispersión se cierra en horas, no instantáneo.
- **Señal y horizonte:** desviación estándar (o rango) del funding del mismo símbolo
  across ≥4 venues, z-score 30d. Alto z → short del lado del venue más caro. Horizonte
  8h-2d.
- **Datos:** fundingRate por venue — Binance `fapi`, Bybit V5, OKX `/public/funding-rate`,
  Hyperliquid `info` (fundingHistory), dYdX. Historia 2022→hoy (Hyperliquid desde
  fines 2022/2023). [gratis]
- **Test de refutación:** IC no-solapado de la dispersión vs retorno fwd; event-study
  por terciles; placebo permutando el mapeo venue↔funding; OOS; control por nivel medio
  de funding (para aislar *dispersión* de *nivel*, que ya es #6-adyacente).
- **Diferencia con lo ya probado:** #6 es dispersión del funding **entre monedas en un
  venue**. Esto es dispersión del **mismo activo entre venues** — eje ortogonal
  (geografía/plataforma del apalancamiento, no mix de activos).
- **Fuentes:** OKX V5: https://www.okx.com/docs-v5/en/ · Bybit V5:
  https://bybit-exchange.github.io/docs/v5/market/tickers · Binance Futures:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api ·
  Hyperliquid info API: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
  (dYdX: sin fuente verificable en esta revisión).
- **Score §1:** Mecanismo 4 · Lag 3.5 · Falsabilidad 4.5 · Costo 3.5 · Novedad 4.5 · Retorno 3.5 → **ponderado 3.93**

### K1-03 — Aceleración de 2º orden del funding agregado (jerk del crowding)
- **Mecanismo:** §4i-v8 probó la *primera derivada* (crowding que se da vuelta). La
  segunda derivada (aceleración de la aceleración, "jerk") detecta el momento en que el
  apalancamiento deja de *acelerar* — el punto de agotamiento de entrada de flujo nuevo
  antes de que el nivel siquiera baje. Es un early-warning del techo de posicionamiento.
- **Lag / persistencia:** el agotamiento precede al unwind por el tiempo que tardan los
  últimos entrantes en capitular → horas.
- **Señal y horizonte:** funding agregado (media ponderada por OI de top venues),
  suavizado, 2ª diferencia; dispara cuando la aceleración cruza a negativo desde un
  nivel alto. Horizonte 12h-2d, short.
- **Datos:** fundingRate + openInterest por venue (Binance/Bybit/OKX). 2020→hoy. [gratis]
- **Test de refutación:** IC no-solapado del jerk vs fwd; comparar contra v8 (1ª
  derivada) para mostrar aporte incremental (partial correlation); placebo por
  permutación; OOS.
- **Diferencia con lo ya probado:** §4i-v8 = *velocidad* del crowding (cchg). Esto es
  *aceleración/jerk* (2ª derivada) y además agregado ponderado por OI, no la señal de
  nivel de #6. Si no bate a v8 en partial-IC, se descarta.
- **Fuentes:** Binance Futures:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api ·
  Bybit V5: https://bybit-exchange.github.io/docs/v5/market/tickers · OKX V5:
  https://www.okx.com/docs-v5/en/
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4 · Costo 4 · Novedad 4 · Retorno 3 → **ponderado 3.68**

---

## B. Liquidaciones como flujo observable

### K1-04 — Impulso de liquidaciones forzadas → reversión por sobre-corrección
- **Mecanismo:** una cascada de liquidaciones es *flujo forzado* (no informado): el
  motor de margen vende/compra a mercado sin importar precio. Eso empuja el precio más
  allá del valor → reversión mecánica cuando el flujo forzado se agota. Es el único
  flujo del libro que es **observable y causalmente forzado**, no una creencia.
- **Lag / persistencia:** la reversión aparece minutos-horas después del pico de
  liquidaciones; el scheduler de minutos puede operar el tramo de horas.
- **Señal y horizonte:** volumen de liquidaciones (notional, lado) z-score vs baseline
  intradía; dispara tras un pico >Nσ → entrada contraria al lado liquidado. Horizonte
  1-6h, medir también 24h.
- **Datos:** Binance `allForceOrders`/liquidation stream (histórico vía
  data.binance.vision "liquidationSnapshot" y forward-collect), Coinglass (gated/pago),
  Bybit liquidation stream. Lo más limpio gratis: **forward-collect** del WS de
  liquidaciones + lo disponible en data.binance.vision. [gratis parcial / forward-collect]
- **Test de refutación:** event-study de retorno fwd tras picos, **controlando por
  volumen total** (clave: separar "liquidación" de "vela grande cualquiera");
  placebo = picos de volumen SIN liquidación desproporcionada (debe no revertir si el
  mecanismo es real); no-solapado; OOS.
- **Diferencia con lo ya probado:** el libro nunca testeó liquidaciones como serie
  (solo funding/OI/base). Flujo forzado observable ≠ posicionamiento implícito.
- **Fuentes:** Binance Futures WS `forceOrder`:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams ·
  data.binance.vision: https://data.binance.vision/ · Bybit V5 all-liquidation stream:
  https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- **Score §1:** Mecanismo 4 · Lag 3 · Falsabilidad 4.5 · Costo 3 · Novedad 4 · Retorno 3.5 → **ponderado 3.73**

### K1-05 — Asimetría long/short de liquidaciones como gauge de capitulación
- **Mecanismo:** no el *tamaño* sino el *desbalance*: cuando las liquidaciones son
  abrumadoramente de un lado (p.ej. 90% longs liquidados), el apalancamiento de ese
  lado quedó purgado → el combustible para seguir en esa dirección se agotó. Señal de
  suelo/techo local por *limpieza de margen*.
- **Lag / persistencia:** tras la purga, el rebote tarda en formarse mientras entra
  capital fresco → horas.
- **Señal y horizonte:** ratio (liq_long − liq_short)/(liq_long + liq_short) en ventana
  rodante 4-12h, z-score. Extremo negativo (longs purgados) → sesgo long; extremo
  positivo → sesgo short. Horizonte 4-24h.
- **Datos:** mismos feeds de liquidación que K1-04 con el lado. [gratis parcial / forward-collect]
- **Test de refutación:** IC no-solapado del ratio vs fwd; event-study por terciles;
  placebo permutando el signo del ratio; OOS; control por retorno reciente (para que no
  sea sólo mean-reversion de precio disfrazada).
- **Diferencia con lo ya probado:** magnitud vs asimetría son mecanismos distintos;
  K1-04 mide intensidad, K1-05 mide dirección de la purga. Ninguno en el libro.
- **Fuentes:** Binance Futures WS `forceOrder`:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams ·
  Bybit V5 all-liquidation: https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4 · Costo 3 · Novedad 3.5 · Retorno 3.5 → **ponderado 3.50**

### K1-06 — Clustering de liquidaciones en el libro público (mapa de niveles)
- **Mecanismo:** con mark-price, OI y tiers de margen públicos de cada exchange se
  puede estimar **dónde** se acumulan precios de liquidación (los "liquidation levels"
  que publican Coinglass/Hyblock). Cuando un cúmulo grande está cerca del precio,
  actúa como imán (los market-makers empujan hacia la liquidez de stops). Posicionarse
  hacia el cúmulo más denso dentro de rango.
- **Lag / persistencia:** el imán opera en horas; el cúmulo tarda en reconstruirse tras
  barrerse.
- **Señal y horizonte:** densidad estimada de liq-levels a ±X% del spot (reconstruida
  de OI por tier + apalancamiento típico); dispara cuando hay asimetría fuerte de
  densidad a un lado. Horizonte 4-48h.
- **Datos:** OI y mark de Binance/Bybit/OKX + reglas de margen públicas (leverage
  tiers, maintenance margin — publicadas). Alternativa directa: Hyperliquid expone
  posiciones y liquidation prices por wallet (API pública). [gratis con reconstrucción]
- **Test de refutación:** ¿el precio fwd se mueve hacia el cúmulo denso más que hacia
  el ralo? event-study condicionado a asimetría; placebo = cúmulos aleatorios de misma
  masa; no-solapado; OOS.
- **Diferencia con lo ya probado:** reconstruir el *mapa espacial* de liquidaciones es
  un mecanismo nuevo (ni funding ni OI agregado); usa reglas de margen públicas +
  posiciones públicas de Hyperliquid, no el leaderboard de PnL de L7.
- **Fuentes:** Hyperliquid info API (clearinghouseState):
  https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint ·
  reglas de leverage-tier/maintenance-margin de exchanges: sin fuente verificable única
  (varían por exchange; se derivan de sus páginas de reglas de margen).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 · Novedad 4.5 · Retorno 3.5 → **ponderado 3.48**

---

## C. Opciones más allá de skew/DVOL

### K1-07 — Pendiente de la term-structure de vol implícita (contango/backwardation)
- **Mecanismo:** la curva de IV por vencimiento normalmente está en contango (IV larga
  > IV corta). Cuando se invierte (backwardation: IV corta > larga), el mercado paga
  prima por cobertura *inmediata* → miedo de corto plazo que suele preceder
  movimiento/reversión de vol. Es información de *estructura temporal*, distinta del
  nivel (DVOL) y del skew (F2/F5).
- **Lag / persistencia:** la term-structure se ajusta en horas; la señal de régimen
  dura días.
- **Señal y horizonte:** ratio ATM-IV(7d)/ATM-IV(30d); z-score. Backwardation extrema →
  régimen de estrés (reducir short-vol / sesgo defensivo). Horizonte 1-5 días como
  feature de régimen.
- **Datos:** Deribit `public/get_instruments` + mark IV por vencimiento (ATM), o DVOL a
  distintos tenores. **Snapshot gratis; historia requiere forward-collect** (igual que
  F2/F5). [gated / forward-collect]
- **Test de refutación:** IC del slope vs vol realizada fwd y vs retorno fwd (no-solap);
  separar de DVOL-nivel por partial-corr (clave, para no re-descubrir F5); placebo;
  OOS. Si no aporta sobre DVOL-nivel, se descarta.
- **Diferencia con lo ya probado:** F5 = *nivel* de DVOL; F2 = *skew* (asimetría
  call/put). Esto es la **pendiente temporal 7d/30d** — tercera dimensión de la
  superficie, no tocada.
- **Fuentes:** Deribit API (get_volatility_index_data por tenor, get_instruments):
  https://docs.deribit.com/
- **Score §1:** Mecanismo 3.5 · Lag 3 · Falsabilidad 4 · Costo 2 · Novedad 4 · Retorno 3 → **ponderado 3.28**

### K1-08 — Gamma de dealers (GEX) → compresión/expansión de rango
- **Mecanismo:** si los dealers están net-long gamma, cubren contra-tendencia (venden
  en subas, compran en bajas) → **comprimen** el rango. Si están net-short gamma,
  cubren a favor → **amplifican** los movimientos. El signo del gamma agregado predice
  régimen de vol intradía/diaria. Estándar en equities (SpotGamma), casi inédito en
  cripto retail.
- **Lag / persistencia:** el posicionamiento de gamma cambia lento (vencimientos) →
  persiste días hasta el siguiente expiry.
- **Señal y horizonte:** GEX estimado del open interest por strike (asumiendo dealers
  short calls/long puts o signo por flujo); signo y magnitud. Gamma positiva →
  estrategias de rango; negativa → esperar expansión/breakout. Horizonte 1-5 días
  (hasta expiry semanal/mensual).
- **Datos:** Deribit open interest **por strike** (`public/get_book_summary_by_currency`,
  get_instruments) — snapshot gratis; historia por forward-collect o Amberdata/Laevitas
  (pago). [gated / forward-collect]
- **Test de refutación:** ¿vol realizada fwd es menor cuando GEX>0 vs GEX<0?
  event-study por signo; placebo permutando el signo; no-solapado; OOS. Ojo
  convención del signo del dealer (probar ambas, reportar cuál).
- **Diferencia con lo ya probado:** GEX usa la **distribución del OI por strike** y una
  hipótesis de posicionamiento de dealers — ni skew (F2) ni nivel (F5). Mecanismo nuevo
  en el libro.
- **Fuentes:** Deribit get_book_summary_by_currency: https://docs.deribit.com/ ·
  literatura GEX de equities (adaptación; sin fuente académica única verificada acá).
- **Score §1:** Mecanismo 4 · Lag 3.5 · Falsabilidad 3.5 · Costo 2 · Novedad 4.5 · Retorno 3.5 → **ponderado 3.58**

### K1-09 — Max-pain drift hacia el vencimiento
- **Mecanismo:** cerca de expiries grandes (mensuales/trimestrales de Deribit) el
  precio tiende a gravitar al strike que minimiza el pago total a los compradores de
  opciones ("max pain"), porque los dealers cubren hacia ahí. Efecto de imán los días
  previos a expiry.
- **Lag / persistencia:** opera en la ventana de 1-5 días antes del expiry.
- **Señal y horizonte:** distancia spot↔max-pain; dispara en los N días previos a un
  expiry con OI grande; dirección = hacia max-pain. Horizonte: hasta el expiry.
- **Datos:** Deribit OI por strike + calendario de expiries (público). Max-pain se
  computa del OI. Snapshot gratis; historia forward-collect. [gated / forward-collect]
- **Test de refutación:** event-study del retorno hacia max-pain sólo en ventanas
  pre-expiry; placebo = días equivalentes SIN expiry cercano (debe no haber drift);
  controlar por tamaño de OI; no-solapado (cada expiry es un evento independiente); OOS.
- **Diferencia con lo ya probado:** evento calendario-de-opciones con mecanismo de
  hedging; nada en el libro toca expiries de opciones ni max-pain.
- **Fuentes:** Deribit get_instruments (expiries) + get_book_summary_by_currency
  (OI/strike): https://docs.deribit.com/
- **Score §1:** Mecanismo 3 · Lag 4 · Falsabilidad 4 · Costo 2.5 · Novedad 4 · Retorno 3 → **ponderado 3.38**

### K1-10 — Put/Call ratio de **volumen** como sentimiento contrarian
- **Mecanismo:** el ratio put/call por volumen operado (no por OI) es un termómetro de
  pánico/euforia rápido: picos de compra de puts marcan miedo extremo → suelo
  contrarian. Distinto del skew (precio relativo) — mide *flujo* de opciones.
- **Lag / persistencia:** el sentimiento extremo revierte en 1-3 días.
- **Señal y horizonte:** volumen diario puts/calls (BTC, ETH) en Deribit; z-score 30d;
  extremos → señal contrarian. Horizonte 1-3 días.
- **Datos:** Deribit trades/volume stats por tipo (public/get_trade_volumes o agregando
  trades). Snapshot/ventana reciente gratis; historia larga por forward-collect o
  Amberdata (pago). [gated / forward-collect]
- **Test de refutación:** IC no-solapado del ratio vs fwd; event-study por terciles;
  placebo; OOS; control por retorno reciente.
- **Diferencia con lo ya probado:** flujo (volumen) de opciones por tipo, no la
  superficie de precios (F2/F5). Mecanismo de sentimiento distinto.
- **Fuentes:** Deribit get_trade_volumes / trades API: https://docs.deribit.com/
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 2.5 · Novedad 3 · Retorno 3 → **ponderado 3.08**

---

## D. OI y posicionamiento: nuevos cortes

### K1-11 — Divergencia OI-precio por **tipo de margen** (coin-M vs USDT) en flujo, no nivel
- **Mecanismo:** #7 miró el *share* coin-M de OI (nivel) y decayó. Nuevo ángulo: el
  *cambio de flujo* — cuando el OI coin-M (apostadores convexos, suelen ser holders
  alcistas que apalancan en BTC) crece mientras el USDT-M se estanca, marca euforia
  nativa-cripto; el colapso de ese flujo adelanta techos. Se mira la **velocidad
  relativa de OI por tipo de margen**, no el nivel estático.
- **Lag / persistencia:** el reposicionamiento de margen tarda (mover BTC colateral) →
  horas-días.
- **Señal y horizonte:** d(OI_coinM)/dt − d(OI_usdtM)/dt normalizado; z-score. Horizonte
  1-3 días.
- **Datos:** Bybit V5 OI (inverse vs linear) + Binance coin-M vs USDT-M OI. 2021→hoy.
  [gratis]
- **Test de refutación:** IC no-solapado del flujo relativo vs fwd; **partial vs el
  nivel de #7** (para probar que el flujo aporta sobre el nivel decaído); placebo; OOS;
  split por régimen (como #7 decayó en 2024+, reportar si el flujo también).
- **Diferencia con lo ya probado:** #7 y F6 usan *niveles* (share coin-M, OI-precio).
  Esto es la **derivada temporal del OI por tipo de margen** — flujo, no stock. Si no
  bate al nivel en partial-IC, se descarta.
- **Fuentes:** Bybit V5 open-interest: https://bybit-exchange.github.io/docs/v5/market/open-interest ·
  Binance USDⓈ-M y COIN-M futures docs: https://developers.binance.com/en/docs/catalog
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4 · Costo 4 · Novedad 3.5 · Retorno 3 → **ponderado 3.55**

### K1-12 — Ratio de cuentas long/short de top-traders (Binance) como contrarian/confirm
- **Mecanismo:** Binance publica el **global long/short account ratio** y el
  **top-trader position ratio**. La divergencia entre ambos (retail vs ballenas) es
  información de posicionamiento directa: cuando retail está muy long y top-traders
  neutro/short, el retail es contrarian. Dato dedicado, poco usado en backtest serio.
- **Lag / persistencia:** el sentimiento retail persiste días; el unwind es gradual.
- **Señal y horizonte:** spread (top-trader ratio − global account ratio), z-score;
  extremos → operar con top-traders. Horizonte 1-3 días.
- **Datos:** Binance `futures/data/globalLongShortAccountRatio`,
  `topLongShortAccountRatio`, `topLongShortPositionRatio` — **sólo últimos ~30 días en
  vivo** vía API, pero hay dumps históricos en data.binance.vision y agregadores.
  [gratis con forward-collect para historia larga]
- **Test de refutación:** IC no-solapado del spread vs fwd; event-study por terciles;
  placebo; OOS; control por funding (para no duplicar #6).
- **Diferencia con lo ya probado:** usa el dataset dedicado long/short-ratio de Binance,
  no funding ni OI; el *spread retail-vs-ballena* es el mecanismo nuevo.
- **Fuentes:** Binance Futures data endpoints (globalLongShortAccountRatio,
  topLongShortAccountRatio, topLongShortPositionRatio), catálogo USDⓈ-M:
  https://developers.binance.com/en/docs/catalog
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4.5 · Costo 3.5 · Novedad 3.5 · Retorno 3 → **ponderado 3.63**

### K1-13 — Taker buy/sell volume imbalance en perps (presión de agresor)
- **Mecanismo:** Binance publica el **taker buy/sell volume** de futuros: cuánto del
  volumen fue agresor-comprador vs agresor-vendedor. Un desbalance sostenido de
  agresión en perps (apalancado) que no se confirma en spot marca apalancamiento
  direccional frágil → reversión cuando se agota.
- **Lag / persistencia:** la agresión apalancada se agota en horas.
- **Señal y horizonte:** ratio taker-buy/taker-sell en perps, z-score 1-3 días;
  divergencia con el mismo ratio en spot. Horizonte 4-24h.
- **Datos:** Binance `futures/data/takerlongshortRatio` (agregado) +
  `takerBuySellVol`; historia 30d en vivo + data.binance.vision para aggTrades si se
  reconstruye. [gratis con forward-collect]
- **Test de refutación:** IC no-solapado; event-study; placebo; OOS; **control por
  retorno concurrente** (para que no sea momentum trivial).
- **Diferencia con lo ya probado:** presión de agresor en derivados vs la base/OI/funding
  del libro; nada mide taker-imbalance perp-vs-spot.
- **Fuentes:** Binance Futures (takerlongshortRatio, takerBuySellVol), catálogo USDⓈ-M:
  https://developers.binance.com/en/docs/catalog
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 3.5 · Novedad 3.5 · Retorno 3 → **ponderado 3.28**

### K1-14 — OI "fantasma": crecimiento de OI sin volumen (acumulación silenciosa)
- **Mecanismo:** OI que sube con **poco volumen** implica posiciones nuevas que se
  arman sin urgencia (limit orders, acumulación paciente) — típicamente manos fuertes;
  OI que sube con mucho volumen es FOMO. La *calidad* del crecimiento de OI (OI-Δ por
  unidad de volumen) distingue acumulación informada de euforia.
- **Lag / persistencia:** la acumulación paciente precede al movimiento por días.
- **Señal y horizonte:** ΔOI / volumen (ventana diaria), z-score; alto ratio con precio
  plano → sesgo a favor del lado neto. Horizonte 1-5 días.
- **Datos:** OI + volumen por venue (Binance/Bybit/OKX), diario/horario. 2020→hoy.
  [gratis]
- **Test de refutación:** IC no-solapado del ratio vs fwd; placebo; OOS; separar de
  F6 (OI-precio nivel) por construcción (acá es OI/volumen, no OI/precio).
- **Diferencia con lo ya probado:** F6 relaciona OI con *precio*; esto relaciona OI con
  *volumen* (eficiencia de formación de OI). Mecanismo distinto.
- **Fuentes:** Binance USDⓈ-M: https://developers.binance.com/en/docs/catalog ·
  Bybit V5 open-interest: https://bybit-exchange.github.io/docs/v5/market/open-interest ·
  OKX V5: https://www.okx.com/docs-v5/en/
- **Score §1:** Mecanismo 3 · Lag 3.5 · Falsabilidad 4 · Costo 4 · Novedad 3.5 · Retorno 3 → **ponderado 3.45**

---

## E. DEX perps / on-chain derivados (fuentes nuevas)

### K1-15 — Hyperliquid: concentración del OI por wallet (crowding de ballenas, no PnL)
- **Mecanismo:** Hyperliquid expone **posiciones abiertas por wallet** on-chain. En vez
  de rankear por PnL (L7), medir la **concentración** del OI: cuando pocas wallets
  concentran el OI de un lado (HHI alto), ese lado está crowded y es vulnerable a
  liquidación en cascada → señal contrarian de fragilidad. Mide estructura del
  posicionamiento, no "copiar al ganador".
- **Lag / persistencia:** la concentración se deshace vía liquidaciones/cierres →
  horas-días.
- **Señal y horizonte:** HHI (o top-5 share) del OI long vs short por activo; z-score;
  alto desbalance de concentración → sesgo contra el lado concentrado. Horizonte 4-48h.
- **Datos:** Hyperliquid `info` API (clearinghouseState por wallet, metaAndAssetCtxs
  para OI agregado) — público, 2023→hoy. Requiere agregar muchas wallets
  (forward-collect ligero o snapshots). [gratis / forward-collect]
- **Test de refutación:** IC no-solapado de la concentración vs fwd; placebo permutando
  asignación de OI a wallets; OOS; control por OI total.
- **Diferencia con lo ya probado:** L7 rankea wallets por PnL para *copiarlas* (débil).
  Esto mide **concentración/HHI del OI** como fragilidad — mecanismo contrarian, no de
  imitación; y es flujo de posicionamiento, no skill.
- **Fuentes:** Hyperliquid info API (info endpoint, clearinghouseState, metaAndAssetCtxs):
  https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- **Score §1:** Mecanismo 4 · Lag 3.5 · Falsabilidad 4 · Costo 2.5 · Novedad 4.5 · Retorno 3.5 → **ponderado 3.68**

### K1-16 — Spread de funding DEX (GMX/Hyperliquid) vs CEX (lag estructural de pools)
- **Mecanismo:** el funding/borrow-rate de perps DEX basados en pool (GMX, Hyperliquid)
  se ajusta por reglas del pool/utilización, no por un libro de órdenes continuo →
  reacciona con lag vs el funding CEX. El spread DEX−CEX es un arbitraje de
  posicionamiento con fricción (gas, LP caps) → predice convergencia.
- **Lag / persistencia:** el arbitraje cross-venue DEX↔CEX tiene fricción real (gas,
  bridging, utilización del pool) → horas.
- **Señal y horizonte:** funding DEX − funding CEX del mismo activo, z-score; extremo →
  operar hacia la convergencia. Horizonte 8h-2d.
- **Datos:** Hyperliquid funding (info API), GMX borrow/funding (subgraph / contratos
  Arbitrum), vs Binance/Bybit. 2022/2023→hoy. [gratis]
- **Test de refutación:** ¿el spread predice el retorno del activo o sólo la
  convergencia del propio spread? medir ambos; no-solapado; placebo; OOS.
- **Diferencia con lo ya probado:** F3 es base spot-perp en un venue; esto es
  **funding DEX vs CEX** (mecanismo de pool con lag estructural). Fuente y mecanismo
  nuevos.
- **Fuentes:** Hyperliquid info API:
  https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint ·
  GMX docs: https://docs.gmx.io/ · Binance/Bybit funding:
  https://developers.binance.com/en/docs/catalog ·
  https://bybit-exchange.github.io/docs/v5/market/tickers
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.40**

### K1-17 — Skew de utilización de GLP/pools de market-maker (desbalance de trader net)
- **Mecanismo:** en DEX pool-based (GMX GLP, gTrade), el pool es la contraparte de los
  traders. Cuando los traders están netos muy long, el pool está net-short y ajusta
  incentivos; ese **desbalance net-trader** es posicionamiento retail agregado,
  observable on-chain, y cuando es extremo suele preceder reversión (el pool "gana" a
  los traders en extremos).
- **Lag / persistencia:** el desbalance se corrige lento (los traders no cierran de
  golpe) → días.
- **Señal y horizonte:** (OI_long − OI_short)/(OI_long + OI_short) del pool DEX;
  z-score; extremo → contrarian. Horizonte 1-4 días.
- **Datos:** GMX stats (subgraph Arbitrum/Avalanche), gTrade, Hyperliquid. [gratis]
- **Test de refutación:** IC no-solapado; placebo; OOS; control por funding CEX (no
  duplicar #6).
- **Diferencia con lo ya probado:** posicionamiento net-trader en **pools DEX** (fuente
  on-chain nueva); nada en el libro mira GLP/pool imbalance.
- **Fuentes:** GMX docs: https://docs.gmx.io/ · Hyperliquid info API:
  https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint ·
  (gTrade/Gains Network: sin fuente verificable en esta revisión).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.40**

---

## F. Basis, calendario de funding y microtiming estructural (horas/días)

### K1-18 — Mean-reversion del snap de funding en el settlement de 8h
- **Mecanismo:** el funding se liquida en marcas fijas (00/08/16 UTC en Binance). Cerca
  del settlement, traders maniobran para evitar/cobrar funding → distorsión temporal de
  precio alrededor de la marca que revierte después. Es microtiming **estructural y
  recurrente** (todos los días), con horizonte de horas → operable por el scheduler.
- **Lag / persistencia:** la distorsión pre-settlement revierte en 1-4h post-marca.
- **Señal y horizonte:** retorno en la ventana [-1h, settlement] condicionado al signo
  del funding; apostar a la reversión en [+0h, +4h]. Horizonte intra-día (horas).
- **Datos:** klines 1h/15m + fundingRate + horario de settlement (Binance). 2020→hoy.
  [gratis]
- **Test de refutación:** event-study por marca de settlement vs **control de horas
  no-settlement** (placebo: misma lógica en 04/12/20 UTC, donde no hay marca); no-solap
  (cada settlement independiente); OOS; neto de fees.
- **Diferencia con lo ya probado:** el libro refutó el "00:00 UTC impulse" (reloj
  Schelling genérico) y la base F3. Esto es específico del **mecanismo de settlement de
  funding**, con control por horas sin-marca — mecanismo y placebo distintos del
  midnight-impulse.
- **Fuentes:** Binance USDⓈ-M futures docs (funding settlement, klines):
  https://developers.binance.com/en/docs/catalog
- **Score §1:** Mecanismo 3.5 · Lag 3 · Falsabilidad 4.5 · Costo 4 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.50**

### K1-19 — Divergencia funding entre quote-assets (USDT-M vs USDC-M)
- **Mecanismo:** el mismo activo tiene perps en USDT y en USDC. El funding de cada uno
  refleja el apalancamiento denominado en esa stablecoin; divergencias marcan estrés o
  rotación entre bases de stablecoin (p.ej. preferencia por USDC en risk-off). Señal de
  posicionamiento + stress de colateral.
- **Lag / persistencia:** el arbitraje entre bases tiene fricción (swap de stable) →
  horas.
- **Señal y horizonte:** funding(USDT-perp) − funding(USDC-perp) mismo activo; z-score;
  extremo → señal de estrés/rotación. Horizonte 8h-2d.
- **Datos:** Binance/Bybit/OKX perps USDT vs USDC del mismo activo (p.ej. BTCUSDT vs
  BTCUSDC donde exista). [gratis]
- **Test de refutación:** IC no-solapado; placebo; OOS; separar de #2 peg-sync (que era
  spot stablecoin, no funding de perps).
- **Diferencia con lo ya probado:** #2 miró el *peg spot* de stablecoins (refutado);
  esto mira el **funding de perps por quote-asset** — mecanismo de posicionamiento, no
  de peg. Fuente/serie distinta.
- **Fuentes:** Binance USDⓈ-M: https://developers.binance.com/en/docs/catalog ·
  Bybit V5: https://bybit-exchange.github.io/docs/v5/market/tickers · OKX V5:
  https://www.okx.com/docs-v5/en/
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 3.5 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.18**

### K1-20 — Persistencia del signo de funding (rachas) como momentum de posicionamiento
- **Mecanismo:** una racha larga de funding positivo = apalancamiento long cada vez más
  arraigado. La *longitud de la racha* (no el nivel) mide convicción acumulada; rachas
  extremas marcan agotamiento. Distinto de nivel (#6) y de aceleración (v8/K1-03).
- **Lag / persistencia:** las rachas largas se rompen en días.
- **Señal y horizonte:** nº de settlements consecutivos con funding del mismo signo;
  percentil histórico; racha extrema → sesgo contrarian. Horizonte 1-4 días.
- **Datos:** fundingRate histórico (Binance/Bybit). 2020→hoy. [gratis]
- **Test de refutación:** IC no-solapado de la longitud de racha vs fwd; **partial vs
  nivel de funding** (para aislar "duración" de "nivel"); placebo; OOS.
- **Diferencia con lo ya probado:** #6 = nivel+dispersión; v8 = aceleración. Racha =
  *persistencia temporal del signo*, eje nuevo. Si no bate al nivel en partial, descarte.
- **Fuentes:** Binance USDⓈ-M funding history: https://developers.binance.com/en/docs/catalog ·
  Bybit V5: https://bybit-exchange.github.io/docs/v5/market/tickers
- **Score §1:** Mecanismo 3 · Lag 3.5 · Falsabilidad 4 · Costo 4 · Novedad 3 · Retorno 2.5 → **ponderado 3.30**

---

## G. Cross-sectional y relativos (no el cross-section de #6-v5)

### K1-21 — Beta de funding: sensibilidad del funding de una alt al funding de BTC
- **Mecanismo:** regresar el funding de cada alt contra el funding de BTC da una "beta
  de apalancamiento". Alts con beta alta son donde el apalancamiento especulativo se
  amplifica. Cuando la beta de una alt **salta** (su funding se desacopla al alza vs
  BTC), hay crowding idiosincrático → vulnerable. Usa la *estructura de covarianza del
  funding*, no su nivel ni dispersión simple.
- **Lag / persistencia:** el crowding idiosincrático se purga en días.
- **Señal y horizonte:** residual del funding de la alt tras regresión rolling contra
  BTC-funding; z-score; residual extremo → short la alt. Horizonte 1-3 días.
- **Datos:** fundingRate de BTC + 15-20 alts líquidas (Binance/Bybit). 2020→hoy. [gratis]
- **Test de refutación:** IC no-solapado del residual vs fwd de la alt; placebo; OOS;
  control por retorno reciente de la alt.
- **Diferencia con lo ya probado:** #6-v5 (cross-section) shortea la alt más crowded por
  *nivel* de funding. Esto usa el **residual idiosincrático tras una beta de funding
  vs BTC** — descompone en sistemático vs idiosincrático, no el nivel crudo.
- **Fuentes:** Binance USDⓈ-M funding por símbolo: https://developers.binance.com/en/docs/catalog ·
  Bybit V5: https://bybit-exchange.github.io/docs/v5/market/tickers
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4 · Costo 3.5 · Novedad 4 · Retorno 3 → **ponderado 3.60**

### K1-22 — Lead-lag de OI: ¿el OI de BTC lidera el OI de alts?
- **Mecanismo:** el apalancamiento suele entrar primero a BTC/ETH y luego rota a alts
  ("risk-on ladder"). Si el crecimiento de OI de BTC **lidera** el de alts por horas,
  hay una ventana para anticipar el leg de alts. Es lead-lag de *posicionamiento*, no de
  precio.
- **Lag / persistencia:** la rotación de apalancamiento tarda horas-1 día.
- **Señal y horizonte:** correlación cruzada rezagada ΔOI_BTC → ΔOI_alt; cuando BTC-OI
  acelera, sesgo long alts al día siguiente. Horizonte 1-2 días.
- **Datos:** OI de BTC + alts (Binance/Bybit/OKX). 2020→hoy. [gratis]
- **Test de refutación:** Granger/lead-lag con muestras no-solapadas; placebo
  (permutar la serie de BTC-OI); OOS; control por retorno de BTC (que no sea sólo
  beta de precio).
- **Diferencia con lo ya probado:** F6 es OI-precio de un activo; esto es **lead-lag de
  OI entre activos** (rotación de apalancamiento). Mecanismo relacional nuevo.
- **Fuentes:** Binance USDⓈ-M: https://developers.binance.com/en/docs/catalog ·
  Bybit V5 open-interest: https://bybit-exchange.github.io/docs/v5/market/open-interest ·
  OKX V5: https://www.okx.com/docs-v5/en/
- **Score §1:** Mecanismo 3 · Lag 3.5 · Falsabilidad 3.5 · Costo 3.5 · Novedad 3.5 · Retorno 3 → **ponderado 3.28**

### K1-23 — Dispersión de IV entre activos (concentración de miedo)
- **Mecanismo:** cuando la vol implícita se dispara en un solo activo vs la canasta, es
  miedo idiosincrático; cuando la IV de todos converge al alza, es estrés sistémico. La
  **dispersión cross-sectional de IV** (sólo BTC/ETH y pocas alts con opciones líquidas)
  distingue régimen local de sistémico → condiciona exposición.
- **Lag / persistencia:** el régimen de vol persiste días.
- **Señal y horizonte:** std cross-sectional de ATM-IV (BTC, ETH, SOL si hay); z-score;
  baja dispersión + IV alta = estrés sistémico (defensivo). Horizonte 1-5 días, feature
  de régimen.
- **Datos:** Deribit ATM-IV por activo (BTC/ETH/SOL donde haya opciones). Snapshot
  gratis; historia forward-collect. [gated / forward-collect]
- **Test de refutación:** IC vs vol/retorno fwd de la canasta; no-solap; placebo; OOS;
  separar de DVOL-nivel (F5) por partial.
- **Diferencia con lo ya probado:** F5 = nivel DVOL de un activo. Esto es **dispersión
  de IV entre activos** — mecanismo de concentración de miedo, no probado (y OJO: el
  libro dijo que la familia "entropía/topología" murió, pero esto es IV de
  *posicionamiento de opciones*, no topología de red on-chain; aun así, score de novedad
  prudente y debe pasar partial vs nivel).
- **Fuentes:** Deribit volatility index (get_volatility_index_data) por activo:
  https://docs.deribit.com/
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3.5 · Costo 2 · Novedad 3 · Retorno 2.5 → **ponderado 2.85**

---

## H. Convexidad y colateral (nicho estructural)

### K1-24 — Degradación de colateral: funding vs tasa de borrow del colateral
- **Mecanismo:** quien apalanca long a veces usa colateral que a su vez rinde/cuesta
  (p.ej. perps colateralizados con stETH, o borrow en lending). Cuando el costo de
  mantener la posición (funding + borrow del colateral) supera el carry esperado, el
  apalancamiento se vuelve insostenible → desapalancamiento forzado. El **spread
  carry-vs-costo-de-colateral** anticipa unwinds.
- **Lag / persistencia:** el ajuste de posiciones apalancadas con colateral que rinde
  tarda días (no se cierran al instante por costos).
- **Señal y horizonte:** funding perp − (yield neto del colateral habitual, p.ej. stETH
  staking yield − borrow rate Aave); z-score; spread muy negativo para el long →
  presión de unwind → sesgo short. Horizonte 1-5 días.
- **Datos:** fundingRate (Binance) + stETH APR (Lido) + borrow rates Aave (subgraph /
  API DefiLlama yields). 2021→hoy. [gratis]
- **Test de refutación:** IC no-solapado del spread vs fwd; placebo; OOS; control por
  funding solo (para probar que el colateral aporta).
- **Diferencia con lo ya probado:** combina funding con **costo de colateral on-chain**
  — mecanismo de sostenibilidad del carry, no el nivel de funding (#6) ni la base (F3).
- **Fuentes:** Lido docs (stETH APR): https://docs.lido.fi/contracts/lido · Aave docs:
  https://aave.com/docs · DefiLlama yields API: https://api-docs.defillama.com/ ·
  Binance funding: https://developers.binance.com/en/docs/catalog
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.43**

### K1-25 — Convexidad de liquidación: clustering de leverage efectivo en Hyperliquid
- **Mecanismo:** con las posiciones públicas de Hyperliquid se puede estimar el
  **apalancamiento efectivo agregado** (suma de notional / suma de margen) del mercado.
  Cuando el leverage efectivo agregado está en percentil extremo, un movimiento chico
  dispara liquidaciones desproporcionadas (convexidad) → régimen frágil, reducir
  exposición / esperar expansión de vol.
- **Lag / persistencia:** el leverage agregado baja sólo tras un shake-out → el estado
  frágil persiste hasta que se purga (días).
- **Señal y horizonte:** leverage efectivo agregado (notional/margin) por activo;
  percentil; extremo → feature de fragilidad / sesgo contrarian al lado apalancado.
  Horizonte 1-4 días.
- **Datos:** Hyperliquid info API (clearinghouseState por wallet → agregado; o
  metaAndAssetCtxs). 2023→hoy. [gratis / forward-collect]
- **Test de refutación:** ¿vol realizada fwd es mayor cuando el leverage agregado está
  alto? event-study por percentil; placebo; no-solap; OOS; control por OI (que no sea
  sólo "hay más OI").
- **Diferencia con lo ya probado:** L7 copia PnL; K1-15 mide concentración por wallet.
  Esto mide **leverage efectivo agregado** (convexidad de liquidación sistémica) — gauge
  de fragilidad, mecanismo distinto de los dos anteriores y del coin-M de #7.
- **Fuentes:** Hyperliquid info API (clearinghouseState, metaAndAssetCtxs):
  https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- **Score §1:** Mecanismo 4 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 · Novedad 4.5 · Retorno 3.5 → **ponderado 3.63**

---

## Tabla resumen

| id | nombre | score | datos | fit bot |
|---|---|---|---|---|
| K1-01 | Pendiente curva de funding (perp vs trimestral) | 3.95 | gratis | ✅ alto |
| K1-02 | Dispersión de funding entre venues | 3.93 | gratis | ✅ alto |
| K1-03 | Jerk (2ª derivada) del funding agregado | 3.68 | gratis | ✅ alto |
| K1-04 | Impulso de liquidaciones → reversión | 3.73 | gratis parcial / fwd-collect | ⚠️ medio (horas) |
| K1-05 | Asimetría long/short de liquidaciones | 3.50 | gratis parcial / fwd-collect | ✅ alto |
| K1-06 | Clustering espacial de liq-levels | 3.48 | gratis c/reconstrucción | ✅ alto |
| K1-07 | Term-structure IV (7d/30d) | 3.28 | gated / fwd-collect | ✅ alto |
| K1-08 | Gamma de dealers (GEX) | 3.58 | gated / fwd-collect | ✅ alto |
| K1-09 | Max-pain drift pre-expiry | 3.38 | gated / fwd-collect | ✅ alto |
| K1-10 | Put/Call ratio de volumen | 3.08 | gated / fwd-collect | ✅ alto |
| K1-11 | Flujo OI por tipo de margen (coin-M vs USDT) | 3.55 | gratis | ✅ alto |
| K1-12 | Spread long/short retail vs top-trader | 3.63 | gratis / fwd-collect | ✅ alto |
| K1-13 | Taker buy/sell imbalance perp vs spot | 3.28 | gratis / fwd-collect | ⚠️ medio (horas) |
| K1-14 | OI fantasma (ΔOI/volumen) | 3.45 | gratis | ✅ alto |
| K1-15 | Hyperliquid: concentración (HHI) del OI | 3.68 | gratis / fwd-collect | ✅ alto |
| K1-16 | Spread funding DEX vs CEX | 3.40 | gratis | ✅ alto |
| K1-17 | Skew de net-trader en pools GLP/DEX | 3.40 | gratis | ✅ alto |
| K1-18 | Mean-reversion del settlement de funding 8h | 3.50 | gratis | ⚠️ medio (horas) |
| K1-19 | Divergencia funding USDT-M vs USDC-M | 3.18 | gratis | ✅ alto |
| K1-20 | Persistencia (racha) del signo de funding | 3.30 | gratis | ✅ alto |
| K1-21 | Residual idiosincrático de beta-funding vs BTC | 3.60 | gratis | ✅ alto |
| K1-22 | Lead-lag de OI BTC → alts | 3.28 | gratis | ✅ alto |
| K1-23 | Dispersión de IV entre activos | 2.85 | gated / fwd-collect | ✅ alto |
| K1-24 | Funding vs costo de colateral (stETH/Aave) | 3.43 | gratis | ✅ alto |
| K1-25 | Hyperliquid: leverage efectivo agregado | 3.63 | gratis / fwd-collect | ✅ alto |

**Conteo: 25 fichas.**

### Lectura rápida para el revisor (K5)
- **Mejor prior + testeable-ya con data gratis que ya bajamos:** K1-01 (curva de
  funding), K1-02 (dispersión entre venues), K1-11 (flujo OI por margen), K1-14 (OI
  fantasma), K1-21 (residual beta-funding), K1-12 (spread retail vs top-trader). Todas
  solo fundingRate/OI de Binance/Bybit/OKX.
- **Alto novel pero data por forward-collect o reconstrucción:** K1-08 (GEX), K1-15 y
  K1-25 (Hyperliquid), K1-06 (liq-levels).
- **Advertencia honesta:** varias de opciones (K1-07/08/09/10/23) comparten el muro de
  F2/F5 — Deribit solo da snapshot, la historia hay que *forward-collectarla* o pagar
  Amberdata/Laevitas. Las marco gated para que el revisor no las priorice como
  "testeable esta semana".
- **Riesgo de solapamiento con #6:** K1-03, K1-11, K1-20, K1-21 tocan funding/OI; cada
  una trae en su test un **partial-IC contra el nivel/variante ya probada** para
  descartarse sola si no aporta señal incremental.
