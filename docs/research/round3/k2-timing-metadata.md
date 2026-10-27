# K2 — Timing / metadata pública (Ronda 3)

> Sesión K2 · Familia: señales derivadas de **metadata pública y timing de eventos**
> (listings/delistings, mantenimientos de exchange, status pages, actividad de GitHub,
> gobernanza on-chain, anuncios oficiales, calendarios de infra).
> Línea roja respetada: **solo datos públicos/observables**. Nada de insider/MNPI, nada de
> acceso no autorizado, nada de explotar vulnerabilidades, nada de MEV/sandwich contra
> usuarios. "Hack" = leer info pública de forma astuta.
>
> Antes de leer: cruzar con `signal-hypotheses.md`. En §4g ya se tocó la familia
> "grey-hat/timing" y se concluyó que **listing-leak, cert-transparency y mempool
> whale-deposit no tienen historia retro → forward-collection**. Las fichas de abajo
> evitan reempaquetar esas tres: cuando una idea toca un tema vecino, lo dice explícito
> y cambia **mecanismo o fuente**. Varias de las ideas aquí son retro-testeables con
> archivos públicos que SÍ existen (el eje donde §4g se quedó corto).

---

## Nota metodológica común a toda la familia

El riesgo #1 de esta familia es **supervivencia de datos**: los anuncios/status/listings
son eventos, y muchos agregadores solo guardan el snapshot actual. Cada ficha marca la
ruta de datos como **[gratis | gated | forward-collect]** y, cuando el histórico existe,
nombra el archivo concreto (Wayback Machine, dumps de GitHub Archive, repos de gobernanza,
CSV de delistings, etc.). El riesgo #2 es **confundir el evento con su reacción**: casi
todas estas señales son *event-studies* con ventana [−k, +m] alrededor de un timestamp, de
modo que el test de refutación estándar es: CAR con placebo de fechas aleatorias +
muestras NO-solapadas + OOS por mitades. Lo escribo una vez acá para no repetirlo en cada
ficha.

---

### K2-01 — Delisting Forced-Exit Drift
- **Mecanismo:** cuando un exchange grande (Binance/Coinbase/Upbit) anuncia la **baja** de
  un par, los tenedores tienen una fecha límite para salir y los market-makers retiran
  liquidez anticipadamente. La presión de venta es *forzada y datada*, no informacional:
  todos los que usaban ese venue como salida principal deben liquidar antes del corte.
- **Lag / persistencia:** el anuncio precede a la baja efectiva por días/semanas; el drift
  se sostiene porque la salida es mecánica (no se puede arbitrar comprando algo que va a
  perder su venue de liquidez principal).
- **Señal y horizonte:** short del token desde el anuncio hasta ~T+1 día post-baja;
  horizonte días. Dispara con el timestamp del anuncio de delisting.
- **Datos:** páginas de anuncios oficiales (binance.com/support/announcement/list,
  Coinbase blog, Upbit notices). Histórico retro vía **Wayback Machine** de esas páginas +
  changelog de pares en `data.binance.vision` (cuándo desaparece un símbolo). Rango
  2019→hoy. [gratis] (reconstrucción con esfuerzo medio).
- **Test de refutación:** event-study CAR [−5d, +2d] del token vs BTC; placebo con fechas
  aleatorias del mismo token; no-solapado; OOS pre/post-2023.
- **Diferencia con lo ya probado:** §4g tocó *listing-leak* (entrada, forward-collect). Esto
  es el lado **opuesto y datable** — la SALIDA forzada de delistings, con historia
  reconstruible vía los pares que desaparecen del dump de Binance. Mecanismo y dirección
  distintos.
- **Fuentes:** https://www.binance.com/en/support/announcement/list/161 (delistings);
  https://data.binance.vision/ (desaparición de símbolos).
- **Score §1:** Mecanismo 4 · Lag 4 · Falsabilidad 4 · Costo 3 · Novedad 3 · Retorno 3 → **ponderado 3.6**

### K2-02 — Listing "Teaser-to-Trade" Gap
- **Mecanismo:** varios exchanges publican el anuncio de un listing **con horas de
  antelación** a la apertura de trading. No hay MNPI: el anuncio es público. El edge no es
  "enterarse antes", es que entre el anuncio y la apertura el token cotiza en OTROS venues
  que ya lo tenían, y esos reaccionan con lag al flujo esperado del venue grande.
- **Lag / persistencia:** la ventana anuncio→apertura (típ. 1–24h) es un lag estructural
  publicado. Persiste porque el retail que sigue el venue grande no puede comprar hasta la
  apertura, pero el precio en venues preexistentes ya empieza a moverse.
- **Señal y horizonte:** long del token en el venue preexistente desde el timestamp del
  anuncio hasta la apertura en el venue grande; horizonte horas.
- **Datos:** feed de anuncios (mismas páginas que K2-01) con su timestamp exacto; klines
  del token en el venue donde ya cotizaba (p.ej. ya está en Gate/MEXC y lo lista Binance).
  [gratis / parcialmente forward-collect] — el timestamp exacto del anuncio se preserva mal
  retro, requiere Wayback + cross-check de posts.
- **Test de refutación:** retorno anuncio→apertura vs control de ventana equivalente sin
  anuncio; placebo; no-solapado.
- **Diferencia con lo ya probado:** NO es el listing-leak de §4g (que apostaba a adivinar el
  listing). Acá el anuncio YA es público; el edge es el **gap temporal anuncio→apertura**
  explotando que el token preexiste en otro venue. Fuente y mecanismo distintos.
- **Fuentes:** https://www.binance.com/en/support/announcement/list/48 (nuevos listings);
  https://www.gate.io/docs/developers/apiv4/en/ y https://www.mexc.com/api-docs (klines de
  venues preexistentes).
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 3 · Novedad 3 · Retorno 3 → **ponderado 3.2**

