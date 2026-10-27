# K4 — Mecanismos DeFi con lag estructural

> Ronda 3 · Familia K4: liquidaciones de lending, oráculos, bridges, LST/LRT, L2.
> Autor: k4-kiro · Fecha: 2026-10-27 · Brief: `docs/research/round3/BRIEF.md`.
>
> **Línea roja aplicada:** solo datos públicos/observables (eventos on-chain, subgraphs,
> RPC público, APIs gratis/gated declaradas). Nada de insider/MNPI, acceso no autorizado,
> explotación de vulnerabilidades ni MEV/sandwich contra usuarios. "Hack" = lectura astuta
> de información pública que *ya está en cadena* pero que el mercado tarda en integrar.
>
> **Tesis de la familia.** DeFi tiene **lags estructurales duros**, no estadísticos: un
> oráculo solo actualiza cada *heartbeat* o al cruzar un *deviation threshold*; una cola de
> retiro de LST tiene un delay de protocolo medible en épocas/días; un bridge canónico tiene
> una ventana de finality/challenge fija; una liquidación en lending se dispara a un health
> factor exacto y conocido. El edge candidato no es "topología de red" (ronda 2 la mató
> entera) sino **posicionamiento/flujo apalancado con un reloj de protocolo**: cuándo *debe*
> ocurrir oferta/demanda forzada porque las reglas del contrato lo obligan, y el precio
> todavía no lo descontó. Esto se alinea con el insight meta de §4d/§4g (lo que sobrevive es
> posicionamiento por derivados / oferta forzada *con mecanismo*, no la contabilidad de
> oferta blanda). La diferencia con unlocks (F4, refutada) es que acá la oferta forzada es
> **endógena al precio y de muy corto lag** (liquidación/oráculo), no una fecha de calendario
> exógena que el mercado ya tiene en agenda.
>
> **Caveats honestos que atraviesan todas las fichas:**
> - La historia on-chain "seria" se está cerrando (beaconcha.in, Etherscan, Dune ahora piden
>   key; ver §4g). Las rutas que marco **gratis** son BigQuery público, subgraphs con free-tier,
>   RPC público y JSON en GitHub Actions. Lo **gated** lo digo explícito.
> - Varias ideas de *timing puro* solo se validan con **forward-collection** desde hoy; lo marco.
> - Toda ficha trae test **no-solapado + placebo/permutación** porque el error nº1 de rondas
>   previas fue el espejismo de ventanas solapadas.

---

## A. Liquidaciones en lending (cascada / overhang de colateral)

### K4-01 — Lending Liquidation Cascade Proximity
- **Mecanismo:** En Aave/Compound cada posición tiene un *health factor* (HF) y un umbral de
  liquidación **conocido y público**. Cuando mucho colateral (p.ej. WETH) está agrupado cerca
  de HF≈1 en un rango de precio estrecho, un movimiento adverso chico dispara liquidaciones en
  cadena que *venden colateral al mercado* → presión bajista mecánica y amplificada. La
  distribución de HF es observable *antes* de que el precio llegue ahí.
- **Lag / persistencia:** El overhang existe mientras el precio no toque la zona; cuando la
  toca, la venta forzada es inmediata pero el **drift de continuación** (más liquidaciones a
  medida que cae) dura horas. No se arbitra porque reconstruir la distribución de HF agregada
  requiere indexar posiciones, cosa que el retail no hace.
- **Señal y horizonte:** Densidad de colateral (USD) con precio-de-liquidación dentro de −5%/−10%
  del spot, normalizada por TVL del mercado. Dispara cuando la densidad entra en su decil alto.
  Horizonte 1–3 días. Sesgo short del activo colateral (o comprar vol).
- **Datos:** Aave V3 subgraph (The Graph decentralized, 100K queries/mes gratis) → entidades
  `userReserve`/`reserve` con `currentATokenBalance`, `currentTotalDebt`, `reserveLiquidationThreshold`;
  reconstruir HF por usuario. Rango: Aave V3 desde ene-2023 (ETH mainnet), más Arbitrum/Base/Optimism.
  Alternativa sin key: `th3nolo/aave-v3-data` (JSON diario de reservas, no por-usuario → solo parámetros).
  [gated-lite: free-tier subgraph].
- **Test de refutación:** Event-study del retorno fwd 1/2/3d de WETH condicionado al decil de
  densidad-de-liquidación, con **muestras no-solapadas** (una obs/día). Placebo: permutar las
  fechas de densidad vs retornos (p<0.05). Control por vol realizada 7d (que la densidad no sea
  solo un proxy de vol). OOS 2023-24 vs 2025-26.
- **Diferencia con lo ya probado:** No es "whale netflow" (§4b, refutado: flujo agregado sin
  mecanismo) ni "unlock overhang" (F4, fecha exógena). Acá la oferta forzada es **endógena al
  precio** y tiene un gatillo contractual exacto (HF=1). Ninguna ronda midió la *distribución
  de HF* como variable predictiva.
- **Fuentes:** Aave V3 health factor & liquidations — https://aave.com/help/borrowing/liquidations ·
  Aave subgraphs (The Graph) — https://github.com/LeviScoffie/aave-protocol-subgraphs ·
  The Graph pricing (100K gratis/mes) — https://docs.celo.org/developer/indexer/the-graph
- **Score §1:** Mec 4.0 · Lag 3.5 · Fals 4.0 · Costo 2.5 · Nov 4.5 · Ret 3.5 → **ponderado 3.68**

### K4-02 — Post-Liquidation Overshoot Reversion
- **Mecanismo:** Un evento de liquidación grande vende colateral *a mercado sin elasticidad de
  precio* (el liquidador toma el bono y revende rápido). Eso empuja el precio por debajo del
  "valor justo" por minutos-horas; cuando la venta forzada se agota, el precio **rebota**. Es
  el espejo mean-reversion de K4-01 en ventana corta.
- **Lag / persistencia:** El overshoot se corrige en 2–12 h (los arbs reponen liquidez pero no
  instantáneo para tamaños grandes). Persiste porque el tamaño del evento no es observable sin
  parsear los `LiquidationCall`.
- **Señal y horizonte:** Suma de `liquidationCall` (colateral USD) por ventana horaria; cuando
  supera su z-score alto, long el activo colateral a 4–12 h. Horizonte intradía/1 día.
- **Datos:** Eventos `LiquidationCall` del pool Aave V3 (subgraph o logs RPC por topic0). Compound
  v3 `AbsorbCollateral`. Rango ene-2023→hoy. [gratis vía logs RPC público filtrados por topic].
