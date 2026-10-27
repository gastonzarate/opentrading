# Ronda 3 — K3 · Calendario y cross-asset

> Autor: `k3-kiro` · Familia: vencimientos, CME, macro, ETF/índices, horario TradFi
> Archivo de salida de la tarea K3 del BRIEF.md · 25 fichas nuevas.

Línea roja respetada: **solo datos públicos/observables**. Ninguna de estas ideas
usa insider/MNPI, acceso no autorizado, explotación de vulnerabilidades ni MEV
contra usuarios. "Hack" = lectura astuta de información pública con lag estructural.

Sesgo de diseño siguiendo las lecciones previas:
- Horizontes de **horas/días** (el bot corre en scheduler de minutos; nada sub-minuto salvo "research-only").
- Cada ficha trae **ruta de datos concreta** (endpoint/dataset/rango) y etiqueta [gratis | gated | forward-collect].
- Test de refutación con **muestra no-solapada + placebo/permutación** desde la ficha.
- Cada idea dice en qué **cambia de mecanismo o fuente** respecto de lo ya probado
  (CME-gap reversal ❌, Gold→BTC ❌, 00:00 UTC ❌, ETF-flow F1 ⛔, RWA 🟡, unlocks F4 ❌).

Bloques: **A. Vencimientos de opciones/futuros** (K3-01…06) · **B. CME y COT**
(K3-07…11) · **C. Calendario macro** (K3-12…16) · **D. ETF e índices**
(K3-17…21) · **E. Horario TradFi / fronteras de sesión** (K3-22…25).

---

## A. Vencimientos de opciones / futuros

### K3-01 — Deribit Max-Pain Pin Drift (deriva hacia dolor máximo pre-expiry)
- **Mecanismo:** los dealers que vendieron opciones quedan short-gamma cerca del
  vencimiento mensual de Deribit (último viernes, 08:00 UTC). Para cubrirse
  compran cuando el spot cae y venden cuando sube, empujando el precio hacia el
  strike de **max-pain** (donde vence sin valor la mayor cantidad de opciones).
  No es manipulación: es el agregado mecánico de la cobertura delta.
- **Lag / persistencia:** el "pin" se forma en las 24–48 h previas al expiry y se
  deshace después; el open interest por strike es público pero casi nadie calcula
  el max-pain forward en cripto retail → el reposicionamiento no se arbitra entero.
- **Señal y horizonte:** cada día, calcular max-pain de la serie mensual próxima.
  Si |spot − maxpain| > umbral y faltan ≤2 días, apostar a convergencia hacia
  max-pain. Horizonte: hasta el expiry (horas–2 días). Dirección = signo(maxpain−spot).
- **Datos:** Deribit API pública `public/get_book_summary_by_currency` + OI por
  instrumento (`public/get_instruments`), BTC/ETH, 2019→hoy. Para histórico fino:
  snapshots diarios de OI por strike. [gratis el snapshot actual; **forward-collect**
  para serie OI-por-strike histórica, o Amberdata/Laevitas gated para retro].
- **Test de refutación:** event-study de retorno spot forward condicionado a
  (distancia a max-pain × días a expiry), bucketeado; IC no-solapado por ciclo
  mensual (1 obs/mes → ~80 meses desde 2019); **placebo** con días aleatorios lejos
  del expiry; permutación de la etiqueta de ciclo.
- **Diferencia con lo ya probado:** ninguna previa usa max-pain/OI-por-strike. F2
  (skew 25Δ) y F5 (DVOL) usan Deribit pero miden *sentimiento de vol*, no la
  *geometría de posicionamiento por strike* ni el efecto pin. Mecanismo y métrica distintos.
- **Fuentes:** Deribit API docs https://docs.deribit.com/ (`get_book_summary_by_currency`,
  `get_instruments`). Literatura "max pain / option pinning": Ni, Pearson & Poteshman (2005),
  "Stock price clustering on option expiration dates", J. Financial Economics.
- **Score §1:** Mecanismo 3.5 · Lag 3.0 · Falsabilidad 4.0 · Costo 2.5 (OI histórico forward-collect) · Novedad 4.0 · Retorno 3.0 → **ponderado 3.3**

### K3-02 — Quarterly-Expiry Gamma Flip (cambio de régimen gamma dealer post-vencimiento trimestral)
- **Mecanismo:** los vencimientos trimestrales (marzo/junio/sep/dic, últimos
  viernes) son los de mayor OI. Antes del expiry los dealers suelen estar
  net-short-gamma (suprimen vol, mean-reversion); al vencer, ese gamma desaparece
  y el mercado pasa a un régimen más tendencial/volátil. El "gamma flip level" es
  el spot donde el gamma agregado del dealer cambia de signo.
- **Lag / persistencia:** el régimen cambia en una fecha conocida y fija; la
  transición de supresión→expansión de vol persiste días porque las nuevas
  posiciones se reconstruyen lentamente. Calendario público, reacción lenta.
- **Señal y horizonte:** medir vol realizada forward (y |retorno|) en la ventana
  T+0…T+5 tras el trimestral vs una ventana control equidistante sin expiry.
  Señal de régimen: subir exposición a estrategias de momentum / bajar las de
  reversión en la semana post-trimestral. Horizonte 1–5 días.
- **Datos:** calendario de expiries trimestrales Deribit/CME (fijo, derivable) +
  klines 1h BTC/ETH 2019→hoy (ya los tenemos). OI agregado por expiry: Deribit
  público. [gratis].
- **Test de refutación:** comparar distribución de vol realizada T+0..5 post-trimestral
  vs 100 ventanas placebo aleatorias; test de medias + permutación; IC no-solapado
  (1 obs/trimestre, ~28 trimestres desde 2019 → underpowered, declararlo); OOS por mitades.
- **Diferencia con lo ya probado:** el "Weekend/CME-gap reversal" refutado miraba
  gaps de precio del fin de semana. Esto mira el **cambio de régimen de vol por
  desaparición de gamma dealer** en fecha de expiry trimestral — mecanismo (gamma)
  y métrica (vol realizada, no gap de precio) totalmente distintos.
- **Fuentes:** Deribit API docs https://docs.deribit.com/ (OI por instrumento y calendario de
  expiries derivable de `get_instruments`). Concepto gamma-exposure (GEX): nota pública de
  SqueezeMetrics (sin DOI; referencia conceptual, no cuantía).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.0 (pocos trimestres) · Costo 4.0 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.3**

### K3-03 — Perp Funding Reset Clustering alrededor de expiry de opciones
- **Mecanismo:** cerca de un gran expiry de opciones, los traders rotan cobertura
  de opciones a perps (más baratas de mantener), lo que concentra presión en el
  funding del perp justo en las horas previas al vencimiento. Ese pico de funding
  localizado en el tiempo es un proxy de "crowding forzado por calendario" distinto
  del crowding orgánico de #6.
- **Lag / persistencia:** el calendario es conocido pero el flujo de rotación
  opción→perp se materializa en las 12–24 h previas; se deshace tras el expiry.
- **Señal y horizonte:** z-score del funding en la ventana [-24h, 0h] respecto del
  expiry vs baseline; si el funding se dispara anómalamente alto justo antes del
  expiry, short post-expiry (crowding se desarma). Horizonte 6–24 h.