### K2-03 — Scheduled-Maintenance Volatility Clamp
- **Mecanismo:** los exchanges publican **ventanas de mantenimiento** de sistemas (API,
  wallets, matching engine) por adelantado. Durante el mantenimiento, el arbitraje contra
  ese venue se corta → la liquidez agregada cae y la vol en los venues restantes puede
  dislocarse (spreads más anchos, gaps al reabrir).
- **Lag / persistencia:** la ventana está anunciada con días de anticipación; el efecto es
  mecánico (menos árbitros online) y no arbitrables porque el venue literalmente está caído.
- **Señal y horizonte:** reducir sizing / esperar reversión del gap de reapertura; horizonte
  minutos-horas alrededor de la ventana. (Fit bot: marginal — mejor como *filtro de riesgo*
  que como gatillo.)
- **Datos:** status pages oficiales (binance.statuspage, coinbase status, kraken status) y
  anuncios de "system upgrade". Histórico vía Wayback + el CHANGELOG de la API de Binance
  (lista upgrades con fecha/hora UTC, confirmado público). Rango 2020→hoy. [gratis]
- **Test de refutación:** vol realizada en [ventana, ventana+2h] vs control de mismo horario
  sin mantenimiento; placebo de horarios; no-solapado.
- **Diferencia con lo ya probado:** tema nuevo en el libro — nadie testeó mantenimientos
  programados como factor de vol. No es microestructura HFT (la ventana se conoce con días).
- **Fuentes:** https://developers.binance.com/en/docs/products/spot/CHANGELOG (upgrades con
  timestamp UTC); páginas de status de cada venue.
- **Score §1:** Mecanismo 3 · Lag 4 · Falsabilidad 4 · Costo 4 · Novedad 4 · Retorno 2 → **ponderado 3.4**

### K2-04 — Status-Page Incident Contagion
- **Mecanismo:** una *incidencia no programada* (degradación de API, retiros pausados) en un
  exchange grande, publicada en su status page, señala estrés operativo. Si los retiros se
  pausan, el precio en ESE venue puede desacoplarse (prima/descuento) respecto a venues
  sanos, porque el capital no puede moverse hasta que se resuelva.
- **Lag / persistencia:** la incidencia se publica en tiempo (semi) real; el desacople dura
  mientras la pausa esté activa (minutos-horas) y no se arbitra porque, justamente, no se
  puede mover capital a/desde el venue afectado.
- **Señal y horizonte:** operar el spread del precio del venue afectado vs el índice sano, o
  quedarse fuera; horizonte horas. (Fit bot medio.)
- **Datos:** status pages tienen **historial de incidentes público** (Atlassian Statuspage
  expone JSON de incidentes pasados). Rango depende del venue (típ. 2–3 años retenidos).
  [gratis] — con nota: algunos venues purgan incidentes viejos → parte forward-collect.
- **Test de refutación:** desvío de precio del venue afectado vs índice compuesto durante
  incidentes vs control; placebo; no-solapado.
- **Diferencia con lo ya probado:** ninguna previa. Usa el **feed de incidentes** de status
  pages, fuente no explorada en el libro.
- **Fuentes:** p.ej. `https://binance.statuspage.io/api/v2/incidents.json` y equivalentes
  Atlassian de otros venues.
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.2**

### K2-05 — GitHub Release-Cadence Pre-Mainnet
- **Mecanismo:** antes de un **upgrade/hardfork de mainnet** o un release mayor, la
  actividad de release en el repo oficial del protocolo (tags, release notes, merges a
  `main`) se acelera de forma pública y observable. El mercado valora el upgrade recién al
  anuncio oficial / fecha, pero la **cadencia de releases** lo adelanta.
- **Lag / persistencia:** devs publican código semanas antes del evento de precio; el retail
  no mira el repo. Lag estructural de atención.
- **Señal y horizonte:** long del token nativo cuando la tasa de releases/commits a ramas de
  release supera su baseline; horizonte días-semanas hasta el evento.
- **Datos:** **GH Archive** (BigQuery `githubarchive`, eventos de GitHub desde 2011, gratis
  en Sandbox) + API de releases de GitHub. Mapear repo↔token (ethereum/go-ethereum,
  solana-labs/solana, etc.). Rango 2015→hoy. [gratis vía BigQuery/GH Archive]
- **Test de refutación:** IC no-solapado entre z-score de release-rate y retorno forward 7/14d
  del token; placebo; OOS; control por beta de mercado.
- **Diferencia con lo ya probado:** el libro no tocó actividad de repos. Distinto de la
  familia "builders/topología" (§4b, refutada): acá no es topología de red sino **cadencia
  de releases como proxy de catalizador datado**.
- **Fuentes:** https://www.gharchive.org/ ; BigQuery `githubarchive.day.*`.
- **Score §1:** Mecanismo 3 · Lag 4 · Falsabilidad 4 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.5**

### K2-06 — Governance Proposal "Pass-to-Execute" Window
- **Mecanismo:** en DAOs con timelock (Compound, Uniswap, Aave…), una propuesta que **pasa
  la votación** tiene un **delay de ejecución fijo por contrato** (timelock, p.ej. 2 días)
  antes de aplicarse. Si la propuesta cambia parámetros con impacto económico (fees,
  incentivos, recompras), el efecto es *conocido y datado* pero recién se materializa a la
  ejecución.
- **Lag / persistencia:** el timelock es un lag **estructural del protocolo** — imposible de
  acelerar. El mercado suele reaccionar a la ejecución, no al "voto pasó + timelock corriendo".