- **Test de refutación:** Buckets de retorno fwd 4/8/12 h por tamaño del evento, no-solapado
  (eventos separados ≥12 h). Placebo con eventos random del mismo tamaño nocional pero fecha
  permutada. Control: ¿el rebote es solo el rebote genérico post-caída? → comparar contra
  caídas de igual magnitud *sin* liquidación concentrada.
- **Diferencia con lo ya probado:** Relacionada con "Iceberg absorption" (#4) en espíritu
  (venta forzada → reversión) pero **fuente distinta** (eventos de liquidación on-chain, no
  tape de order-book) y **horizonte horas, no minutos** → ejecutable por el scheduler. Ninguna
  ronda testeó liquidaciones de lending como gatillo.
- **Fuentes:** Aave V3 `liquidationCall` guía — https://github.com/galacticcouncil/aave-docs-v3/blob/main/guides/liquidations.md ·
  Compound III `absorb` (liquidation) — https://docs.compound.finance/liquidation/
- **Score §1:** Mec 3.5 · Lag 3.0 · Fals 4.0 · Costo 3.0 · Nov 4.0 · Ret 3.0 → **ponderado 3.43**

### K4-03 — Utilization-Spike Borrow-Rate Shock
- **Mecanismo:** Cuando la **utilización** de un mercado de lending cruza el *kink* del modelo
  de interés (p.ej. 80–90%), la tasa de borrow salta de forma convexa y súbita. Eso fuerza a
  los apalancados (loopers de LST, carry de stables) a **desapalancar** → venta de colateral o
  compra de deuda. El kink es un parámetro público; el cruce es observable.
- **Lag / persistencia:** El desapalancamiento no es instantáneo (gas, gestión de posición,
  husos horarios) → drift de horas. No se arbitra porque pocos monitorean utilización por mercado.
- **Señal y horizonte:** Utilización del mercado (p.ej. USDC/USDT en Aave) cruzando hacia el
  tramo convexo + aceleración de la tasa. Horizonte 1–2 días. Dirección: risk-off (short alts
  apalancadas / reducir).
- **Datos:** `reserve.utilizationRate` y curva de interés del subgraph Aave, o `aave-v3-data`
  JSON diario (gratis, sin key, actualizado por GitHub Actions). Rango desde 2023.
- **Test de refutación:** IC continuo de (distancia al kink firmada) vs retorno fwd 1/2d del
  colateral dominante, no-solapado. Placebo permutación. Control por funding (que no sea solo
  co-movimiento con el apalancamiento de derivados #6).
- **Diferencia con lo ya probado:** No es base spot-perp (F3) ni OI-precio (F6). Mide **estrés
  de apalancamiento on-chain** vía tasa de interés, un canal independiente del funding de perps.
- **Fuentes:** Aave rates module (tasas/utilización) — https://aave.com/docs/aave-v3/concepts/liquidity-pool ·
  `th3nolo/aave-v3-data` (JSON diario, sin key) — https://github.com/th3nolo/aave-v3-data
- **Score §1:** Mec 3.5 · Lag 3.0 · Fals 4.0 · Costo 3.5 · Nov 4.0 · Ret 3.0 → **ponderado 3.48**

### K4-04 — Bad-Debt / Insolvency Flag Spillover
- **Mecanismo:** Cuando un mercado de lending acumula **bad debt** (deuda sin colateral tras
  liquidaciones fallidas), hay un riesgo público de socialización de pérdidas o freeze. Los
  tenedores del token de gobernanza del protocolo y de su stable asociada reaccionan con lag.
- **Lag / persistencia:** La bad debt se registra on-chain pero su interpretación tarda (hace
  falta leer reservas vs deuda). Lag de días.
- **Señal y horizonte:** Bad-debt ratio por protocolo (deuda cuyo colateral < deuda) subiendo de
  umbral. Short token de gobernanza / su stable. Horizonte 1–5 días.
- **Datos:** Subgraph Aave/Compound + precios; o dashboards de riesgo públicos (Chaos/Gauntlet
  publican, pero gated). Reconstrucción propia vía subgraph. [gated-lite].
- **Test de refutación:** Event-study alrededor de saltos de bad-debt, no-solapado; placebo con
  fechas random. OOS. Pocos eventos → probablemente **sub-powered**; declararlo.
- **Diferencia con lo ya probado:** Ninguna. Canal de solvencia, no de flujo.
- **Fuentes:** Aave V3 glosario (health factor / reservas) — https://aave.com/docs/resources/glossary
- **Score §1:** Mec 3.5 · Lag 3.5 · Fals 2.5 · Costo 2.5 · Nov 4.0 · Ret 3.0 → **ponderado 3.23**

---

## B. Oráculos (lag de discretización: heartbeat / deviation)

### K4-05 — Oracle-Spot Staleness Gap
- **Mecanismo:** Un feed de Chainlink solo actualiza al cruzar su *deviation threshold* (p.ej.
  0.5% ETH/USD) o al vencer su *heartbeat*. Entre updates, el precio on-chain está **congelado**
  mientras el spot de exchanges se mueve. El *gap* oráculo−spot es una medida pública de cuánta
  realidad todavía no entró a DeFi. Un gap grande implica liquidaciones/arbitrajes inminentes
  cuando el oráculo por fin actualice.
- **Lag / persistencia:** El lag es **el mecanismo literal** del oráculo (segundos a minutos),
  pero su *consecuencia* (ola de liquidaciones al actualizar) tiene drift de minutos-horas.
  Ojo: la parte sub-minuto es research-only; el edge operable es el *estado* "DeFi está
  rezagado y por reaccionar".
- **Señal y horizonte:** |precio_oráculo − precio_spot| / spot, por encima de umbral sostenido.
  Horizonte: 1–4 h (no sub-minuto). Dirección: continuación del lado del spot.
- **Datos:** Eventos `AnswerUpdated` del aggregator Chainlink (RPC público, gratis) + klines spot
  Binance 1m (ya los bajamos). Rango: feeds existen desde 2020+. [gratis].
- **Test de refutación:** IC de gap firmado vs retorno fwd 1/2/4 h del spot, **no-solapado** (una
  obs por episodio de gap, separadas). Placebo permutación. Control crítico: ¿el gap solo
  refleja vol instantánea ya conocida? → parcializar por retorno reciente. Marcar riesgo de que
  sea coincidente (como el peg #2).
- **Diferencia con lo ya probado:** No es peg de stablecoins (#2, info mutua entre pegs). Mide
  el **lag de discretización oráculo vs spot de un activo volátil**, fuente y mecanismo nuevos.
- **Fuentes:** Chainlink historical data (heartbeat/deviation) — https://docs.chain.link/data-feeds/historical-data/ ·
  Chainlink decentralized data model (`AnswerUpdated`) — https://docs.chain.link/architecture-overview/architecture-decentralized-model/
- **Score §1:** Mec 3.5 · Lag 2.5 · Fals 4.0 · Costo 3.5 · Nov 4.0 · Ret 3.0 → **ponderado 3.33**

### K4-06 — Pre-Heartbeat Liquidation Clustering
- **Mecanismo:** Si un feed está cerca de su heartbeat (no actualizó en casi X minutos) y el
  spot se movió, el **próximo update** del oráculo materializa de golpe un salto de precio
  on-chain → cluster de liquidaciones sincronizadas en ese bloque. El tiempo-desde-último-update
  es público y predice *cuándo* viene el salto.
- **Lag / persistencia:** El reloj del heartbeat es determinista; la reacción de liquidaciones es
  de minutos. Edge de régimen: "hay un salto de oráculo pendiente".
- **Señal y horizonte:** (tiempo desde último update / heartbeat) alto × gap grande → prob. de
  cluster de liquidación en la próxima hora. Horizonte 1–2 h.
- **Datos:** `AnswerUpdated` timestamps + heartbeat del feed (público) + spot. [gratis, RPC].
- **Test de refutación:** ¿Los `LiquidationCall` se concentran en bloques inmediatamente
  posteriores a updates de oráculo con gap alto? Test de concentración vs null de Poisson;
  luego retorno fwd. No-solapado. Alto riesgo research-only (minutos).
- **Diferencia con lo ya probado:** Ninguna. Explota el *reloj* del oráculo, no el nivel.
- **Fuentes:** Chainlink data feeds (modelo OCR / heartbeat) — https://docs.chain.link/architecture-overview/architecture-decentralized-model/ ·
  Chainlink historical data — https://docs.chain.link/data-feeds/historical-data/
- **Score §1:** Mec 3.5 · Lag 2.5 · Fals 3.5 · Costo 3.0 · Nov 4.5 · Ret 2.5 → **ponderado 3.23**

### K4-07 — Cross-Oracle Divergence (Chainlink vs Pyth/Redstone)
- **Mecanismo:** Distintos protocolos usan distintos oráculos con *latencias y métodos*
  distintos (Chainlink pull-based lento vs Pyth push de baja latencia). Cuando divergen, hay un
  arbitraje de liquidación entre protocolos y una señal de hacia dónde va el consenso. La
  divergencia es pública en ambos contratos.
- **Lag / persistencia:** Minutos-horas hasta que el feed lento alcanza al rápido. El lento
  "sabe" hacia dónde va (el rápido ya lo marcó).
- **Señal y horizonte:** Precio_Pyth − Precio_Chainlink firmado → continuación del lado rápido en
  el activo. Horizonte 1–4 h.
- **Datos:** Pyth price feeds (API/Hermes, gratis) + Chainlink aggregator (RPC). Rango Pyth desde
  ~2022. [gratis, forward-collect para historia densa de Pyth].
- **Test de refutación:** IC divergencia vs retorno fwd spot, no-solapado, placebo. Control: ¿la
  divergencia solo replica el spot (entonces es redundante con tener el spot)? Comparar aporte
  marginal sobre spot-only.
- **Diferencia con lo ya probado:** Ninguna. Fuente nueva (dos oráculos), mecanismo de latencia
  diferencial.
- **Fuentes:** Pyth Hermes / fetch price updates — https://docs.pyth.network/price-feeds/fetch-price-updates
  (nota: Hermes exige API key desde 2026-08-26) · Chainlink feeds — https://docs.chain.link/data-feeds/
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 3.5 · Costo 2.5 · Nov 4.5 · Ret 3.0 → **ponderado 3.23**

---

## C. LST / LRT (colas de retiro, depeg, redención)

### K4-08 — LST Redemption-Queue Overhang
- **Mecanismo:** Retirar stETH→ETH (Lido) o cualquier LST pasa por una **cola de salida de la
  beacon chain con delay de protocolo** (épocas → horas/días) más la cola interna del protocolo.
  Cuando la cola de retiro se agranda, hay oferta de ETH *contratada a futuro* con fecha de
  protocolo conocida → presión bajista anticipable sobre stETH/ETH y potencialmente ETH.
- **Lag / persistencia:** El delay de la cola es literal y medible (el mecanismo *es* el lag).
  Persiste porque el tamaño agregado de la cola no lo mira el retail de precio.
- **Señal y horizonte:** Tamaño de la cola de retiro de Lido (ETH pendientes) + su derivada,
  z-score. Horizonte 1–5 días. Sesgo: discount stETH/ETH ↑ → oportunidad o señal risk-off.
- **Datos:** Contrato de withdrawals de Lido (eventos `WithdrawalRequested`, RPC/subgraph, gratis),
  o Lido subgraph. Cola de salida de validadores: beacon chain (gated: beaconcha.in pide key;
  proxy vía BigQuery solo ETH). Rango: withdrawals Lido desde Shapella (abr-2023). [gratis-lite].
- **Test de refutación:** IC de tamaño-de-cola firmado vs retorno fwd 1/3/5d de stETH/ETH ratio y
  de ETH, no-solapado. Placebo. Control por funding de ETH. OOS.
- **Diferencia con lo ya probado:** No es "cola de validadores entrada" (§4g L3, entrada
  refutada). Acá es la cola de **salida/redención de LST** (el mecanismo que L3 marcó como el
  verdadero pero no pudo testear por falta de key) — ruta alternativa vía eventos de Lido que
  **no** requieren beacon chain. Diferencia de fuente y de lado de la cola.
- **Fuentes:** Lido WithdrawalQueueERC721 — https://docs.lido.fi/contracts/withdrawal-queue-erc721/ ·
  Lido withdrawals (FIFO, 1–5 días) — https://lido.fi/how-lido-works/withdrawals · §4g (L3 declaró esta cola como la pendiente).
- **Score §1:** Mec 4.0 · Lag 4.0 · Fals 3.5 · Costo 3.0 · Nov 4.0 · Ret 3.0 → **ponderado 3.68**

### K4-09 — LST Depeg → Looping Unwind
- **Mecanismo:** Las posiciones "looped" (stETH colateral → pedir ETH → comprar más stETH) son
  enormes en Aave. Un depeg de stETH/ETH baja el HF de todos los loopers a la vez → desapalanca-
  miento forzado → más venta de stETH → espiral. El depeg y el stock de loops son públicos.
- **Lag / persistencia:** El unwind es reflexivo pero no instantáneo (gestión de posición, gas).
  Drift de horas. El stock de loops agregado no lo mira el retail.
- **Señal y horizonte:** (discount stETH/ETH) × (stETH depositado en Aave usado como colateral
  con deuda ETH) → riesgo de cascada. Horizonte 4–24 h. Short stETH/ETH ratio.
- **Datos:** stETH/ETH pool price (Curve, subgraph/RPC) + posiciones Aave (subgraph). Rango 2023+.
  [gated-lite].
- **Test de refutación:** Event-study del ratio fwd condicionado a (depeg × loop-stock),
  no-solapado, placebo. Control: ¿es solo momentum del depeg? comparar vs depeg sin loop-stock alto.
- **Diferencia con lo ya probado:** Combina K4-01 (HF) con el canal LST específico; ninguna ronda
  lo midió. No es peg de *stablecoins* (#2).
- **Fuentes:** stETH/ETH ratio on-chain (Chainlink feed stETH/ETH, mismo mecanismo de feeds) — https://docs.chain.link/data-feeds/price-feeds/historical-data/ ·
  Aave posiciones (subgraph) — https://github.com/LeviScoffie/aave-protocol-subgraphs
  (pool stETH de Curve: sin URL de subgraph verificada; leer el contrato del pool por RPC).
- **Score §1:** Mec 4.0 · Lag 3.5 · Fals 3.5 · Costo 2.5 · Nov 4.0 · Ret 3.5 → **ponderado 3.55**

### K4-10 — LST Rebase-Day Flow
- **Mecanismo:** Algunos LST/entornos distribuyen rewards en un ciclo (rebase diario de stETH,
  epochs de rewards). Alrededor del rebase hay flujos predecibles (reinversión, claims). Reloj
  de protocolo conocido.
- **Lag / persistencia:** Ciclo fijo → estacionalidad. Edge chico si existe.
- **Señal y horizonte:** Retorno condicionado a la fase del ciclo de rebase/rewards. Horizonte 1 día.
- **Datos:** Timestamps de rebase (on-chain, gratis). Rango 2023+.
- **Test de refutación:** Buckets por fase del ciclo con **control de día-de-semana** (clave:
  no confundir con efecto calendario), placebo permutando fases, no-solapado. Alto riesgo de
  null (como "00:00 UTC" §4b que murió por control).
- **Diferencia con lo ya probado:** No es el impulso 00:00 UTC (§4b, refutado). Reloj de
  protocolo, no reloj de pared.
- **Fuentes:** Lido contratos (rebase / stETH) — https://docs.lido.fi/contracts/lido/
- **Score §1:** Mec 2.5 · Lag 2.5 · Fals 4.0 · Costo 3.5 · Nov 3.5 · Ret 2.0 → **ponderado 2.90**

### K4-11 — LRT Points-Program Cliff
- **Mecanismo:** Los LRT (EigenLayer restaking: ether.fi, Renzo, Kelp) corrieron con "points"
  especulativos. Cuando termina una temporada de points o cambia el reward, el capital
  mercenario sale → venta del LRT y del subyacente. Las fechas/condiciones son públicas (anuncios).
- **Lag / persistencia:** La salida no es instantánea (cola de retiro del LRT + decisión). Días.
- **Señal y horizonte:** Evento de fin-de-temporada / recorte de incentivos → short LRT vs ETH.
  Horizonte 1–7 días.
- **Datos:** Fechas de programas (anuncios públicos, forward-collect) + precios LRT (DEX/CEX).
  Rango: LRT líquidos desde 2024. [forward-collect; pocos eventos → sub-powered].
- **Test de refutación:** Event-study CAR del LRT vs ETH alrededor de los cliffs, placebo con
  fechas random, no-solapado. Declarar sub-powered (pocos eventos).
- **Diferencia con lo ya probado:** No es unlock de vesting (F4) — es fin de *incentivo de
  liquidez*, oferta mercenaria endógena. Fuente distinta.
- **Fuentes:** EigenLayer/ether.fi/Renzo: sin URL única verificada (programas de points comunicados por anuncios puntuales);
  fechas a recolectar de los anuncios oficiales de cada protocolo al momento del evento → forward-collect. Sin fuente histórica verificable.
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 2.5 · Costo 2.5 · Nov 4.0 · Ret 3.0 → **ponderado 3.03**

---

## D. Bridges (finality / challenge window / net-flow)

### K4-12 — Canonical-Bridge Net-Flow Lead
- **Mecanismo:** El puente canónico de un L2 (Arbitrum/Optimism/Base) tiene **ventanas de
  finality fijas** (depósitos ~minutos; retiros ~7 días en optimistic rollups por el challenge
  window). El *net-flow* de ETH entrando por el bridge es capital que llega a operar en el L2 con
  lag conocido → demanda anticipable de tokens del ecosistema L2.
- **Lag / persistencia:** El reloj del bridge es duro (7d retiro). Los depósitos tienen lag de
  "intención → acción" de horas. El net-flow agregado no lo mira el retail.
- **Señal y horizonte:** Net-flow de ETH/stables al bridge canónico (depósitos − retiros), z-score.
  Horizonte 1–3 días. Long canasta de tokens del L2 (ARB/OP) cuando entra capital.
- **Datos:** Eventos de depósito/retiro de los contratos de bridge (RPC público / BigQuery
  `crypto_ethereum`, gratis con GCP sandbox) + klines ARB/OP/BTC. Rango 2021+ (Arbitrum/Optimism).
  [gratis con sandbox GCP].
- **Test de refutación:** IC net-flow firmado vs retorno fwd 1/2/3d de (canasta L2 − BTC),
  no-solapado, placebo. Control por funding y por blob-fee (que no sea redundante con #6-blob,
  que ya se refutó).
- **Diferencia con lo ya probado:** No es blob-fee KL (#6/§4b, refutado: medía *actividad* de
  rollups vía fee). Acá mide **flujo de capital por el bridge** (oferta/demanda real de ETH en el
  L2), fuente y mecanismo distintos. No es whale-netflow de exchanges (§4b).
- **Fuentes:** Arbitrum bridge / challenge period (~6.4 días) — https://docs.arbitrum.io/build-decentralized-apps/bridging/withdraw/tokens ·
  Optimism bridging cross-domain (challenge 7 días) — https://docs.optimism.io/op-stack/bridging/cross-domain ·
  BigQuery `crypto_ethereum` (público) — https://cloud.google.com/blog/products/data-analytics/ethereum-bigquery-public-dataset-smart-contract-analytics/
- **Score §1:** Mec 3.5 · Lag 3.5 · Fals 3.5 · Costo 2.5 · Nov 4.0 · Ret 3.0 → **ponderado 3.40**

### K4-13 — Withdrawal-Queue Release (optimistic challenge window)
- **Mecanismo:** En optimistic rollups los retiros se "liberan" **7 días exactos** después de
  iniciados. La cola de retiros iniciados es pública → hay un calendario endógeno de ETH que
  *volverá* a L1 en fecha conocida. Un pico de retiros iniciados predice oferta de ETH/venta de
  tokens L2 a +7d.
- **Lag / persistencia:** Lag de protocolo exacto (7d). Nadie construye el calendario agregado.
- **Señal y horizonte:** Volumen de retiros iniciados hoy → evento a +7d. Horizonte: ventana
  alrededor de T+7d.
- **Datos:** Eventos de inicio de retiro del bridge L2 (RPC/BigQuery). Rango 2021+. [gratis-lite].
- **Test de refutación:** Event-study en T+7d condicionado al tamaño de la cola, placebo con lag
  falso (T+5d, T+9d) para probar que el efecto está *específicamente* en el día de liberación,
  no-solapado.
- **Diferencia con lo ya probado:** Ninguna. El placebo de "lag falso" es un test único que
  explota la precisión del reloj de 7d (no disponible en ideas de calendario blando como F4).
- **Fuentes:** Optimism withdrawal flow (challenge 7 días) — https://docs.optimism.io/op-stack/bridging/withdrawal-flow ·
  Arbitrum withdraw a parent chain (~6.4 días) — https://docs.arbitrum.io/build-decentralized-apps/bridging/withdraw/tokens
- **Score §1:** Mec 3.5 · Lag 4.0 · Fals 4.0 · Costo 2.5 · Nov 4.5 · Ret 2.5 → **ponderado 3.50**

### K4-14 — Bridge-Halt / Pause Risk-Off
- **Mecanismo:** Cuando un bridge se **pausa** (upgrade, incidente, guardian) el capital queda
  atrapado temporalmente → risk-off en los tokens de ese ecosistema hasta que reabre. El estado
  pause/unpause es público on-chain.
- **Lag / persistencia:** La reacción de precio tarda en difundirse (no todos monitorean el
  estado del contrato). Horas.
- **Señal y horizonte:** Transición a estado `paused` del bridge → short tokens del ecosistema;
  `unpaused` → posible rebote. Horizonte 1–3 días.
- **Datos:** Eventos `Paused`/`Unpaused` de los contratos de bridge (RPC, gratis). Pocos eventos.
- **Test de refutación:** Event-study, placebo fechas random, no-solapado. **Sub-powered** (raro) →
  declararlo; sirve más como regla de riesgo que como alpha estadístico.
- **Diferencia con lo ya probado:** Ninguna. Canal de estado-de-infra, distinto a status pages
  (esa es familia K2).
- **Fuentes:** Optimism OptimismPortal / pause de seguridad (fault-proofs) — https://docs.optimism.io/op-stack/fault-proofs/fp-security
  (eventos `Paused`/`Unpaused` legibles por RPC del contrato del bridge).
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 2.5 · Costo 3.0 · Nov 4.0 · Ret 2.5 → **ponderado 3.03**

### K4-15 — Cross-Chain Stablecoin Mint/Burn Imbalance
- **Mecanismo:** Los bridges de stablecoins (CCTP de Circle, etc.) emiten/queman USDC al cruzar
  cadenas. Un desbalance (mucho USDC acuñándose en un L2) indica **capital fresco entrando a
  especular ahí** con lag de horas antes de que compre tokens.
- **Lag / persistencia:** El mint es instantáneo; su *despliegue* en compras tarda horas. No lo
  mira el retail por-cadena.
- **Señal y horizonte:** Mint neto de USDC/USDT en un L2 vía CCTP/bridge, z-score. Horizonte
  1–2 días. Long tokens del L2.
- **Datos:** Eventos de mint/burn de USDC por cadena (RPC/BigQuery, gratis). Rango CCTP desde 2023.
- **Test de refutación:** IC mint-neto vs retorno fwd de canasta del L2, no-solapado, placebo,
  control por net-flow del bridge canónico (K4-12) para aislar el canal stable.
- **Diferencia con lo ya probado:** No es "stablecoin supply flow → BTC" (§4d, débil/null a nivel
  agregado global). Acá es **por-cadena/por-L2** y direccional al ecosistema local, no al BTC
  global → mecanismo y granularidad distintos.
- **Fuentes:** Circle CCTP (burn-and-mint de USDC por cadena) — https://developers.circle.com/cctp ·
  guía técnica CCTP — https://developers.circle.com/cctp/references/technical-guide
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 3.5 · Costo 2.5 · Nov 3.5 · Ret 3.0 → **ponderado 3.05**

---

## E. L2 / infraestructura (sequencer, fees, gas base)

### K4-16 — Sequencer-Downtime Dislocation
- **Mecanismo:** Si el **sequencer** de un L2 se cae, no se procesan trades en los DEX de ese L2;
  cuando vuelve, hay una dislocación de precios (el L2 está "congelado" vs el mercado global) que
  se cierra con un salto. El estado del sequencer (y su feed de uptime Chainlink) es público.
- **Lag / persistencia:** El reajuste al volver es de minutos (research-only) pero el *riesgo
  acumulado* durante el downtime es un edge de régimen de horas.
- **Señal y horizonte:** Feed de uptime del sequencer (Chainlink L2 Sequencer Uptime) = down +
  duración → al reabrir, continuación del movimiento global perdido. Horizonte minutos-horas.
- **Datos:** Chainlink Sequencer Uptime Feed (RPC, gratis) + precios. Rango 2022+. Pocos eventos.
- **Test de refutación:** Event-study al `unpause` del sequencer, placebo, no-solapado.
  Sub-powered (raro). Marcar research-only para la parte sub-minuto.
- **Diferencia con lo ya probado:** Ninguna. Infra-L2 específica.
- **Fuentes:** Chainlink L2 Sequencer Uptime Feeds — https://docs.chain.link/data-feeds/l2-sequencer-feeds/
- **Score §1:** Mec 3.0 · Lag 2.5 · Fals 3.0 · Costo 3.0 · Nov 4.0 · Ret 2.5 → **ponderado 3.00**

### K4-17 — L1 Base-Fee Regime → Risk Appetite
- **Mecanismo:** El `baseFee` de Ethereum (EIP-1559) es un termómetro **público y de alta
  frecuencia** de demanda de blockspace = actividad especulativa on-chain (mints, swaps,
  airdrops). Un régimen sostenido de base-fee alto marca risk-on retail; su colapso, risk-off.
  Desacoplado del fee de blobs (que ya se refutó).
- **Lag / persistencia:** La demanda de blockspace lidera el precio de alts de horas a 1 día
  (la actividad precede a la apreciación).
- **Señal y horizonte:** Media/mediana diaria de baseFee, z-score 30d. Horizonte 1–2 días. Long
  canasta de alts cuando el régimen de fee sube.
- **Datos:** `baseFeePerGas` por bloque (RPC público / BigQuery, gratis). Rango post-Londres
  (ago-2021). [gratis].
- **Test de refutación:** IC de régimen-de-fee vs retorno fwd de (canasta alts − BTC),
  no-solapado, placebo. Control: ¿es solo un proxy de vol/volumen ya conocido? parcializar por
  volumen de CEX. OOS.
- **Diferencia con lo ya probado:** No es blob-fee KL (#6, refutado) — el blob-fee se desacopló
  del gas de ejecución justamente; acá uso el **base-fee de ejecución**, el canal que el
  blob-fee *dejó de medir*. Mecanismo y fuente distintos.
- **Fuentes:** EIP-1559 (fuente de EIPs) — https://eips.ethereum.org ·
  BigQuery `crypto_ethereum` blocks (`base_fee_per_gas`) — https://cloud.google.com/blog/products/data-analytics/ethereum-bigquery-how-we-built-dataset
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 4.0 · Costo 3.5 · Nov 3.0 · Ret 3.0 → **ponderado 3.23**

### K4-18 — Gas-Price Percentile Capitulation
- **Mecanismo:** Un **colapso** del gas (percentil muy bajo sostenido) marca capitulación/apatía
  on-chain — históricamente cerca de suelos locales (nadie transacciona → mínimo de interés).
  Señal contrarian de mediano plazo.
- **Lag / persistencia:** El sentimiento tarda en girar; días.
- **Señal y horizonte:** baseFee en su decil bajo durante N días → sesgo long BTC/ETH. Horizonte
  3–7 días.
- **Datos:** baseFee histórico (BigQuery/RPC, gratis). Rango 2021+.
- **Test de refutación:** IC de percentil-bajo vs retorno fwd 3/5/7d, no-solapado, placebo.
  Riesgo: coincidente con precio bajo (parcializar por drawdown reciente). OOS.
- **Diferencia con lo ya probado:** Ángulo contrarian del régimen de fee (complementa K4-17 por
  el lado bajo). No testeado antes.
- **Fuentes:** BigQuery `crypto_ethereum` (dataset público) — https://cloud.google.com/blog/products/data-analytics/ethereum-bigquery-public-dataset-smart-contract-analytics/ ·
  queries de ejemplo — https://github.com/blockchain-etl/awesome-bigquery-views
- **Score §1:** Mec 2.5 · Lag 3.0 · Fals 4.0 · Costo 3.5 · Nov 3.0 · Ret 2.5 → **ponderado 3.03**

### K4-19 — DEX-Pool Reserve-Imbalance Pre-Move
- **Mecanismo:** En un AMM (Uniswap v3), un **desbalance creciente de reservas** en una pool
  profunda (p.ej. ETH/USDC) refleja flujo direccional neto de informados que todavía no se
  trasladó al CEX. El desbalance es público (estado del contrato).
- **Lag / persistencia:** El arbitraje DEX↔CEX es rápido pero el *flujo acumulado* firma una
  dirección que persiste horas.
- **Señal y horizonte:** Cambio neto de reservas (o del balance del pool) firmado, z-score.
  Horizonte 1–6 h. Continuación.
- **Datos:** Eventos `Swap`/estado de pools Uniswap v3 (subgraph, free-tier / BigQuery). Rango 2021+.
  [gated-lite].
- **Test de refutación:** IC flujo-neto firmado vs retorno fwd 1/4/6 h CEX, no-solapado, placebo,
  control por volumen CEX. Riesgo de que sea coincidente (arbitrado).
- **Diferencia con lo ya probado:** No es order-book CEX (QLEC/#3 etc., todos HFT). Mide **flujo
  on-chain en AMM** a horizonte horas. Fuente distinta.
- **Fuentes:** Uniswap v3 subgraph (entidades/queries) — https://docs.uniswap.org/api/subgraph/overview ·
  ejemplos de query v3 — https://docs.uniswap.org/api/subgraph/guides/v3-examples
- **Score §1:** Mec 3.0 · Lag 2.5 · Fals 3.5 · Costo 2.5 · Nov 3.5 · Ret 3.0 → **ponderado 2.98**

---

## F. Mercados monetarios cripto-nativos (tasas, carry, CDP)

### K4-20 — On-Chain Funding vs CEX-Perp Funding Spread
- **Mecanismo:** El "funding" implícito del apalancamiento on-chain (tasa de borrow de stables en
  Aave, usada para loops long) vs el funding de perps CEX. Cuando divergen, hay un canal de
  apalancamiento barato que el otro no refleja → predice hacia dónde migra el apalancamiento.
- **Lag / persistencia:** La migración de apalancamiento entre venues tarda horas-días.
- **Señal y horizonte:** (borrow-rate Aave anualizada − funding perp) firmado. Horizonte 1–3 días.
- **Datos:** Aave rates (`aave-v3-data` JSON gratis) + funding perp (Binance/Bybit, gratis, ya
  bajado para #6). Rango 2023+. [gratis].
- **Test de refutación:** IC del spread vs retorno fwd, no-solapado, placebo, **control por #6
  (funding dispersion)** para aislar el canal on-chain. OOS.
- **Diferencia con lo ya probado:** #6 usa solo funding de perps. Acá agrego el **apalancamiento
  on-chain** como segundo canal → aporte marginal sobre #6 es la pregunta explícita del test.
- **Fuentes:** Aave rates / liquidity pool — https://aave.com/docs/aave-v3/concepts/liquidity-pool ·
  `aave-v3-data` JSON — https://github.com/th3nolo/aave-v3-data · §5 (#6 funding dispersion).
- **Score §1:** Mec 3.5 · Lag 3.0 · Fals 4.0 · Costo 4.0 · Nov 3.5 · Ret 3.0 → **ponderado 3.50**

### K4-21 — DAI/sDAI Savings-Rate (DSR) Regime
- **Mecanismo:** La **DSR** de MakerDAO/Sky es una tasa libre de riesgo cripto-nativa fijada por
  gobernanza. Subidas de DSR atraen capital a sDAI (sale de activos de riesgo); bajadas lo
  expulsan a buscar yield en riesgo. Los cambios son públicos (votaciones/ejecución).
- **Lag / persistencia:** El rebalanceo hacia/desde riesgo tarda días.
- **Señal y horizonte:** Cambio de DSR firmado → risk-off (sube) / risk-on (baja). Horizonte
  2–7 días.
- **Datos:** Parámetro DSR on-chain + fechas de cambio (RPC/foros Sky, gratis). Rango 2023+ (DSR
  revivió). Pocos cambios → sub-powered.
- **Test de refutación:** Event-study alrededor de cambios de DSR, placebo fechas random,
  no-solapado. Declarar sub-powered.
- **Diferencia con lo ya probado:** No es RWA/T-bill rotation (§4c, AUM de treasuries). Acá es la
  **tasa de política** cripto-nativa, no el flujo de AUM. Mecanismo distinto (precio del dinero vs
  stock).
- **Fuentes:** MakerDAO Pot / DSR (rates module) — https://docs.makerdao.com/smart-contract-modules/rates-module/pot-detailed-documentation
- **Score §1:** Mec 3.0 · Lag 3.5 · Fals 3.0 · Costo 3.5 · Nov 3.5 · Ret 2.5 → **ponderado 3.18**

### K4-22 — CDP Stability-Fee Shock → Collateral Pressure
- **Mecanismo:** Cuando MakerDAO/Sky sube la **stability fee** de un colateral (p.ej. ETH), los
  vault owners cierran posiciones (repagan deuda vendiendo colateral) → presión bajista sobre ese
  colateral. El cambio de fee es público.
- **Lag / persistencia:** El cierre de vaults tarda días (no todos reaccionan al instante).
- **Señal y horizonte:** Subida de stability fee del colateral → short ese colateral. Horizonte
  2–5 días.
- **Datos:** Parámetros de vaults Maker/Sky (RPC, gratis) + precios. Rango 2023+. Pocos eventos.
- **Test de refutación:** Event-study, placebo, no-solapado. Sub-powered.
- **Diferencia con lo ya probado:** Ninguna. Canal CDP específico.
- **Fuentes:** Sky Savings Rate / DSR (rates module de Maker) — https://docs.makerdao.com/smart-contract-modules/rates-module
  (stability fee por colateral: mismo módulo de rates).
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 2.5 · Costo 3.0 · Nov 3.5 · Ret 2.5 → **ponderado 2.93**

### K4-23 — Perp-DEX Open-Interest Cap Proximity (GMX/Hyperliquid)
- **Mecanismo:** Los perps en DEX tienen **caps de OI por activo** y pools de liquidez finitos
  (GLP/HLP). Cuando el OI long se acerca al cap, el apalancamiento nuevo se frena y el carry se
  encarece → techo mecánico al rally de ese activo. El OI y el cap son públicos.
- **Lag / persistencia:** El efecto techo actúa en horas-1 día mientras el OI está pegado al cap.
- **Señal y horizonte:** (OI / cap) alto + skew long → sesgo mean-reversion/short del activo.
  Horizonte 1–2 días.
- **Datos:** GMX/Hyperliquid API pública (OI, caps, gratis sin key). Rango GMX 2022+, HL 2023+.
  [gratis / forward-collect para historia densa].
- **Test de refutación:** IC de proximidad-al-cap firmada vs retorno fwd, no-solapado, placebo,
  control por funding CEX. OOS.
- **Diferencia con lo ya probado:** No es Hyperliquid smart-money mirror (§4g L7, copiar wallets).
  Acá es la **restricción estructural de capacidad** del venue (cap de OI), no el skill de
  traders. Mecanismo y dato distintos.
- **Fuentes:** GMX docs (OI limitado por el pool GM) — https://docs.gmx.io/docs/intro/ ·
  Hyperliquid API (meta: markers de OI cap) — https://app.hyperliquid.xyz/API
- **Score §1:** Mec 3.5 · Lag 3.0 · Fals 3.5 · Costo 3.0 · Nov 4.0 · Ret 3.0 → **ponderado 3.38**

---

## G. Gobernanza / parámetros con efecto de mercado

### K4-24 — Risk-Parameter-Change Front-Run (public governance)
- **Mecanismo:** Los cambios de parámetros de riesgo en Aave/Compound (subir LTV, bajar
  liquidation threshold, cambiar caps) se **anuncian y votan públicamente antes de ejecutarse**
  (timelock). Bajar el liquidation threshold de un colateral fuerza desapalancamiento cuando
  ejecuta → venta anticipable. La fecha de ejecución del timelock es pública y exacta.
- **Lag / persistencia:** El timelock da un lag conocido (horas-días) entre voto y ejecución; el
  mercado no suele leer la cola de ejecución.
- **Señal y horizonte:** Propuesta ejecutable que endurece parámetros de un colateral → short ese
  colateral alrededor de la ejecución del timelock. Horizonte: ventana de ejecución ±2d.
- **Datos:** Aave/Compound governance on-chain (propuestas, timelock queue; subgraph/RPC, gratis)
  + snapshot/foros. Rango 2021+. [gratis].
- **Test de refutación:** Event-study CAR del colateral alrededor de la ejecución, placebo con
  propuestas *no* relacionadas a riesgo (control), no-solapado. Sub-powered posible.
- **Diferencia con lo ya probado:** Es "gobernanza" pero **on-chain con timelock exacto** y efecto
  de liquidación mecánico, no un anuncio blando (esa familia genérica es K2). El placebo con
  propuestas no-riesgo es específico de K4.
- **Fuentes:** Aave governance — https://aave.com/docs/aave-v3/overview ·
  Compound III governance — https://docs.compound.finance/governance/
- **Score §1:** Mec 3.5 · Lag 3.5 · Fals 3.0 · Costo 3.0 · Nov 4.0 · Ret 2.5 → **ponderado 3.33**

### K4-25 — Collateral-Onboarding Demand Pull
- **Mecanismo:** Cuando un lending blue-chip (Aave) **onboarda un colateral nuevo** (p.ej. un LST
  o RWA), se habilita apalancamiento sobre él → demanda de compra para loopear → apreciación con
  lag. El onboarding es público (propuesta ejecutada).
- **Lag / persistencia:** La construcción de posiciones apalancadas tarde días en madurar.
- **Señal y horizonte:** Fecha de ejecución del onboarding → long el activo onboardado. Horizonte
  1–7 días.
- **Datos:** Governance Aave (ejecución de `listReserve`) + precio del activo. Rango 2021+. Pocos
  eventos → sub-powered.
- **Test de refutación:** Event-study CAR, placebo con activos comparables no onboardados,
  no-solapado. Declarar sub-powered.
- **Diferencia con lo ya probado:** Espejo demanda de K4-24 (oferta). Ninguna ronda lo midió.
- **Fuentes:** Aave V3 liquidity pool / listing de reservas por gobernanza — https://aave.com/docs/aave-v3/concepts/liquidity-pool
- **Score §1:** Mec 3.0 · Lag 3.0 · Fals 2.5 · Costo 3.0 · Nov 3.5 · Ret 2.5 → **ponderado 2.93**

---

## Tabla resumen

| id | Nombre | Score | Datos (ruta / costo) | Fit bot |
|---|---|---|---|---|
| K4-01 | Lending Liquidation Cascade Proximity | 3.68 | Aave subgraph free-tier (HF por usuario) | ✅ alto (1–3d) |
| K4-02 | Post-Liquidation Overshoot Reversion | 3.43 | `LiquidationCall` logs RPC (gratis) | ⚠️ medio (4–12h) |
| K4-03 | Utilization-Spike Borrow-Rate Shock | 3.48 | `aave-v3-data` JSON diario (gratis) | ✅ alto (1–2d) |
| K4-04 | Bad-Debt Insolvency Spillover | 3.23 | Aave/Compound subgraph (gated-lite) | ⚠️ sub-powered |
| K4-05 | Oracle-Spot Staleness Gap | 3.33 | Chainlink `AnswerUpdated` RPC + spot (gratis) | ⚠️ medio (1–4h) |
| K4-06 | Pre-Heartbeat Liquidation Clustering | 3.23 | Chainlink timestamps + liq. events (gratis) | ⛔ research-only (min) |
| K4-07 | Cross-Oracle Divergence (CL vs Pyth) | 3.23 | Pyth Hermes + Chainlink (gratis/fwd-collect) | ⚠️ medio (1–4h) |
| K4-08 | LST Redemption-Queue Overhang | 3.68 | Lido withdrawals events RPC/subgraph (gratis-lite) | ✅ alto (1–5d) |
| K4-09 | LST Depeg → Looping Unwind | 3.55 | Curve stETH + Aave posiciones (gated-lite) | ✅ alto (4–24h) |
| K4-10 | LST Rebase-Day Flow | 2.90 | Rebase timestamps on-chain (gratis) | ⚠️ edge chico |
| K4-11 | LRT Points-Program Cliff | 3.03 | Anuncios + precios (forward-collect) | ⚠️ sub-powered |
| K4-12 | Canonical-Bridge Net-Flow Lead | 3.40 | Bridge events RPC/BigQuery (gratis+sandbox) | ✅ alto (1–3d) |
| K4-13 | Withdrawal-Queue Release (7d) | 3.50 | Bridge withdrawal-init events (gratis-lite) | ✅ alto (T+7d) |
| K4-14 | Bridge-Halt Risk-Off | 3.03 | `Paused`/`Unpaused` events (gratis) | ⚠️ sub-powered |
| K4-15 | Cross-Chain Stablecoin Mint/Burn | 3.05 | CCTP mint/burn por cadena (gratis/BigQuery) | ✅ alto (1–2d) |
| K4-16 | Sequencer-Downtime Dislocation | 3.00 | Chainlink Sequencer Uptime feed (gratis) | ⛔ research-only |
| K4-17 | L1 Base-Fee Regime → Risk | 3.23 | `baseFeePerGas` RPC/BigQuery (gratis) | ✅ alto (1–2d) |
| K4-18 | Gas-Price Percentile Capitulation | 3.03 | baseFee histórico (gratis) | ✅ alto (3–7d) |
| K4-19 | DEX-Pool Reserve-Imbalance Pre-Move | 2.98 | Uniswap v3 subgraph (gated-lite) | ⚠️ medio (1–6h) |
| K4-20 | On-Chain vs CEX-Perp Funding Spread | 3.50 | Aave rates + funding perp (gratis, ya bajado) | ✅ alto (1–3d) |
| K4-21 | DAI/sDAI Savings-Rate (DSR) Regime | 3.18 | DSR on-chain + fechas (gratis) | ⚠️ sub-powered |
| K4-22 | CDP Stability-Fee Shock | 2.93 | Maker/Sky vault params (gratis) | ⚠️ sub-powered |
| K4-23 | Perp-DEX OI-Cap Proximity | 3.38 | GMX/Hyperliquid API (gratis/fwd-collect) | ✅ alto (1–2d) |
| K4-24 | Risk-Parameter-Change Front-Run | 3.33 | Aave/Compound gov + timelock (gratis) | ✅ medio (±2d) |
| K4-25 | Collateral-Onboarding Demand Pull | 2.93 | Aave gov asset-listings (gratis) | ⚠️ sub-powered |

**Lectura de K4 (para el revisor / convergencia).** Las candidatas más fuertes son las que
combinan **reloj de protocolo duro + oferta/demanda forzada endógena al precio + data gratis o
cuasi-gratis**: K4-01 (distribución de HF), K4-08 (cola de redención LST), K4-20 (funding
on-chain vs perp, aporte marginal sobre #6), K4-13 (liberación a 7d con placebo de lag falso) y
K4-12/K4-03 (flujo de bridge / shock de utilización). Encajan con el insight meta de
`signal-hypotheses.md` (§4d/§4g): sobrevive el **posicionamiento/apalancamiento forzado**, no la
contabilidad de oferta blanda. Riesgos transversales declarados: (a) varias dependen de subgraph
free-tier o GCP sandbox (datos gated-lite); (b) los eventos de gobernanza/bridge-halt/CDP son
**sub-powered** (pocos eventos) → sirven más como reglas de riesgo que como alpha estadístico;
(c) oráculo/sequencer tienen una pata sub-minuto marcada **research-only** (no la ejecuta el
scheduler). Todas traen test no-solapado + placebo/permutación desde la ficha para evitar el
espejismo de ventanas solapadas que mató candidatas en rondas previas.

**Total: 25 ideas (K4-01 … K4-25).**