- **Datos:** Binance `fundingRate` histórico (2019→hoy, gratis, ya usado en #6) +
  calendario de expiries Deribit. [gratis].
- **Test de refutación:** condicionar el edge de funding SOLO a la proximidad de
  expiry vs funding en días sin expiry (control); si el funding predice igual en
  ambos, el calendario no aporta → refutado. Permutación de fechas de expiry; no-solapado.
- **Diferencia con lo ya probado:** #6 (funding dispersion) usa funding como señal
  continua agnóstica del calendario. Esto **condiciona el funding al calendario de
  expiry** — nueva variable (interacción funding×expiry), no el funding crudo. Si no
  aporta sobre #6, se descarta explícitamente.
- **Fuentes:** Binance USDⓈ-M Futures API, endpoint fundingRate https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
  ; Deribit API docs https://docs.deribit.com/ (calendario de expiries vía `get_instruments`).
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 4.0 · Costo 4.5 (data ya bajada) · Novedad 3.0 · Retorno 2.5 → **ponderado 3.2**

### K3-04 — CME Bitcoin Futures Roll Pressure (presión de rollover trimestral)
- **Mecanismo:** los futuros de CME (BTC, MBT micro) tienen vencimiento mensual;
  los fondos institucionales que mantienen exposición larga deben **rolar** del
  contrato próximo al siguiente en la semana previa al vencimiento (último viernes).
  Esa venta del front / compra del next genera presión de base y a veces spot
  cuando los arbitrajistas cash-and-carry ajustan. Flujo mecánico con fecha fija.
- **Lag / persistencia:** la ventana de roll es conocida (≈5 días hábiles antes del
  último viernes) pero el reacomodo del basis spot-futuro se propaga en horas–días.
- **Señal y horizonte:** medir el spread CME front−next y su cambio en la semana de
  roll; correlacionar con retorno spot forward 1–3 días. Dirección: si el roll
  comprime la base anómalamente, carry-unwind. Horizonte 1–3 días.
- **Datos:** CME settlement prices de BTC/MBT futures (cmegroup.com settlements,
  gratis con delay; Barchart/investing para histórico). 2017→hoy. [gratis con delay | gated histórico fino].
- **Test de refutación:** event-study del basis y retorno spot en la ventana de roll
  vs semanas control; permutación; no-solapado (1 obs/mes); placebo con semanas
  aleatorias.
- **Diferencia con lo ya probado:** el CME-gap reversal refutado miraba el *gap de
  apertura del lunes*. Esto mira el **basis CME front-next durante el roll trimestral**
  — fuente de datos (settlements CME, no klines de spot del weekend) y mecanismo
  (roll institucional, no gap) distintos. También distinto de F3 (basis spot-perp de
  Binance): aquí la base es CME-institucional con calendario fijo.
- **Fuentes:** CME Group Bitcoin futures settlements https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin.settlements.html
  ; concepto de roll yield / carry en futuros (texto estándar, sin URL única).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 (CME histórico) · Novedad 4.0 · Retorno 3.0 → **ponderado 3.4**

### K3-05 — Options Expiry Vol-Crush Carry (venta de vol antes de expiry conocido)
- **Mecanismo:** la vol implícita de opciones cortas tiende a inflarse antes de un
  vencimiento grande y a colapsar justo después (vol-crush), porque la demanda de
  cobertura se concentra y luego desaparece. Vender vol (o proxy direccional de
  mean-reversion de |retorno|) en la ventana es un carry de calendario.
- **Lag / persistencia:** el patrón es estacional-de-calendario; persiste porque el
  retail no vende vol sistemáticamente antes de expiry en cripto.
- **Señal y horizonte:** comparar IV de la serie corta en T-2d vs vol realizada
  posterior T+0..T+2; si IV >> RV esperada, el VRP de calendario es positivo.
  Proxy sin opciones: |retorno| realizado post-expiry < pre-expiry. Horizonte 1–2 días.
- **Datos:** Deribit DVOL / `get_volatility_index_data` (gratis, ya usado en F5) +
  klines para RV. [gratis].
- **Test de refutación:** VRP (IV−RV) en ventanas de expiry vs ventanas control;
  permutación de fechas; no-solapado por ciclo; OOS por mitades. Controlar por nivel
  de DVOL (que F5 ya mostró débil-real) para aislar el componente *de calendario*.
- **Diferencia con lo ya probado:** F5 (DVOL) usa el *nivel* de vol implícita como
  feature de régimen agnóstico del calendario. Esto aísla el **componente de VRP
  atribuible al calendario de expiry** (interacción DVOL×expiry) — pregunta distinta.
- **Fuentes:** Deribit DVOL / `get_volatility_index_data` — Deribit API docs https://docs.deribit.com/
  ; VRP (variance risk premium): Bollerslev, Tauchen & Zhou (2009), "Expected Stock Returns and
  Variance Risk Premia", Review of Financial Studies.
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.0 · Retorno 2.5 → **ponderado 3.1**

### K3-06 — Deribit OI Strike Migration (migración de OI hacia strikes altos = señal alcista anticipada)
- **Mecanismo:** cuando el dinero "inteligente" se posiciona para un movimiento,
  el open interest nuevo se concentra en strikes OTM de un lado (calls altos para
  alcista). La distribución de OI por strike es pública y se mueve *antes* que el
  spot porque posicionarse en opciones es más barato que en spot/perp.
- **Lag / persistencia:** la acumulación de OI en strikes direccionales precede al
  movimiento del subyacente por horas–días; el retail no mira la *distribución* de OI.
- **Señal y horizonte:** medir el centro de masa (o skew) de la distribución de OI
  por strike día a día; un desplazamiento del centro de masa hacia arriba (calls)
  anticipa retorno positivo. Horizonte 1–3 días, long/short según dirección del shift.
- **Datos:** Deribit `get_instruments` + OI por instrumento, snapshot diario.
  [**forward-collect** para serie histórica de OI-por-strike; snapshot actual gratis].
- **Test de refutación:** IC continuo del shift del centro de masa vs retorno forward
  1/2/3d, no-solapado; permutación; placebo con shift aleatorio; controlar por funding
  y por el propio precio (evitar que sea solo momentum).
- **Diferencia con lo ya probado:** ninguna previa mira la *forma* de la distribución
  de OI por strike. Distinta de F2 (skew de precio de opción) y de K3-01 (max-pain):
  aquí la señal es el **desplazamiento temporal del OI entre strikes**, no el nivel
  de skew ni la distancia al max-pain.
- **Fuentes:** Deribit API docs https://docs.deribit.com/ (`get_instruments` + OI por instrumento).
  Concepto de trading informado en opciones: Easley, O'Hara & Srinivas (1998), "Option Volume and
  Stock Prices", J. Finance.
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 (forward-collect) · Novedad 4.0 · Retorno 3.0 → **ponderado 3.4**

---

## B. CME y COT (posicionamiento reportado)

### K3-07 — CFTC COT Leveraged-Funds Net Position (posicionamiento apalancado reportado)
- **Mecanismo:** el reporte semanal COT de la CFTC desglosa el OI de los futuros
  BTC de CME por tipo de participante (dealers, asset managers, **leveraged funds**,
  non-reportables). Un extremo en el neto de los leveraged funds (hedge funds) es un
  proxy *reportado oficialmente* de crowding de posicionamiento — la misma familia
  que #6/F5 (derivados), pero vía dato regulatorio, no de exchange.
- **Lag / persistencia:** el COT se publica el viernes con corte del martes anterior
  (lag de 3 días, público). Ese lag conocido + que pocos cripto-traders lo leen
  sostiene el edge: el posicionamiento extremo revierte en la semana siguiente.
- **Señal y horizonte:** z-score del neto de leveraged funds; extremo largo → short
  forward (y viceversa). Horizonte 1–2 semanas (frecuencia semanal del dato).
- **Datos:** CFTC "Traders in Financial Futures" (TFF) report, Bitcoin CME, 2018→hoy
  (publicg.cftc.gov, CSV descargable, gratis). ~400 semanas. [gratis].
- **Test de refutación:** IC del z-score vs retorno forward 1–2 semanas, no-solapado
  (dato ya es semanal → poco solape); permutación; placebo con shuffling de la serie;
  OOS por mitades. Controlar por funding de Binance (que es la señal rápida equivalente).
- **Diferencia con lo ya probado:** #6 usa funding de exchange (diario/8h). Esto usa
  el **posicionamiento institucional reportado por la CFTC** (fuente de datos
  completamente distinta, regulatoria, frecuencia semanal, universo institucional CME
  en vez de retail perp). Mismo *tema* (posicionamiento = señal real), nueva fuente.
- **Fuentes:** CFTC Commitments of Traders, Traders in Financial Futures (TFF) — portal de datos
  públicos https://publicreporting.cftc.gov/ y página oficial COT https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  ; evidencia COT en commodities: Sanders, Irwin & Merrin (2009), J. Agricultural & Applied Economics.
- **Score §1:** Mecanismo 4.0 · Lag 4.0 · Falsabilidad 4.0 · Costo 3.5 (CSV CFTC) · Novedad 4.0 · Retorno 3.0 → **ponderado 3.8**

### K3-08 — CME Micro vs Standard OI Ratio (retail CME vs institucional)
- **Mecanismo:** CME ofrece BTC estándar (5 BTC) y Micro MBT (0.1 BTC). La ratio de
  OI micro/estándar mide la **composición retail vs institucional** dentro del canal
  regulado. Un salto en la participación micro (retail) suele marcar euforia tardía;
  dominancia del estándar (institucional) marca convicción. Es un termómetro de
  "manos" dentro de CME que nadie en retail cripto construye.
- **Lag / persistencia:** la composición cambia lentamente (días); el dato de OI por
  producto se publica diario con delay. Lag estructural real.
- **Señal y horizonte:** z-score de la ratio micro/estándar; extremo retail → fade
  (short); extremo institucional → seguir. Horizonte 3–10 días.
- **Datos:** CME daily OI por producto (BTC, MBT) — CME settlements/volume&OI reports,
  gratis con delay, 2021→hoy (MBT lanzado may-2021). [gratis con delay].
- **Test de refutación:** IC de la ratio vs retorno forward 3/5/10d, no-solapado;
  permutación; placebo; OOS. Controlar por nivel de precio (evitar que sea solo
  proxy de tendencia).
- **Diferencia con lo ya probado:** ninguna previa separa retail vs institucional por
  tamaño de contrato. Distinto de #7 (coin-M vs linear de Bybit, que mide convexidad
  de margen) — aquí la partición es por **tamaño de contrato en CME** (composición de
  participante), no por tipo de colateral.