- **Señal y horizonte:** posicionarse en el token de gobernanza en la ventana voto-pasó →
  ejecución; horizonte = largo del timelock (horas-días).
- **Datos:** Tally/Snapshot API (propuestas, estado, timestamps) + eventos del contrato
  Timelock on-chain (BigQuery `crypto_ethereum.logs`). Rango 2020→hoy. [gratis]
- **Test de refutación:** CAR del token en [voto-pasó, ejecución+1d] vs placebo de propuestas
  que NO pasaron; segmentar por tipo (económica vs cosmética); no-solapado.
- **Diferencia con lo ya probado:** ninguna previa de gobernanza en el libro. El lag es
  **contractual** (timelock), no de atención — eso lo hace más robusto que los lags de
  atención que murieron.
- **Fuentes:** https://docs.tally.xyz/ ; Snapshot GraphQL; contratos Timelock (OpenZeppelin).
- **Score §1:** Mecanismo 4 · Lag 4 · Falsabilidad 4 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.7**

### K2-07 — Snapshot Vote-Turnout Surprise
- **Mecanismo:** la **participación** (turnout / número de wallets votantes, no el resultado)
  en una votación de gobernanza mide atención genuina de la comunidad. Un turnout
  anormalmente alto en una propuesta señala un catalizador que la comunidad considera
  material — información de sentimiento pública pero poco mirada.
- **Lag / persistencia:** el turnout se ve durante la ventana de votación, antes de que el
  mercado digiera la relevancia; el retail no cuenta votantes.
- **Señal y horizonte:** long/short según dirección de la propuesta cuando turnout >> baseline
  del DAO; horizonte días.
- **Datos:** Snapshot GraphQL (votos por propuesta, voter count), gratis. Rango 2021→hoy.
  [gratis]
- **Test de refutación:** IC entre z-score de turnout y retorno forward; placebo; no-solapado;
  controlar por market-cap/liquidez del token.
- **Diferencia con lo ya probado:** mide **participación**, no resultado (K2-06 mide el
  timelock). Ángulo de sentimiento no explorado.
- **Fuentes:** https://docs.snapshot.org/tools/api
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 4 · Novedad 4 · Retorno 2 → **ponderado 3.2**

### K2-08 — Token-Generation-Event Countdown Compression
- **Mecanismo:** los proyectos publican **fecha de TGE / claim de airdrop** con antelación.
  A medida que el countdown se comprime, los farmers que acumularon posición en pre-mercado
  o puntos ajustan exposición de forma datada. No es el unlock de vesting (ya refutado, §4f):
  es el **primer día de liquidez** de un token nuevo, donde la oferta pasa de 0 a circulante.
- **Lag / persistencia:** la fecha es pública y fija; el reposicionamiento se concentra en los
  días previos. Persiste porque el evento es inevitable y datado.
- **Señal y horizonte:** patrón sistemático de pre-TGE (pre-market en venues que lo ofrecen) →
  retorno post-TGE; horizonte días alrededor del TGE.
- **Datos:** calendarios públicos de TGE (CoinMarketCal, ICO calendars) + pre-market de
  Hyperliquid/Whales Market cuando existe + klines post-listing. Rango 2023→hoy. [gratis /
  parte forward-collect para pre-market].
- **Test de refutación:** retorno día 0→día 3 post-TGE condicionado a señales pre-TGE; placebo
  con TGEs aleatorios; no-solapado.
- **Diferencia con lo ya probado:** explícitamente NO es unlocks/vesting (F4, refutada por
  placebo). Es el **debut de liquidez** (oferta 0→circulante), mecanismo y timing distintos.
- **Fuentes:** https://coinmarketcal.com/ (API) ; Hyperliquid pre-market docs.
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 2 · Novedad 3 · Retorno 3 → **ponderado 2.8**

### K2-09 — Exchange Wallet-Label "Cold-to-Hot" Reshuffle Timing
- **Mecanismo:** los exchanges mueven fondos entre cold y hot wallets en patrones observables
  on-chain. Un reaprovisionamiento grande de hot wallets (cold→hot) suele preceder a
  ventanas de **alta demanda de retiros esperada** (p.ej. antes de un evento de volatilidad
  que el propio exchange anticipa operativamente). Es metadata de infra, pública en la chain.
- **Lag / persistencia:** el movimiento on-chain es visible en el bloque; el significado
  operativo (el exchange se prepara para flujo) tiene lag de interpretación.
- **Señal y horizonte:** feature de régimen de liquidez; horizonte horas-días. (Fit bot medio,
  mejor como condicionante.)
- **Datos:** BigQuery `crypto_ethereum` + labels de exchange (`dawsbot/eth-labels`, MIT, ya
  usado en el libro). Rango 2020→hoy. [gratis]
- **Test de refutación:** IC entre volumen cold→hot (z-score) y vol forward de BTC/ETH;
  no-solapado; placebo; descartar si solo co-mueve con vol actual (parcial).
- **Diferencia con lo ya probado:** NO es netflow de whales (§4b, refutado: flujo direccional).
  Acá es **gestión interna de infra del exchange** (cold↔hot) como proxy de preparación
  operativa, no flujo de usuarios. Mecanismo distinto.
- **Fuentes:** https://github.com/dawsbot/eth-labels ; BigQuery public dataset.
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 3 · Costo 3 · Novedad 3 · Retorno 2 → **ponderado 2.6**

### K2-10 — Stablecoin Mint/Redeem Authorization Timing
- **Mecanismo:** Circle (USDC) y Tether publican/visibilizan on-chain las operaciones del
  contrato (mint, burn, blacklist) con timestamp. Un **burst de mints** autorizados señala
  capital entrando al ecosistema con intención de desplegarse — distinto del *supply
  circulante* (ya testeado, débil) porque mira la **cadencia/timing** del evento, no el nivel.