- **Fuentes:** CME Group Volume & Open Interest (reportes diarios por producto, BTC y MBT Micro)
  https://www.cmegroup.com/market-data/volume-open-interest.html
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 · Novedad 4.5 · Retorno 2.5 → **ponderado 3.4**

### K3-09 — CME Settlement-Window Drift (deriva alrededor del fixing de 4pm CT)
- **Mecanismo:** los futuros de CME liquidan contra una ventana de referencia
  (BRR/BRRNY de CF Benchmarks, fijada alrededor de las 16:00 London / horario CME).
  Los que necesitan marcar contra ese fixing (fondos, estructurados) concentran
  flujo en la ventana, creando una deriva predecible justo antes y una reversión
  después. Flujo mecánico anclado a un horario público.
- **Lag / persistencia:** el horario es fijo y conocido; el micro-patrón de
  pre-fixing/reversión persiste porque está atado a obligaciones de marcación, no a
  especulación. (Horizonte corto → marcar parte como research-only si cae sub-hora.)
- **Señal y horizonte:** retorno en [fixing-30m, fixing] vs [fixing, fixing+60m];
  buscar deriva + reversión. Horizonte: 1–2 h alrededor del fixing (parcialmente
  research-only por el scheduler, pero la *reversión a 1–4 h* sí es operable).
- **Datos:** klines 1h/15m BTC (ya los tenemos) + horario del BRR de CF Benchmarks
  (público). 2019→hoy. [gratis].
- **Test de refutación:** retorno medio pre/post fixing vs control a la misma hora en
  días sin relevancia de fixing (findes); permutación de la hora de referencia
  (placebo con horas falsas); no-solapado por día. Si una hora placebo da el mismo
  patrón, refutado (como pasó con 00:00 UTC vs 12:00).
- **Diferencia con lo ya probado:** el "00:00 UTC Synchronization Impulse" refutado
  probó medianoche UTC como reloj Schelling y el control de las 12:00 revirtió igual.
  Esto ancla a un **fixing institucional específico y verificable (BRR 16:00)** con
  un mecanismo de marcación concreto, no a un reloj redondo arbitrario; y el placebo
  de hora es parte del diseño precisamente por esa lección.
- **Fuentes:** CME CF Bitcoin Reference Rate (BRR/BRRNY) — CF Benchmarks https://www.cfbenchmarks.com/data/indices/BRR
  (ventana de fixing 15:00–16:00 London); metodología referenciada desde CME crypto reference rates.
- **Score §1:** Mecanismo 3.0 · Lag 2.5 (horizonte corto) · Falsabilidad 4.0 · Costo 4.5 · Novedad 3.5 · Retorno 2.0 → **ponderado 3.1**

### K3-10 — CME Holiday Closure Vol-Bunching (cripto absorbe flujo con CME cerrado)
- **Mecanismo:** CME cierra en feriados US y fines de semana, pero el spot cripto no.
  Cuando llega información macro mientras CME está cerrado, el ajuste se concentra en
  el spot/perp 24/7 y luego, **a la reapertura de CME**, hay un gap de reconciliación
  entre el último settlement CME y el spot. La dirección/tamaño del desajuste
  acumulado durante el cierre predice el movimiento de reconciliación.
- **Lag / persistencia:** el calendario de feriados CME es público y fijo; la
  reconciliación ocurre en las primeras horas de reapertura. Lag estructural claro.
- **Señal y horizonte:** medir el retorno spot acumulado durante el cierre de CME;
  predecir el gap de reapertura y su reversión parcial. Horizonte: primeras 1–4 h de
  reapertura CME.
- **Datos:** calendario de feriados/horario CME (público) + klines spot 1h (ya los
  tenemos) + settlement CME. 2018→hoy. [gratis].
- **Test de refutación:** regresión del gap de reapertura sobre el retorno spot del
  período de cierre; separar continuación vs reversión; permutación; no-solapado;
  **placebo** con "cierres falsos" en días normales. Pocos feriados/año → declarar
  power limitado.
- **Diferencia con lo ya probado:** el CME-gap reversal refutado miraba el gap del
  **lunes tras el fin de semana** y encontró *continuación*, no reversión, con p=0.86.
  Esto se enfoca en **feriados US específicos** (no todos los weekends) y modela
  explícitamente la *magnitud del desajuste acumulado* como predictor del signo —
  variable y muestra distintas. Si replica el null del weekend, se descarta.
- **Fuentes:** CME Group calendario/horario de negociación (incl. feriados) https://www.cmegroup.com/tools-information/holiday-calendar.html
  ; concepto de gaps en mercados cerrados (texto estándar, sin URL única).
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.0 · Retorno 2.5 → **ponderado 3.1**

### K3-11 — CME Basis Term-Structure Slope (contango/backwardation institucional como régimen)
- **Mecanismo:** la pendiente de la curva de futuros CME (next − front anualizado)
  refleja el apetito institucional de apalancamiento largo (contango alto = demanda
  de carry larga). Extremos de contango marcan euforia apalancada institucional;
  backwardation marca stress/desapalancamiento. Es un posicionamiento institucional
  *estructural* (no el funding retail de perps).
- **Lag / persistencia:** la curva se mueve lento (días); extremos de contango han
  precedido techos. El dato es público pero poco mirado por retail cripto.
- **Señal y horizonte:** z-score de la pendiente anualizada; contango extremo → fade
  (short); backwardation extrema → posible rebote. Horizonte 5–15 días.
- **Datos:** CME settlement de front y next BTC futures (cmegroup, gratis con delay),
  2017→hoy. [gratis con delay | gated histórico fino].
- **Test de refutación:** IC de la pendiente vs retorno forward 5/10/15d, no-solapado;
  permutación; OOS; controlar por funding de Binance y por basis spot-perp (F3, que
  fue null) para probar que el componente **CME-institucional** aporta algo distinto.
- **Diferencia con lo ya probado:** F3 (basis spot-perp de Binance) fue refutado, pero
  medía la base *retail perp*. Esta usa la **curva de futuros con fecha de entrega de
  CME** (institucional, término fijo) — fuente y naturaleza del participante distintas.
  Si replica el null de F3, se documenta como confirmación de que el basis no tiene edge.
- **Fuentes:** CME Group Bitcoin futures settlements https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin.settlements.html
  ; concepto de estructura de términos y carry en futuros (texto estándar, sin URL única).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.2**

---

## C. Calendario macro (FOMC / CPI / NFP)

### K3-12 — FOMC Pre-Announcement Drift (deriva alcista en la ventana pre-FOMC)
- **Mecanismo:** en equities existe el "pre-FOMC announcement drift" documentado
  (Lucca-Moench, NY Fed): el mercado tiende a subir en las ~24 h previas al anuncio
  del FOMC, por reducción de incertidumbre/posicionamiento. Si BTC se comporta como
  activo de riesgo beta-alto, debería heredar (y amplificar) esa deriva de calendario.
  Fechas del FOMC publicadas con un año de anticipación → puro calendario.
- **Lag / persistencia:** el drift es un fenómeno de ventana fija (pre-anuncio) que
  en equities persistió décadas pese a ser conocido; su réplica en cripto es novedosa.
- **Señal y horizonte:** long BTC en la ventana [anuncio−24h, anuncio]; cerrar en el
  anuncio. ~8 FOMC/año. Horizonte ~24 h.
- **Datos:** calendario FOMC (federalreserve.gov, fijo, 2015→hoy, ~90 reuniones) +
  klines 1h BTC. [gratis].
- **Test de refutación:** retorno medio en la ventana pre-FOMC vs 90 ventanas placebo
  aleatorias de 24 h; test de medias + permutación; no-solapado (1 obs/reunión); OOS
  por mitades (el drift de equities se debilitó post-2011 → chequear decaimiento).
- **Diferencia con lo ya probado:** ninguna hipótesis previa usa el calendario FOMC.
  Las ideas macro previas (Gold→BTC) usaban *niveles de otro activo*, no un **evento
  de calendario de política monetaria con fecha fija publicada**. Mecanismo y dato nuevos.
- **Fuentes:** Lucca & Moench (2015) "The Pre-FOMC Announcement Drift", J. Finance — versión NY Fed
  Staff Report 512 https://www.newyorkfed.org/research/staff_reports/sr512.html ; calendario FOMC
  oficial https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 4.0 · Costo 4.5 (klines ya bajados) · Novedad 4.0 · Retorno 3.0 → **ponderado 3.7**

### K3-13 — CPI/NFP Vol-Crush Reversal (sobre-reacción a datos macro y reversión)
- **Mecanismo:** los releases de CPI (mensual, 08:30 ET) y NFP (primer viernes,
  08:30 ET) generan un spike de vol y un movimiento inicial que a menudo
  **sobre-reacciona** y revierte parcialmente en las horas siguientes, porque el
  primer movimiento es de bots de titulares + liquidaciones, no de reposicionamiento
  razonado. Fechas publicadas por el BLS con calendario anual.
- **Lag / persistencia:** la reversión post-release ocurre en 2–12 h; persiste porque
  requiere capital paciente que entra a contramano del spike inicial.
- **Señal y horizonte:** medir el retorno en los primeros 15–30 min post-release;
  fade de la parte "excesiva" (más allá de 1.5σ) en las 2–8 h siguientes. Horizonte
  2–8 h, dirección contraria al spike.
- **Datos:** calendario BLS de CPI/NFP (bls.gov/schedule, fijo, 2018→hoy) + klines
  15m/1h BTC. [gratis].
- **Test de refutación:** IC del retorno post-spike vs retorno forward 2/4/8 h,
  condicionado a magnitud del spike; no-solapado (mensual); permutación; **placebo**
  con días/horas sin release (clave para no confundir con reversión intradía genérica,
  que ya mató al 00:00 UTC impulse). OOS por mitades.
- **Diferencia con lo ya probado:** el 00:00 UTC refutado halló reversión intradía
  *genérica* sin especificidad de hora. Esto exige que la reversión sea **condicional
  a un evento macro con fecha/hora fija del BLS** y usa el placebo de días-sin-release
  como filtro central; si la reversión no es mayor en días de release, se refuta.
- **Fuentes:** BLS release schedule — CPI https://www.bls.gov/schedule/news_release/cpi.htm y
  Employment Situation (NFP) https://www.bls.gov/schedule/news_release/empsit.htm ; sobre reacción
  de macro-anuncios: literatura de "announcement effects" (p.ej. Andersen et al. 2003, AER), sin URL única.
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.0 · Retorno 2.5 → **ponderado 3.1**

### K3-14 — Macro-Blackout Vol Compression (compresión de vol en ventanas sin catalizador)
- **Mecanismo:** entre el último dato macro de un mes y el siguiente gran evento
  (ventanas "blackout" sin FOMC/CPI/NFP ni expiry grande), la vol realizada tiende a
  comprimirse porque falta catalizador y los dealers venden gamma con tranquilidad.
  El mapa de eventos de calendario permite predecir *a priori* qué días serán
  "desérticos" → régimen de baja vol → favorece mean-reversion/carry sobre momentum.
- **Lag / persistencia:** el calendario de eventos se conoce con semanas de
  anticipación; la compresión persiste hasta el próximo catalizador.
- **Señal y horizonte:** construir un "densidad de eventos" diaria (FOMC/CPI/NFP/
  expiry/opex próximos); días de baja densidad → esperar vol realizada menor →
  condicionar estrategias. Horizonte 1–5 días (feature de régimen).