- **Lag / persistencia:** el mint es visible en el bloque; el despliegue del capital a riesgo
  tiene lag de horas-días.
- **Señal y horizonte:** long cripto cuando la tasa de mints acelera; horizonte días.
- **Datos:** eventos `Mint` de los contratos USDC/USDT (BigQuery `crypto_ethereum.logs` o
  Etherscan). Rango 2019→hoy. [gratis]
- **Test de refutación:** IC no-solapado entre conteo/tamaño de mints (z-score) y retorno
  forward BTC; placebo; OOS; controlar vs supply-level (debe aportar marginal sobre lo ya
  refutado).
- **Diferencia con lo ya probado:** stablecoin-supply-flow (§4d) usó el **nivel** de supply y
  dio débil/null. Esto usa la **cadencia de eventos de mint** (timing discreto) y exige
  aporte marginal sobre aquella serie. Si no aporta marginal → descartar.
- **Fuentes:** https://etherscan.io/token/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
  (USDC, eventos Mint); https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7
  (USDT); https://cloud.google.com/blog/products/data-analytics/ethereum-bigquery-public-dataset-smart-contract-analytics
  (BigQuery `crypto_ethereum.logs`).
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 3 · Novedad 2 · Retorno 3 → **ponderado 3.0**

### K2-11 — Futures Contract Listing (Perp Debut) Momentum
- **Mecanismo:** cuando un exchange **lista un perp nuevo** de un token que antes solo tenía
  spot, se habilita por primera vez el apalancamiento y el short. El cambio de estructura de
  mercado (de solo-spot a apalancable) tiene efecto datado sobre la vol y la dirección.
- **Lag / persistencia:** la fecha de listing del perp es pública y anunciada; el ajuste de
  posicionamiento (shorts recién posibles) se desarrolla en días.
- **Señal y horizonte:** patrón de vol/retorno post-debut del perp; horizonte días.
- **Datos:** anuncios de listing de futuros (Binance Futures announcements) + aparición del
  símbolo en `fapi` klines. Rango 2020→hoy. [gratis]
- **Test de refutación:** CAR y cambio de vol en [debut, debut+5d] vs control; placebo;
  no-solapado.
- **Diferencia con lo ya probado:** familia derivados pero ángulo **timing de estructura**
  (debut del perp), no funding/OI/base (ya cubiertos). Linda con K1; coordinar con K1 para no
  duplicar — aquí el foco es el **evento de listing**, no la métrica continua de derivados.
- **Fuentes:** https://www.binance.com/en/support/announcement/list/48 (futuros);
  `https://fapi.binance.com/fapi/v1/exchangeInfo`.
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 4 · Costo 4 · Novedad 3 · Retorno 3 → **ponderado 3.3**

### K2-12 — Index-Rebalance Anticipation (CoinDesk/CMC indices)
- **Mecanismo:** los índices cripto publicables (CoinDesk indices, CMC/FTSE índices) tienen
  **reglas y fechas de rebalance públicas**. Fondos que replican el índice deben ajustar en
  la fecha; los tokens que entran/salen tienen demanda/oferta datada, como el efecto
  S&P-inclusion en acciones.
- **Lag / persistencia:** la metodología y el calendario son públicos con antelación; el flujo
  pasivo se concentra en el día de rebalance. Lag estructural de ejecución del índice.
- **Señal y horizonte:** long tokens que entran / short los que salen antes del rebalance;
  horizonte días.
- **Datos:** metodologías y calendarios de índices (CoinDesk Indices, CF Benchmarks, CMC).
  Composición histórica retro es el cuello de botella → parte forward-collect. Rango según
  índice (≥2021). [parte gratis, parte forward-collect]
- **Test de refutación:** CAR de entrantes/salientes en [anuncio, rebalance] vs placebo;
  no-solapado; OOS.
- **Diferencia con lo ya probado:** ninguna previa. Trae el efecto índice de TradFi a cripto;
  distinto de ETF-flow (§4f, F1, data-gated) — acá el driver es el **rebalance del índice**,
  no el flujo del ETF.
- **Fuentes:** https://www.cfbenchmarks.com/ ; CoinDesk Indices methodology.
- **Score §1:** Mecanismo 4 · Lag 4 · Falsabilidad 3 · Costo 2 · Novedad 4 · Retorno 3 → **ponderado 3.4**

### K2-13 — Validator/Operator Public Downtime Signal
- **Mecanismo:** las métricas de performance de validadores/operadores (uptime, slashing,
  missed attestations) son **públicas** en beacon explorers. Un salto en missed attestations
  o un slashing evento señala estrés en un operador grande → posible venta forzada / pérdida
  de confianza en un LST asociado.
- **Lag / persistencia:** los datos de rendimiento se publican por época; la interpretación
  económica (riesgo del LST) tiene lag.
- **Señal y horizonte:** short del LST afectado (p.ej. token de un operador con problemas) vs
  ETH; horizonte días. (Fit bot medio.)
- **Datos:** beacon chain data. Nota del libro (§4g, L3): beaconcha.in ahora pide **API key
  gratis**; alternativa BigQuery/beacon dumps. Rango 2021→hoy. [gated-free: requiere key
  gratis]
- **Test de refutación:** CAR del LST en [evento de slashing/downtime, +3d] vs placebo;
  no-solapado.
- **Diferencia con lo ya probado:** §4g L3 miró la **cola de validadores** (oferta de venta).
  Esto mira **performance/slashing de operadores** (riesgo de contraparte del LST), fuente y
  mecanismo distintos.
- **Fuentes:** https://beaconcha.in/api/v1/docs ; dumps de beacon chain.
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 2 · Novedad 4 · Retorno 3 → **ponderado 3.0**

### K2-14 — CoinMarketCal Event-Density Clustering
- **Mecanismo:** CoinMarketCal agrega **eventos anunciados** (mainnets, partnerships,
  conferencias, burns) con fecha. Una **densidad anómala de eventos** en una ventana para un
  token señala un período de catalizadores concentrados — atención datada y pública que el
  precio aún no valoró.
- **Lag / persistencia:** los eventos se anuncian con antelación; el mercado no agrega la
  densidad. Lag de atención agregada.
- **Señal y horizonte:** long tokens con densidad de eventos creciente antes de la ventana;
  horizonte días-semanas.
- **Datos:** CoinMarketCal API (eventos con fecha, validación comunitaria). Rango 2018→hoy.
  [gated-free: API key gratis con rate-limit].
- **Test de refutación:** IC entre densidad de eventos (z-score) y retorno forward; placebo;
  no-solapado; cuidado con sesgo de que tokens populares tienen más eventos (controlar por
  market-cap).
- **Diferencia con lo ya probado:** ninguna. Fuente de calendario agregado no usada. Distinto
  de K2-08 (TGE puntual) — acá es **densidad agregada de eventos heterogéneos**.
- **Fuentes:** https://coinmarketcal.com/en/api
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 3 · Costo 3 · Novedad 3 · Retorno 2 → **ponderado 2.6**

### K2-15 — Exchange Reserve-Attestation Publication Lag
- **Mecanismo:** los exchanges publican **Proof-of-Reserves** en fechas (semi) regulares. El
  *acto de publicar* y su contenido (ratio de reservas) es un evento datado; una publicación
  retrasada o un ratio deteriorado señala estrés. El timing de publicación, no solo el valor,
  es información.
- **Lag / persistencia:** la cadencia de publicación es observable; el mercado reacciona al
  número pero poco al **patrón de timing** (retraso vs calendario esperado).
- **Señal y horizonte:** señal de riesgo risk-off cuando un exchange grande retrasa/empeora su
  PoR; horizonte días. (Fit bot: filtro de riesgo.)
- **Datos:** páginas de PoR de exchanges + snapshots on-chain de wallets atestiguadas. §4c ya
  marcó PoR como **data-gated/sub-powered** (sin historia diaria gratis). Esta ficha acota el
  alcance al **evento de publicación** (fechas), que sí se puede fechar vía Wayback. [gated/
  parte forward-collect].
- **Test de refutación:** CAR del token del exchange (si cotiza, p.ej. tokens de plataforma) o
  de BTC en [publicación PoR, +2d] vs calendario esperado; placebo.
- **Diferencia con lo ya probado:** §4c miró el **nivel/serie** de reservas (data-gated). Esto
  acota al **timing del evento de publicación** como señal, no la serie — ángulo más barato y
  testeable por fechas.
- **Fuentes:** https://www.binance.com/en/proof-of-reserves (PoR Binance);
  https://web.archive.org/ (snapshots fechados de las páginas PoR para reconstruir el
  calendario de publicación).
- **Score §1:** Mecanismo 2 · Lag 2 · Falsabilidad 3 · Costo 2 · Novedad 3 · Retorno 2 → **ponderado 2.3**

### K2-16 — Fork/Upgrade Activation-Block Countdown
- **Mecanismo:** los hardforks de L1 se activan en un **bloque/epoch específico conocido**
  (no en una fecha difusa). A medida que se acerca el bloque de activación, la incertidumbre
  técnica se resuelve de forma datada; históricamente hay un patrón de "buy the rumor, sell
  the news" alrededor del bloque.
- **Lag / persistencia:** el bloque de activación es determinista y público; el patrón de
  reposicionamiento es datable con precisión de bloque.
- **Señal y horizonte:** patrón sistemático pre/post bloque de activación del token nativo;
  horizonte días alrededor del fork.
- **Datos:** anuncios de fork con bloque objetivo (blogs de fundaciones, repos) + timestamp del
  bloque. Rango: todos los forks de ETH/otras L1 desde 2016. Pocos eventos (~decenas) → test
  de pocas muestras. [gratis]
- **Test de refutación:** CAR [−10d, +10d] alrededor del bloque de activación vs placebo;
  dado N chico, reportar potencia y no sobre-interpretar.
- **Diferencia con lo ya probado:** K2-05 mira **cadencia de releases** (continuo); esto mira
  el **evento discreto de activación** (bloque exacto). Complementarios, mecanismos distintos.
- **Fuentes:** https://ethereum.org/en/history/ (forks y bloques); repos de clientes.
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 4 · Novedad 2 · Retorno 2 → **ponderado 2.8**

### K2-17 — Airdrop Snapshot-Date "Farming Unwind"
- **Mecanismo:** cuando un protocolo anuncia que tomó (o tomará) un **snapshot** para un
  airdrop, los farmers que inflaban actividad/TVL para calificar **dejan de farmear** después
  del snapshot. El retiro de ese capital mercenario es datado (post-snapshot) y predecible.
- **Lag / persistencia:** la fecha del snapshot se anuncia o se infiere; el unwind ocurre en
  los días siguientes. No se arbitra porque el capital mercenario es grande y sale en masa.
- **Señal y horizonte:** short del token / TVL-sensitive asset post-snapshot; horizonte días.
- **Datos:** anuncios de snapshot (Twitter/blogs oficiales, fechados) + TVL de DefiLlama +
  klines. Rango 2021→hoy. [gratis / parte forward-collect para fechas de snapshot].
- **Test de refutación:** CAR y cambio de TVL post-snapshot vs placebo; no-solapado; segmentar
  por tamaño del incentivo.