- **Datos:** calendarios combinados (Fed, BLS, Deribit/CME expiry) + klines para RV.
  2018→hoy. [gratis].
- **Test de refutación:** regresión de vol realizada forward sobre la densidad de
  eventos; permutación de las etiquetas de evento; no-solapado; OOS. Chequear que no
  sea solo autocorrelación de vol (incluir vol rezagada como control, como se hizo en
  critical-slowing para evitar el "var ≡ vol" trivial).
- **Diferencia con lo ya probado:** critical-slowing/EWS (refutado) usaba varianza
  rezagada endógena (trivial). Esto usa un **predictor exógeno de calendario**
  (densidad de eventos conocidos a futuro) para la vol, no la vol pasada — evita el
  problema var≡vol por construcción.
- **Fuentes:** calendarios públicos — FOMC https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  y BLS https://www.bls.gov/schedule/news_release/ ; efecto de anuncios programados sobre la vol:
  Ederington & Lee (1993), J. Finance (sin URL única).
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.5 · Retorno 2.0 → **ponderado 3.1**

### K3-15 — Fed Balance-Sheet / Reserves Weekly Delta → Risk (liquidez macro)
- **Mecanismo:** la liquidez del sistema (balance de la Fed H.4.1, reverse repo RRP,
  Treasury General Account TGA) condiciona el apetito de riesgo con lag. Caídas de
  RRP+TGA inyectan liquidez a los mercados; subidas la drenan. BTC, como activo de
  riesgo de duración larga, responde con rezago de días a estos cambios de liquidez
  neta, que se publican semanalmente en fechas fijas.
- **Lag / persistencia:** los datos salen semanales (H.4.1 jueves, RRP diario de la
  NY Fed); el efecto sobre riesgo tarda días en propagarse → lag estructural real.
- **Señal y horizonte:** construir "liquidez neta" = balance Fed − RRP − TGA; su
  cambio semanal (z-score) predice retorno de BTC forward 5–10 días. Long en
  expansión de liquidez, short en contracción. Horizonte 1–2 semanas.
- **Datos:** FRED (series WALCL, RRPONTSYD, WTREGEN), gratis vía API FRED, 2015→hoy.
  [gratis].
- **Test de refutación:** IC del cambio de liquidez neta vs retorno forward 5/10d,
  no-solapado (frecuencia semanal); permutación; OOS por mitades; controlar por DXY
  (para que no sea solo el dólar). Riesgo de espurio por tendencia común → incluir
  diferencias, no niveles.
- **Diferencia con lo ya probado:** Gold→BTC (refutado) y stablecoin-flow (débil)
  miraban *oferta de activos cripto o un metal*. Esto mide la **liquidez del banco
  central (fuente FRED, macro TradFi)** como driver cross-asset — fuente y mecanismo
  distintos; es flujo/liquidez macro, no oferta on-chain.
- **Fuentes:** FRED — WALCL https://fred.stlouisfed.org/series/WALCL , RRPONTSYD
  https://fred.stlouisfed.org/series/RRPONTSYD , WTREGEN https://fred.stlouisfed.org/series/WTREGEN
  (todas series públicas de la Fed vía FRED/St. Louis Fed).
- **Score §1:** Mecanismo 3.0 · Lag 3.5 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.0 · Retorno 3.0 → **ponderado 3.3**

### K3-16 — Options Expiry × FOMC Collision (coincidencia de expiry grande con evento macro)
- **Mecanismo:** cuando un vencimiento de opciones grande (trimestral) cae cerca de
  un FOMC o CPI, el short-gamma del dealer + el shock macro se amplifican: la
  cobertura delta en régimen short-gamma magnifica el movimiento post-dato. La
  coincidencia de *dos* eventos de calendario conocidos crea un predictor de
  **vol amplificada** que casi nadie modela conjuntamente.
- **Lag / persistencia:** ambos calendarios son públicos con meses de anticipación;
  la interacción es un efecto condicional que no se arbitra porque requiere modelar
  dos calendarios a la vez.
- **Señal y horizonte:** flag de "colisión" (expiry trimestral dentro de ±2 días de
  FOMC/CPI); predecir vol realizada mayor en esas ventanas → subir tamaño de
  estrategias de breakout / comprar vol. Horizonte 1–3 días.
- **Datos:** calendarios FOMC+BLS+expiry (todos públicos) + klines. 2019→hoy.
  [gratis]. Pocos eventos de colisión → power limitado (declararlo).
- **Test de refutación:** vol realizada en ventanas de colisión vs (expiry-solo) y
  (FOMC-solo) y (ninguno); test de interacción; permutación; no-solapado. Si la
  colisión no supera la suma de efectos marginales, no hay interacción → refutado.
- **Diferencia con lo ya probado:** combina K3-02 (gamma trimestral) y K3-12 (FOMC)
  pero como **término de interacción de dos calendarios**, un ángulo que ninguna idea
  previa (ni de rondas 1-2) consideró. Novedad en la conjunción.
- **Fuentes:** calendarios FOMC https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm ,
  BLS https://www.bls.gov/schedule/news_release/ y expiries Deribit https://docs.deribit.com/
  (`get_instruments`); gamma-exposure (GEX) como concepto: nota pública de SqueezeMetrics (sin DOI).
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.0 (pocos eventos) · Costo 4.0 · Novedad 4.0 · Retorno 2.5 → **ponderado 3.2**

---

## D. ETF e índices

### K3-17 — ETF Premium/Discount to NAV (desvío de precio del ETF vs valor subyacente)
- **Mecanismo:** los ETF spot de BTC (IBIT, FBTC, etc.) deberían cotizar cerca de su
  NAV, pero durante estrés o demanda desbalanceada aparece un **premium/discount**
  intradía mientras los Authorized Participants tardan en crear/redimir. Un premium
  persistente señala demanda institucional que aún no se trasladó al spot → el spot
  sube para cerrar el gap; un discount, lo inverso. Es presión de arbitraje con lag.
- **Lag / persistencia:** el arbitraje AP se ejecuta en T+0/T+1 pero no es
  instantáneo (ventanas de creación, horario TradFi); el gap persiste horas.
- **Señal y horizonte:** medir (precio ETF − iNAV)/NAV al cierre; premium alto →
  long spot forward; discount → short. Horizonte 1–2 días (resolución del arbitraje).
- **Datos:** precios de cierre + NAV diario de IBIT/FBTC (emisores publican NAV;
  Nasdaq/Yahoo precio), 2024-01→hoy (ETF spot aprobados ene-2024). [gratis precio;
  NAV en sitios de emisores gratis]. Historia corta (~2 años) → power limitado.
- **Test de refutación:** IC del premium/discount vs retorno spot forward 1/2d,
  no-solapado; permutación; OOS. Controlar por retorno del propio ETF (evitar
  momentum trivial). Chequear que no sea solo el desfase horario TradFi vs 24/7.
- **Diferencia con lo ya probado:** F1 (ETF net-flow) estaba data-gated y medía
  *flujos* (creación/redención en $). Esto mide el **premium/discount de precio vs
  NAV**, una señal de precio pública (no el flujo gated de Farside) con mecanismo de
  arbitraje AP distinto. Data accesible sin el CSV manual que bloqueó a F1.
- **Fuentes:** iShares Bitcoin Trust (IBIT) página oficial con NAV/precio de mercado
  https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf ; literatura de premium/discount
  y arbitraje de ETF: Petajisto (2017), "Inefficiencies in the Pricing of Exchange-Traded Funds",
  Financial Analysts Journal (sin URL única).