- **Diferencia con lo ya probado:** no es unlocks (F4) ni TGE (K2-08). Es el **fin del farming
  incentivado** (snapshot como fecha de corte del comportamiento mercenario). Mecanismo nuevo.
- **Fuentes:** https://defillama.com/docs/api (TVL API); anuncios de snapshot (posts
  oficiales fechados del protocolo; curación manual, sin feed único verificable).
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 3 · Novedad 3 · Retorno 3 → **ponderado 3.0**

### K2-18 — Regulatory-Filing Timestamp Edge (EDGAR/court dockets)
- **Mecanismo:** los filings regulatorios (SEC EDGAR, dockets judiciales PACER, decisiones de
  la CFTC) son **públicos y con timestamp exacto de publicación**. Un filing material (fallo,
  settlement, S-1 de ETF) mueve el mercado; el edge es la **latencia entre la publicación
  oficial estructurada y la difusión en medios cripto** (minutos-horas).
- **Lag / persistencia:** EDGAR publica en su feed antes de que los agregados cripto lo
  levanten; lag de difusión real y repetible.
- **Señal y horizonte:** reaccionar al filing estructurado antes que el flujo mediático;
  horizonte minutos-horas. (Fit bot: límite inferior; marcar research/forward.)
- **Datos:** EDGAR full-text search + RSS (gratis, timestamps precisos); CourtListener/PACER
  para dockets (gratis/semi). Rango: EDGAR desde 1994, filings cripto-relevantes desde ~2017.
  [gratis para EDGAR]
- **Test de refutación:** retorno BTC/ETH/token en [timestamp del filing, +1h] vs control;
  requiere mapear filings materiales (curación manual) → N moderado; placebo temporal.
- **Diferencia con lo ya probado:** ninguna previa. Fuente TradFi estructurada (EDGAR) no
  usada en el libro. No es insider: es un feed oficial público leído rápido.
- **Fuentes:** https://www.sec.gov/edgar/search/ (RSS/full-text); https://www.courtlistener.com/
- **Score §1:** Mecanismo 3 · Lag 3 · Falsabilidad 3 · Costo 3 · Novedad 4 · Retorno 3 → **ponderado 3.1**

### K2-19 — Mining-Difficulty-Adjustment Timing (BTC)
- **Mecanismo:** el ajuste de dificultad de BTC ocurre cada **2016 bloques**, en una ventana
  predecible. Un ajuste fuerte al alza aprieta márgenes de mineros → presión de venta
  potencial (mineros venden para cubrir costos). El timing del ajuste es determinista.
- **Lag / persistencia:** la fecha del ajuste es estimable con precisión días antes (por hashrate);
  la reacción de los mineros tiene lag de días.
- **Señal y horizonte:** señal de presión de oferta post-ajuste cuando la dificultad sube fuerte;
  horizonte días.
- **Datos:** dificultad y hashrate históricos (blockchain.com API, mempool.space, gratis) +
  klines BTC. Rango 2010→hoy. [gratis]
- **Test de refutación:** retorno BTC en [ajuste, +5d] condicionado al signo/magnitud del
  ajuste vs placebo; no-solapado; OOS por halving-epoch.
- **Diferencia con lo ya probado:** ninguna previa. Métrica de infra PoW (dificultad) como
  evento de timing; no es flujo on-chain genérico.
- **Fuentes:** https://mempool.space/docs/api ; blockchain.com charts API.
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 4 · Costo 4 · Novedad 3 · Retorno 2 → **ponderado 3.0**

### K2-20 — NPM/PyPI Dependency-Release Pre-Catalyst
- **Mecanismo:** muchos protocolos publican SDKs/paquetes (npm, PyPI, crates.io) con
  **versionado público**. Un bump de versión mayor de un SDK oficial suele preceder a
  integraciones/partnerships anunciadas después. La metadata del package registry es pública
  y nadie en trading la mira.
- **Lag / persistencia:** el release del paquete es anterior al anuncio comercial; lag de
  atención estructural (es "plumbing" de devs).
- **Señal y horizonte:** long del token cuando el SDK oficial tiene un major bump; horizonte
  semanas.
- **Datos:** APIs de registries (npm registry, PyPI JSON, crates.io) con historial de
  versiones y fechas, gratis. Mapear package↔token. Rango 2016→hoy. [gratis]
- **Test de refutación:** IC entre eventos de major-release y retorno forward 14/30d; placebo;
  no-solapado; N moderado → reportar potencia.
- **Diferencia con lo ya probado:** complementa K2-05 (GitHub) pero usa **package registries**
  (otra fuente, otra señal: release publicado vs commit). Ruta de datos distinta.
- **Fuentes:** https://registry.npmjs.org/ ; https://pypi.org/pypi/<pkg>/json ; crates.io API.
- **Score §1:** Mecanismo 2 · Lag 4 · Falsabilidad 3 · Costo 4 · Novedad 4 · Retorno 2 → **ponderado 3.1**

### K2-21 — Wikipedia/Docs Pageview Pre-Spike
- **Mecanismo:** las vistas de página de Wikipedia (y la edición de artículos) de un
  token/protocolo son **públicas vía API** y reflejan atención retail naciente. Un spike de
  pageviews puede preceder flujo de compra retail que todavía no llegó al libro.
- **Lag / persistencia:** la curiosidad (leer antes de comprar) precede a la orden; lag de
  conversión atención→capital.
- **Señal y horizonte:** long cuando pageviews z-score salta; horizonte días.
- **Datos:** Wikimedia Pageviews API (gratis, desde 2015, granularidad diaria/horaria) +
  klines. [gratis]
- **Test de refutación:** IC no-solapado pageviews→retorno forward; placebo; OOS; descartar si
  es coincidente con precio (lead-lag/Granger para confirmar que lidera).
- **Diferencia con lo ya probado:** ninguna previa de search/attention. Es sentimiento/atención
  retro-testeable (a diferencia de Google Trends, Wikimedia da histórico horario limpio y
  estable).
- **Fuentes:** https://wikimedia.org/api/rest_v1/ (pageviews).
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 4 · Costo 4 · Novedad 3 · Retorno 2 → **ponderado 3.0**

### K2-22 — Exchange API Rate-Limit/Spec Change as Flow Tell
- **Mecanismo:** cuando un exchange cambia **rate-limits, nuevos endpoints o pesos de API**
  (publicado en su CHANGELOG), suele anticipar cambios de producto (nuevos pares, mayor
  capacidad esperada de trading). Es metadata de infra que señala preparación para flujo.
- **Lag / persistencia:** el cambio de spec se publica antes del lanzamiento del producto; lag
  de interpretación (nadie liga "subieron el rate-limit de fapi" con "viene algo").
- **Señal y horizonte:** señal débil de régimen/actividad esperada del venue; horizonte
  semanas. (Fit bot: contextual.)
- **Datos:** CHANGELOGs de API (Binance confirmado público con fechas UTC; OKX/Bybit análogos)
  vía Wayback. Rango 2019→hoy. [gratis]
- **Test de refutación:** volumen/vol del venue en semanas post-cambio vs baseline; placebo;
  N chico → exploratorio.
- **Diferencia con lo ya probado:** ninguna. Fuente muy exótica (changelog de API como señal).
  Probablemente débil, pero barata y original.
- **Fuentes:** https://developers.binance.com/en/docs/products/spot/CHANGELOG
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 2 · Costo 3 · Novedad 5 · Retorno 1 → **ponderado 2.5**

### K2-23 — DNS/Subdomain & Job-Posting Pre-Launch Tells
- **Mecanismo:** los proyectos preparan infra pública observable antes de anuncios: nuevos
  **subdominios** (certificate transparency logs), **job postings** específicas (señalan
  expansión a un vertical), páginas de docs publicadas sin anuncio. Todo público, indexable.
- **Lag / persistencia:** la infra se levanta semanas antes del anuncio; lag de atención (nadie
  monitorea CT logs de proyectos cripto para trading).
- **Señal y horizonte:** long del token cuando aparece infra pre-lanzamiento; horizonte
  semanas. (Fit bot: research/forward.)
- **Datos:** CT logs (crt.sh, gratis) + boards de empleo. §4g marcó **cert-transparency como
  forward-collect** (sin historia retro). Esta ficha lo reconoce: es mayormente
  **forward-collect**, pero crt.sh SÍ guarda histórico de certificados (fecha de emisión) →
  parcialmente retro-testeable para subdominios. [parte gratis-retro vía crt.sh, parte
  forward-collect].
- **Test de refutación:** event-study retorno post-aparición de subdominio nuevo relevante vs
  placebo; curación manual → N chico.
- **Diferencia con lo ya probado:** §4g citó cert-transparency como no-testeable retro. Acá se
  refina: **crt.sh conserva fecha de emisión de certificados**, lo que habilita un test retro
  acotado de subdominios — cambia el supuesto de datos de §4g.
- **Fuentes:** https://crt.sh/ ; boards públicos de empleo.
- **Score §1:** Mecanismo 3 · Lag 4 · Falsabilidad 2 · Costo 2 · Novedad 5 · Retorno 2 → **ponderado 3.0**

### K2-24 — Scheduled Token Burn Countdown
- **Mecanismo:** varios tokens tienen **burns programados** (quarterly burns tipo BNB auto-burn,
  buyback-and-burn con fecha). La reducción de oferta es datada y pública; el mercado suele
  valorar el burn con "buy the rumor".
- **Lag / persistencia:** la fecha/criterio del burn es público; el patrón de precio alrededor
  del evento es datable.
- **Señal y horizonte:** patrón pre/post burn programado; horizonte días.
- **Datos:** anuncios de burn + eventos `Burn`/transfer-to-0x0 on-chain (BigQuery/Etherscan) +
  klines. Rango 2019→hoy. [gratis]
- **Test de refutación:** CAR [−5d, +5d] alrededor del burn vs placebo; no-solapado; segmentar
  por tamaño del burn relativo al float.
- **Diferencia con lo ya probado:** ninguna. Reducción de oferta datada — la cara espejo de los
  unlocks (F4), pero con dirección opuesta y mecanismo distinto (quema, no liberación). F4
  refutó *liberación*; el *burn* no se testeó.
- **Fuentes:** https://academy.binance.com/en/articles/what-is-bnb-auto-burn (ejemplo de
  burn programado con fórmula pública); eventos on-chain a la dirección de quema
  https://etherscan.io/address/0x000000000000000000000000000000000000dead (tokens ERC-20).
- **Score §1:** Mecanismo 2 · Lag 3 · Falsabilidad 4 · Costo 3 · Novedad 3 · Retorno 2 → **ponderado 2.9**

### K2-25 — Funding-Settlement Clock Skew Across Venues
- **Mecanismo:** los perps liquidan funding en **horarios fijos conocidos** (típ. cada 8h:
  00/08/16 UTC en Binance), pero distintos venues tienen relojes/horas **ligeramente
  distintos**. Alrededor del settlement hay flujo mecánico (quien no quiere pagar/cobrar
  funding ajusta antes del corte). El timing del corte es público.
- **Lag / persistencia:** los horarios de funding son fijos y publicados; el flujo
  pre-settlement es mecánico y recurrente (sucede cada 8h).