- **Score §1:** Mecanismo 3.5 · Lag 3.0 · Falsabilidad 3.5 · Costo 3.0 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.2**

### K3-18 — ETF Volume-Share Rotation (cuándo domina el canal regulado vs el nativo)
- **Mecanismo:** la ratio volumen(ETF)/volumen(spot cripto 24/7) mide si el flujo
  marginal viene del canal institucional TradFi o del nativo. Un salto en la
  participación del ETF suele marcar entrada de dinero "lento" (allocators) que tiene
  continuación; dominancia del canal nativo marca flujo especulativo volátil. Es un
  termómetro de *quién* está empujando el precio.
- **Lag / persistencia:** el flujo de allocators institucionales vía ETF es pegajoso
  (se mueve en programas de semanas) → continuación; el dato de volumen ETF es diario, público.
- **Señal y horizonte:** z-score de la volume-share del ETF; alza → momentum
  institucional (seguir). Horizonte 3–10 días.
- **Datos:** volumen diario de IBIT/FBTC (Nasdaq/Yahoo) + volumen spot agregado
  (Binance klines). 2024→hoy. [gratis]. Historia corta.
- **Test de refutación:** IC de la volume-share vs retorno forward 3/5/10d,
  no-solapado; permutación; OOS; controlar por precio.
- **Diferencia con lo ya probado:** F1 (net-flow en $, gated). Esto es **volumen
  relativo de canal** (no flujo neto direccional) con data de volumen pública. Métrica
  y fuente distintas; mide composición de participante, no dirección del flujo.
- **Fuentes:** volumen diario de IBIT en Nasdaq https://www.nasdaq.com/market-activity/etf/ibit
  y volumen spot agregado vía Binance klines (API pública); sin paper único para la métrica de volume-share.
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 3.0 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.1**

### K3-19 — Index Rebalance Front-Running (rebalanceo de índices cripto con fecha conocida)
- **Mecanismo:** índices cripto (CoinDesk CDI, Bitwise 10, MarketVector, CF) y los
  productos que los replican rebalancean en fechas publicadas (trimestral/mensual).
  Las altcoins que **entran** al índice reciben compra mecánica de los fondos
  indexados en la fecha; las que **salen** reciben venta. El anuncio precede a la
  ejecución por días → front-running legal de un flujo forzado con fecha.
- **Lag / persistencia:** metodología y fecha son públicas; el flujo de ejecución
  ocurre el día del rebalance → la deriva pre-rebalance y la reversión post son estructurales.
- **Señal y horizonte:** al anunciarse altas/bajas, long las que entran / short las
  que salen hasta el día de ejecución; fade post-ejecución. Horizonte: días desde
  anuncio hasta rebalance (~3–10 días).
- **Datos:** metodologías y constituyentes de índices (CoinDesk Indices, Bitwise,
  MarketVector — publicados) + klines de las alts afectadas. 2021→hoy. [gratis los
  anuncios; requiere armar el calendario de rebalances por índice].
- **Test de refutación:** CAR (cumulative abnormal return, alt vs BTC) desde anuncio
  a ejecución y post; **placebo** con fechas random (igual que se hizo con F4 unlocks,
  que murió justo por el placebo); permutación; no-solapado por evento; OOS.
- **Diferencia con lo ya probado:** F4 (unlocks/vesting) fue el "oferta forzada con
  fecha" refutado por placebo. Esto es **demanda forzada por indexación** (lado
  comprador, fondos replicantes) — lado del flujo y fuente (metodología de índice vs
  schedule de vesting) distintos. Hereda la lección: el placebo es central y, si el
  CAR no supera al placebo, se refuta igual que F4.
- **Fuentes:** metodologías públicas de índices — CoinDesk Indices https://indices.coindesk.com/
  y Bitwise https://bitwiseinvestments.com/ (MarketVector también publica metodologías; sin URL
  verificada aquí por bloqueo del fetch); efecto de reconstitución de índices: Chen, Noronha &
  Singal (2004), J. Finance (sin URL única).
- **Score §1:** Mecanismo 3.5 · Lag 3.5 · Falsabilidad 3.5 · Costo 2.5 · Novedad 3.5 · Retorno 3.0 → **ponderado 3.4**

### K3-20 — Nasdaq/BTC Correlation Regime Shift (quiebre de correlación con equities tech)
- **Mecanismo:** BTC alterna entre régimen "risk-asset" (alta correlación con Nasdaq)
  y "descorrelacionado". El *cambio* de régimen de correlación (medido rolling) es
  informativo: cuando BTC se desacopla al alza mientras Nasdaq cae, suele marcar
  fuerza idiosincrática con continuación; cuando colapsa la correlación a la baja,
  fragilidad. El quiebre se detecta antes de que el precio lo confirme del todo.
- **Lag / persistencia:** la correlación rolling cambia en días; el régimen persiste
  semanas. Dato trivial (precios públicos de ambos).
- **Señal y horizonte:** correlación rolling 20d BTC-Nasdaq y su derivada; condicionar
  dirección según el signo del desacople. Horizonte 3–10 días (feature de régimen más
  que gatillo).
- **Datos:** Nasdaq/NDX diario (Yahoo/Stooq, gratis) + BTC klines. 2018→hoy. [gratis].
- **Test de refutación:** IC del cambio de correlación vs retorno forward, no-solapado;
  permutación; OOS; controlar por el retorno de Nasdaq (evitar que sea solo beta).
  Ojo con el riesgo de espejismo de ventanas solapadas (rolling corr autocorrelado) →
  usar muestreo no-solapado estricto.
- **Diferencia con lo ya probado:** Gold→BTC (refutado) probó lead-lag de *nivel* de un
  metal. Esto usa el **cambio de correlación con equities tech** como variable de
  régimen (segunda derivada, no nivel) — métrica (correlación dinámica) y activo
  (Nasdaq, no oro) distintos.
- **Fuentes:** NDX/Nasdaq-100 diario vía Stooq https://stooq.com/ (CSV gratis) o Yahoo Finance
  https://finance.yahoo.com/quote/%5ENDX + BTC klines; regímenes de correlación cripto-equity es
  observación de mercado post-2020, sin paper único verificable.
- **Score §1:** Mecanismo 2.5 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.0 · Retorno 2.5 → **ponderado 3.0**

### K3-21 — MSTR/Equity-Proxy Premium Divergence (proxy apalancado de BTC en TradFi)
- **Mecanismo:** acciones como MSTR cotizan con un **premium sobre su NAV en BTC**
  que refleja el apetito especulativo apalancado de TradFi por exposición a cripto.
  Cuando el premium de MSTR se dispara (euforia), es una señal de sentimiento tardío
  → fade de BTC; cuando colapsa a descuento, capitulación → posible piso. Es un
  termómetro de posicionamiento en el canal equity, invisible para el cripto-trader.
- **Lag / persistencia:** el premium se mueve en horario TradFi (lag vs 24/7 cripto);
  los extremos de sentimiento equity preceden a giros de BTC por días.
- **Señal y horizonte:** premium = cap MSTR / (BTC holdings × precio BTC); z-score;
  extremo alto → short BTC, extremo bajo → long. Horizonte 3–10 días.
- **Datos:** precio MSTR (Yahoo/Stooq) + BTC holdings reportados (SEC 8-K/press,
  público) + precio BTC. 2020→hoy. [gratis]. Nota: el leverage/estructura de MSTR
  cambió en el tiempo → controlar por eso.
- **Test de refutación:** IC del z-score del premium vs retorno BTC forward 3/5/10d,
  no-solapado; permutación; OOS. **Placebo/control**: separar el efecto del propio
  retorno de MSTR (que tiene beta a BTC) para aislar el *premium* como señal. Riesgo:
  reflexividad (MSTR compra BTC) → documentar.
- **Diferencia con lo ya probado:** ninguna previa usa un equity-proxy. Distinta de
  todas las ideas de posicionamiento por derivados (#6/F5): aquí el sentimiento se lee
  en un **vehículo equity de TradFi (MSTR)**, fuente y canal nuevos.
- **Fuentes:** filings de MicroStrategy/Strategy en SEC EDGAR https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001050446&type=8-K
  (holdings de BTC reportados en 8-K); precio de MSTR vía Stooq https://stooq.com/ o Yahoo
  https://finance.yahoo.com/quote/MSTR ; "premium to NAV" es discusión pública, sin paper único.
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.0 · Costo 3.0 · Novedad 4.0 · Retorno 3.0 → **ponderado 3.2**

---

## E. Horario TradFi / fronteras de sesión

### K3-22 — US Equity Open/Close Spillover (apertura y cierre de Wall Street → BTC)
- **Mecanismo:** la apertura (09:30 ET) y el cierre/subasta (16:00 ET) de la bolsa
  US concentran flujo de allocators y rebalanceo de carteras multiactivo que incluyen
  cripto. En esos minutos, BTC recibe una presión direccional heredada del tono de
  equities (gap de apertura, market-on-close). El horario es fijo y público; el
  spillover tiene lag porque el cripto-nativo 24/7 no anticipa el flujo TradFi.
- **Lag / persistencia:** el efecto se concentra en la ventana de apertura/cierre y
  se propaga 1–3 h; persiste porque está atado a obligaciones de horario, no a especulación.
- **Señal y horizonte:** retorno de BTC en [09:30 ET, 10:30 ET] condicionado al gap
  de apertura de SPY/NDX; y reversión/continuación tras la subasta de cierre.
  Horizonte 1–3 h (parcialmente research-only; la pata a 2–4 h es operable).
- **Datos:** SPY/NDX intradía (Stooq/Yahoo 1m-1h, gratis) + BTC klines 15m/1h.
  2018→hoy. [gratis].
- **Test de refutación:** retorno BTC por hora-del-día TradFi vs **placebo de horas
  equivalentes en fin de semana** (cuando la bolsa está cerrada); si el patrón
  aparece igual el finde, no es spillover de equities → refutado (misma lógica que
  mató al 00:00 UTC). Permutación; no-solapado por día.
- **Diferencia con lo ya probado:** #1 (timezone handoff) usa **entropía del reparto
  de volumen por hora** (métrica de concentración). Esto usa el **nivel/dirección del
  retorno de equities US en horarios fijos de apertura/cierre** como predictor
  cross-asset — métrica (retorno de otro activo) y mecanismo (spillover TradFi) distintos.
- **Fuentes:** datos intradía de SPY/NDX vía Stooq https://stooq.com/ (CSV gratis) o Yahoo Finance
  https://finance.yahoo.com/quote/SPY ; retornos overnight vs intraday como fenómeno documentado
  (p.ej. Lou, Polk & Skouras 2019, JFE), sin URL única.
- **Score §1:** Mecanismo 3.0 · Lag 2.5 (horizonte corto) · Falsabilidad 4.0 · Costo 4.0 · Novedad 3.0 · Retorno 2.5 → **ponderado 3.1**

### K3-23 — Quarter-End Rebalancing Flow (rebalanceo 60/40 de fin de trimestre)
- **Mecanismo:** los fondos multiactivo rebalancean a pesos objetivo a fin de
  trimestre (y fin de mes). Si cripto tuvo un trimestre fuerte vs bonos/equities, los
  rebalanceadores **venden** cripto los últimos días para volver al peso objetivo; si
  tuvo un trimestre débil, **compran**. Es un flujo mecánico, contrario al retorno
  reciente, anclado al calendario contable.
- **Lag / persistencia:** la fecha (último día hábil del trimestre) es conocida; el
  flujo se concentra en los últimos 2–3 días y revierte a principios del trimestre siguiente.
- **Señal y horizonte:** signo del retorno trimestral de BTC vs equities → predecir
  venta (si fuerte) o compra (si débil) en los últimos 3 días; fade post-fin-de-trimestre.
  Horizonte 3–5 días alrededor del cierre trimestral.
- **Datos:** klines BTC + SPY (gratis) + calendario de fin de trimestre (trivial).
  2017→hoy, ~36 trimestres. [gratis]. Power limitado por pocos eventos.
- **Test de refutación:** retorno BTC en los últimos 3 días del trimestre condicionado
  al signo del performance relativo; vs **placebo** de ventanas no-fin-de-trimestre;
  permutación; no-solapado; OOS. Pocos eventos → declarar underpowered.
- **Diferencia con lo ya probado:** ninguna previa usa rebalanceo de fin de trimestre.
  Es flujo cross-asset con fecha contable; distinto del CME-roll (K3-04, que es
  rollover de contrato, no rebalanceo de cartera) y de todo lo refutado.
- **Fuentes:** precios de BTC (klines) y SPY/NDX (Stooq https://stooq.com/ , Yahoo
  https://finance.yahoo.com/ ) para construir el performance relativo; el flujo de rebalanceo de
  fin de trimestre es tesis de research de sell-side (JPM/Nomura), sin URL pública única verificable
  → marcar como "sin fuente verificable" para el dato de flujo.
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.0 (pocos eventos) · Costo 4.0 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.1**

### K3-24 — Asia-Session Funding Reset Asymmetry (asimetría del funding por sesión horaria)
- **Mecanismo:** el funding de los perps se settlea cada 8 h (00:00/08:00/16:00 UTC),
  horarios que alinean con cierres/aperturas de sesiones regionales. Si el crowding
  de posicionamiento se concentra sistemáticamente en una sesión horaria (p.ej. la
  asiática fondea más agresivo), el reset de funding en ese horario genera un desarme
  parcial predecible. Es la interacción del calendario de settlement con la geografía del flujo.
- **Lag / persistencia:** horarios fijos de settlement; el desarme post-settlement
  ocurre en 1–4 h. Pocos lo modelan por sesión.
- **Señal y horizonte:** descomponer el funding por slot de settlement y por sesión
  dominante; shortear tras el slot con funding anómalamente alto. Horizonte 1–8 h.
- **Datos:** Binance `fundingRate` 8h (ya lo tenemos) + klines por hora. 2019→hoy. [gratis].
- **Test de refutación:** condicionar el edge de reversión al slot de settlement y a
  la sesión; **placebo** con slots no-settlement; permutación; no-solapado. Si no hay
  asimetría por slot/sesión, se reduce a #6 sin aporte → refutado.
- **Diferencia con lo ya probado:** #6 usa funding agnóstico del horario; #1 usa
  entropía de volumen por sesión. Esto cruza **funding × slot de settlement × sesión
  horaria** — una interacción de calendario (settlement) con geografía que ninguna
  idea previa modeló. Si no supera a #6, se descarta explícitamente.
- **Fuentes:** Binance USDⓈ-M Futures API, fundingRate https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
  (settlement cada 8 h); #1 (timezone handoff) y #6 (funding dispersion) de signal-hypotheses.md.
- **Score §1:** Mecanismo 2.5 · Lag 2.5 · Falsabilidad 3.5 · Costo 4.5 · Novedad 3.0 · Retorno 2.0 → **ponderado 2.9**

### K3-25 — Triple-Witching Spillover (triple hora bruja de equities → BTC)
- **Mecanismo:** el tercer viernes de marzo/junio/sep/dic vencen simultáneamente
  opciones sobre índices, opciones sobre acciones y futuros de índices en US ("triple
  witching"), generando el mayor volumen y vol del trimestre en equities. Ese shock de
  vol y el reposicionamiento masivo de dealers de equities **se contagia a BTC** como
  activo de riesgo correlacionado, con una ventana de calendario fija y conocida.
- **Lag / persistencia:** fecha fija y pública; el contagio de vol persiste el día del
  witching y el siguiente; pocos cripto-traders lo tienen en el radar.
- **Señal y horizonte:** vol realizada y |retorno| de BTC en la ventana del triple
  witching vs control; condicionar estrategias de breakout. Horizonte 1–2 días.
- **Datos:** calendario de triple witching (derivable, 3er viernes trimestral) +
  klines BTC + SPY/VIX (gratis). 2018→hoy, ~32 eventos. [gratis]. Power moderado.
- **Test de refutación:** vol realizada BTC en ventanas de witching vs placebo de
  viernes no-witching; test de medias + permutación; no-solapado; OOS. Controlar por
  coincidencia con expiry cripto trimestral (que suele caer el mismo día → separar
  atribución vs K3-02).
- **Diferencia con lo ya probado:** K3-02 es el gamma-flip del **expiry cripto**
  trimestral; esto es el spillover del **triple witching de equities US** (evento
  TradFi distinto, fuente de vol exógena). El test incluye separar ambos efectos
  porque a veces coinciden en fecha.
- **Fuentes:** calendario de vencimientos de equity/index options y futuros (3er viernes trimestral)
  — CME equity index expiration https://www.cmegroup.com/trading/equity-index/ y Cboe
  https://www.cboe.com/ ; "triple witching" como fenómeno de volumen/vol (texto estándar, sin URL única).
- **Score §1:** Mecanismo 3.0 · Lag 3.0 · Falsabilidad 3.5 · Costo 4.0 · Novedad 3.5 · Retorno 2.5 → **ponderado 3.2**

---

## Tabla resumen

| id | Nombre | Score | Datos | Fit bot |
|---|---|---|---|---|
| K3-01 | Deribit Max-Pain Pin Drift | 3.3 | Deribit OI/strike [forward-collect] | ✅ medio (horas–2d) |
| K3-02 | Quarterly-Expiry Gamma Flip | 3.3 | Expiry cal. + klines [gratis] | ✅ alto (régimen) |
| K3-03 | Perp Funding Reset × Expiry | 3.2 | Binance funding + expiry [gratis] | ✅ alto |
| K3-04 | CME BTC Futures Roll Pressure | 3.4 | CME settlements [gratis/gated] | ✅ alto |
| K3-05 | Options Expiry Vol-Crush Carry | 3.1 | Deribit DVOL + klines [gratis] | ✅ medio |
| K3-06 | Deribit OI Strike Migration | 3.4 | Deribit OI/strike [forward-collect] | ✅ alto |
| K3-07 | CFTC COT Leveraged-Funds Net | **3.8** | CFTC TFF CSV [gratis] | ✅ alto (semanal) |
| K3-08 | CME Micro vs Standard OI Ratio | 3.4 | CME OI por producto [gratis/delay] | ✅ alto |
| K3-09 | CME Settlement-Window Drift | 3.1 | klines + BRR horario [gratis] | ⚠️ bajo (horas) |
| K3-10 | CME Holiday Closure Vol-Bunching | 3.1 | CME cal. + klines [gratis] | ⚠️ medio |
| K3-11 | CME Basis Term-Structure Slope | 3.2 | CME settlements [gratis/delay] | ✅ alto |
| K3-12 | FOMC Pre-Announcement Drift | **3.7** | FOMC cal. + klines [gratis] | ✅ alto |
| K3-13 | CPI/NFP Vol-Crush Reversal | 3.1 | BLS cal. + klines [gratis] | ⚠️ medio (horas) |
| K3-14 | Macro-Blackout Vol Compression | 3.1 | Calendarios + klines [gratis] | ✅ alto (régimen) |
| K3-15 | Fed Net-Liquidity Weekly Delta | 3.3 | FRED WALCL/RRP/TGA [gratis] | ✅ alto (semanal) |
| K3-16 | Expiry × FOMC Collision | 3.2 | Calendarios + klines [gratis] | ✅ medio |
| K3-17 | ETF Premium/Discount to NAV | 3.2 | Precio+NAV ETF [gratis] | ✅ medio |
| K3-18 | ETF Volume-Share Rotation | 3.1 | Volumen ETF+spot [gratis] | ✅ alto |
| K3-19 | Index Rebalance Front-Running | 3.4 | Metodologías índice + klines [gratis] | ✅ alto |
| K3-20 | Nasdaq/BTC Correlation Regime | 3.0 | NDX + BTC [gratis] | ✅ alto (régimen) |
| K3-21 | MSTR Premium Divergence | 3.2 | MSTR + holdings SEC + BTC [gratis] | ✅ alto |
| K3-22 | US Equity Open/Close Spillover | 3.1 | SPY/NDX intradía + BTC [gratis] | ⚠️ bajo-medio (horas) |
| K3-23 | Quarter-End Rebalancing Flow | 3.1 | BTC+SPY + cal. [gratis] | ✅ medio |
| K3-24 | Asia-Session Funding Asymmetry | 2.9 | Binance funding + klines [gratis] | ⚠️ medio (horas) |
| K3-25 | Triple-Witching Spillover | 3.2 | Equity expiry cal. + klines [gratis] | ✅ medio |

**Síntesis de la tanda K3 (25 ideas):**
- Alineado con la lección meta previa (lo que tiene señal = **posicionamiento por
  derivados**), las candidatas de mayor score son las que leen posicionamiento por un
  **canal/fuente nuevos**: **K3-07 (COT CFTC, 3.8)** y **K3-12 (FOMC drift, 3.7)** son
  las dos puntas — ambas datos gratis, horizonte compatible con el scheduler, y
  mecanismo estructural claro.
- La mayoría usa **data gratis y ya disponible** (klines, funding, FRED, CFTC,
  calendarios públicos); solo K3-01/K3-06 necesitan **forward-collect** de OI-por-strike,
  y K3-04/K3-08/K3-11 dependen de settlements CME (gratis con delay o gated para histórico fino).
- Todas las ideas de *calendario de eventos* traen el **placebo de fechas/horas
  aleatorias** en el test de refutación, precisamente por las lecciones de F4 (unlock,
  murió por placebo) y 00:00 UTC (murió porque el control 12:00 revirtió igual).
- Riesgos transversales: historia corta en ETF (K3-17/18, ~2a) y MSTR; pocos eventos
  en los de frecuencia trimestral (K3-02/10/16/23/25 → underpowered, declarado en cada ficha);
  reflexividad en K3-21 (MSTR compra BTC).