- **Señal y horizonte:** patrón de retorno/vol en los minutos previos al settlement de funding;
  horizonte minutos-horas. (Fit bot: límite — marcar research salvo que el patrón sea de horas.)
- **Datos:** horarios de funding (docs de cada venue) + klines de alta frecuencia +
  fundingRate history (`fapi/v1/fundingRate`, gratis). Rango 2020→hoy. [gratis]
- **Test de refutación:** retorno en ventana pre-settlement vs resto del día; condicionar al
  signo/magnitud del funding; placebo de horarios; no-solapado.
- **Diferencia con lo ya probado:** NO es #6 (dispersión de funding entre monedas) ni F3 (base).
  Acá el eje es el **timing del corte de funding** (reloj del settlement), un efecto de
  calendario intradía, no el nivel de funding. Linda con K1 → coordinar; foco K2 = timing.
- **Fuentes:** https://www.binance.com/en/support/faq (funding schedule);
  `https://fapi.binance.com/fapi/v1/fundingRate`.
- **Score §1:** Mecanismo 3 · Lag 2 · Falsabilidad 4 · Costo 4 · Novedad 3 · Retorno 2 → **ponderado 3.0**

---

## Tabla resumen

| id | Nombre | Score | Datos | Fit bot |
|---|---|---|---|---|
| K2-06 | Governance Pass-to-Execute (timelock) | 3.7 | Tally/Snapshot + logs on-chain [gratis] | ✅ alto (lag contractual) |
| K2-01 | Delisting Forced-Exit Drift | 3.6 | Anuncios + data.binance.vision [gratis] | ✅ alto |
| K2-05 | GitHub Release-Cadence Pre-Mainnet | 3.5 | GH Archive/BigQuery [gratis] | ✅ alto |
| K2-03 | Scheduled-Maintenance Vol Clamp | 3.4 | Status pages + API CHANGELOG [gratis] | ⚠️ filtro de riesgo |
| K2-12 | Index-Rebalance Anticipation | 3.4 | CF Benchmarks/CoinDesk [parte forward] | ✅ alto |
| K2-11 | Perp-Debut Momentum | 3.3 | Futures announcements + fapi [gratis] | ✅ alto |
| K2-02 | Listing Teaser-to-Trade Gap | 3.2 | Anuncios + klines venue menor [parte forward] | ⚠️ horas |
| K2-04 | Status-Page Incident Contagion | 3.2 | Statuspage incidents JSON [gratis] | ⚠️ medio |
| K2-07 | Snapshot Vote-Turnout Surprise | 3.2 | Snapshot GraphQL [gratis] | ✅ medio |
| K2-18 | Regulatory-Filing Timestamp Edge | 3.1 | EDGAR RSS/CourtListener [gratis] | ⚠️ horas |
| K2-20 | NPM/PyPI Dependency-Release | 3.1 | npm/PyPI/crates API [gratis] | ✅ semanas |
| K2-10 | Stablecoin Mint/Redeem Timing | 3.0 | Contratos USDC/USDT logs [gratis] | ✅ medio |
| K2-13 | Validator/Operator Downtime | 3.0 | beaconcha.in [gated-free] | ⚠️ medio |
| K2-17 | Airdrop Snapshot Farming-Unwind | 3.0 | DefiLlama + anuncios [parte forward] | ✅ medio |
| K2-19 | Mining-Difficulty-Adjustment Timing | 3.0 | mempool.space/blockchain.com [gratis] | ✅ medio |
| K2-21 | Wikipedia Pageview Pre-Spike | 3.0 | Wikimedia API [gratis] | ✅ medio |
| K2-23 | DNS/CT-log & Job-Posting Tells | 3.0 | crt.sh [parte retro/forward] | ⚠️ research |
| K2-16 | Fork Activation-Block Countdown | 2.8 | ethereum.org/forks + bloques [gratis] | ✅ medio (N chico) |
| K2-08 | TGE Countdown Compression | 2.8 | CoinMarketCal + pre-market [parte forward] | ✅ medio |
| K2-24 | Scheduled Token Burn Countdown | 2.9 | Anuncios + on-chain burns [gratis] | ✅ medio |
| K2-09 | Exchange Cold-to-Hot Reshuffle | 2.6 | BigQuery + eth-labels [gratis] | ⚠️ medio |
| K2-14 | CoinMarketCal Event-Density | 2.6 | CoinMarketCal API [gated-free] | ⚠️ medio |
| K2-22 | API Rate-Limit/Spec Change Tell | 2.5 | API CHANGELOGs [gratis] | ⚠️ contextual |
| K2-25 | Funding-Settlement Clock Skew | 3.0 | fapi fundingRate + klines [gratis] | ⚠️ intradía |
| K2-15 | Reserve-Attestation Publication Lag | 2.3 | PoR pages via Wayback [gated/forward] | ⚠️ riesgo |

**Conteo: 25 fichas (K2-01 … K2-25).**

### Notas de coordinación para K5 (revisor)
- **Posible solapamiento con K1 (derivados):** K2-11 (perp-debut) y K2-25 (funding-settlement
  clock) tocan derivados pero desde el ángulo *timing de evento*, no métrica continua. Si K1
  propone algo equivalente, quedarse con la versión mejor especificada.
- **Mejores apuestas testeables-ya (retro, data gratis, fit bot):** K2-06, K2-01, K2-05,
  K2-19, K2-21, K2-24 — todas tienen historia reconstruible y horizonte de días.
- **Marcadas honestamente como forward-collect / gated:** K2-08, K2-12, K2-15, K2-23 (parcial),
  K2-13, K2-14. No sobre-venderlas.
- **Línea roja:** ninguna ficha usa insider/MNPI ni explota vulnerabilidades. Todo es lectura
  de feeds oficiales, on-chain público, o registries abiertos.
