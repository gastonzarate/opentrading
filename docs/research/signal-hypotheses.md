# Libro de hipótesis de señal — OpenTrading

> Documento vivo. Última actualización: 2026-07-14.
> Objetivo: buscar un **edge informacional** en cripto (no análisis técnico, que ya
> dio expectativa negativa). Flujo de trabajo: **idear → validar con evidencia →
> converger → recién ahí decidir si va al bot.** Nada de acá está implementado.

---

## 1. Cómo leer el score

Cada hipótesis se puntúa en 6 dimensiones (0–5) y se pondera. La escala **no** mide
"cuánto va a ganar" — mide **qué tan buena es la apuesta de dedicarle tiempo a
backtestearla**. Una idea con score alto es una que, si el edge existe, lo vamos a
poder *probar rápido, barato y sin autoengaño*.

| Dimensión | Peso | Qué pregunta |
|---|---|---|
| **Mecanismo** | 25% | ¿Hay una razón estructural clara de *por qué* debería funcionar? ¿O es data-mining? |
| **Lag / persistencia** | 20% | ¿Por qué el edge no se arbitra al instante? ¿Hay un retardo estructural que lo sostenga? |
| **Falsabilidad** | 15% | ¿Se puede *matar* rápido con un test limpio? (una idea que no se puede refutar no sirve) |
| **Costo de test** | 15% | Inverso al esfuerzo. 5 = data que ya bajamos; 1 = feed nuevo y difícil. |
| **Novedad / anti-crowding** | 15% | ¿Nadie lo usa? Si medio mundo ya lo mira, el edge ya se pagó. |
| **Retorno potencial** | 10% | Magnitud plausible del edge *si* es real. |

> **Filtro extra de fit con nuestro bot:** OpenTrading corre en un *scheduler*
> (minutos), no es un HFT sub-segundo. Las señales de **horas/días** encajan; las de
> **segundos/minutos** (microestructura pura) pueden ser reales pero **no las podemos
> ejecutar** con nuestra arquitectura. Eso baja mucho el atractivo práctico de las
> Tier 2, aunque el score de la idea en sí sea decente.

> **Sobre "cuánto podríamos ganar":** salvo #6 (que ya tiene backtest real), los
> números de las hipótesis nuevas son **expectativas a priori, NO medidas**. Están
> para ordenar prioridades, no para creerles. El número real sale recién después de
> backtestear.

---

## 2. El hallazgo de la ronda 2: la familia "entropía / sorpresa"

De 630 ideas generadas, 359 eran territorio nuevo (fuera de la ronda 1), y
**convergieron solas a una familia coherente** que no habíamos tocado.

**Tesis unificadora:** *el mercado se rompe justo cuando una distribución que
normalmente es diversa/ruidosa colapsa a un solo modo.* Una sola timezone operando,
un solo market-maker mecánico cotizando, una sola narrativa en los launchpads, un
solo origen de fondeo. **Concentración = fragilidad, y se mide *antes* de que
reaccione el precio** — con entropía de Shannon, divergencia KL, información mutua o
entropía de permutación. Es un ángulo que casi nadie usa en cripto retail.

---

## 3. Shortlist rankeada

| # | Hipótesis | Tier | Score | Fit bot | Estado |
|---|---|---|---|---|---|
| 2 | Cross-stablecoin Peg Synchronization | 🟢 1 | 4.3 | ✅ alto | ❌ **REFUTADA** (detector coincidente, no predictor) |
| 1 | Timezone Handoff Volume-Entropy | 🟢 1 | 3.9 | ✅ alto | ⚠️ **DÉBIL PERO REAL** (Sharpe 0.43; sirve de filtro de régimen) |
| 6 | Blob-fee KL Surprise | 🔵 3 | **3.7** | ✅ alto | media-alta |
| 3 | Quote-Lifetime Entropy Collapse | 🟡 2 | **3.6** | ⚠️ bajo (HFT) | media |
| 4 | Iceberg Absorption Surprise | 🟡 2 | **3.5** | ⚠️ bajo (HFT) | media |
| 7 | GPU-Spot → DePIN Spillover | 🔵 3 | **3.5** | ✅ alto | media-alta |
| 5 | Depth-Update Coupling (layering) | 🟡 2 | **3.2** | ⚠️ bajo (HFT) | baja-media |

---

## 4. Las hipótesis en detalle

### #2 — Cross-stablecoin Peg Synchronization · 🟢 Tier 1 · Score 4.3

> 🔴 **VERDICTO BACKTEST (2026-07-14): REFUTADA como predictor.** Data 1h 2022–2026,
> 5 stablecoins. El sanity check pasó (LUNA z=+6.98, SVB/USDC z=+1.60 → *detecta* el
> estrés), pero el test predictivo falló entero: event-study diff ON−OFF ≈ +0.011%
> (nulo, no-monotónico), IC continuo −0.007 (signo equivocado), permutación p=0.91,
> OOS cambia de signo (H1 +0.023 / H2 −0.040). **Es un detector coincidente de
> estrés, no un predictor adelantado** — para cuando los pegs se sincronizan, la vol
> ya está acá. Útil como confirmación risk-off, NO como alpha. Descartada.

**Cómo funciona (fácil).** Cada stablecoin (USDT, USDC, DAI, FDUSD…) tiene su propio
riel de emisión/redención y sus propios bancos. En condiciones normales, cada peg se
mueve con ruido *propio* e independiente. Pero **los mismos market-makers arbitran
todos los pegs a la vez**. Cuando ese capital compartido se retira (susto bancario,
estrés de funding), los pegs empiezan a **temblar todos juntos**. Esa sincronización
—que se mide con *información mutua* entre los pegs— se dispara **antes** de que
estalle la volatilidad de BTC/ETH. Es una señal de **estrés sistémico → subí cash /
reducí exposición / comprá volatilidad**.

**Score.**
- Mecanismo 4.5 — muy sólido y económico: capital de arbitraje compartido.
- Lag 4.0 — el estrés se propaga en horas.
- Falsabilidad 5.0 — **tiene chequeo de cordura incorporado**: debe encenderse sí o
  sí en SVB/USDC-depeg (mar-2023), FTX (nov-2022), LUNA (may-2022). Si no se
  enciende ahí, la hipótesis está muerta. Limpísimo.
- Costo test 4.5 — klines de pares stablecoin en Binance spot, gratis.
- Novedad 4.0 — la info mutua entre pegs casi no se usa en retail.
- Retorno 3.5.

**Cuánto podríamos ganar (prior).** No es una máquina de imprimir direccional; es una
señal **defensiva de timing**. Su valor es *evitar drawdowns* (salir antes del pico
de vol) y opcionalmente *comprar vol barata* antes del salto. Bien calibrada, el
aporte típico de una señal de riesgo así es recortar la peor caída y mejorar el
Sharpe general — no un % anual aislado.

**Qué hace falta.** (1) Panel 1-min 2022–2025 de 4–5 pares stablecoin. (2) Info
mutua rolling + z-score. (3) Sanity check en SVB/FTX/LUNA. (4) Event-study de vol
forward de BTC/ETH condicionada a la señal. **Todo con data que ya sabemos bajar.**

---

### #1 — Timezone Handoff Volume-Entropy Continuation · 🟢 Tier 1 · Score 3.9

> 🟡 **VERDICTO BACKTEST (2026-07-14): DÉBIL PERO REAL.** Data 1h 2022–2026, 5
> símbolos (8.125 filas símbolo·día). Gradiente monotónico correcto: CONCENTRADO →
> continuación (+0.097%/día), NEUTRO ~0, DIFUSO → reversión (−0.078%). IC continuo
> +0.021 con **permutación p=0.025** (efecto real). OOS consistente: ambas mitades
> positivas (H1 +0.031% / H2 +0.164%). P&L BTC operable: 393 trades, win 51%, avg
> +0.168%, +43% total en ~4,5a, **Sharpe 0.43**. Conclusión: efecto genuino pero
> demasiado chico para operarla sola; el valor real es como **variable de régimen**
> (concentración→momentum / difusión→reversión) para condicionar otras señales.

**Cómo funciona (fácil).** Cripto opera 24/7, pero la liquidez y la atención rotan
entre las horas laborales de Asia / Europa / EE.UU. Para cada día calculás la
**entropía de Shannon** de cómo se reparte el volumen por hora. Cuando esa entropía
**colapsa** (el volumen se concentró en una sola sesión), significa que ese día lo
manejó **una sola región operando sobre información local** (una noticia local, un
desk local reposicionándose) que los que dormían en otras zonas todavía no
procesaron. Predicción: ese movimiento **continúa** en la apertura de la región
siguiente.

**Score.**
- Mecanismo 3.5 — razonable, pero el "continuation" puede solaparse con momentum
  intradía ya conocido.
- Lag 3.5 — el handoff entre sesiones es un lag real de horas.
- Falsabilidad 5.0 — test trivial por buckets (z-score de entropía × sesión dominante).
- Costo test 5.0 — **solo velas 1h que ya bajamos.** La más barata de todas.
- Novedad 3.5 — la entropía de volumen es semi-novel; el momentum de sesión no tanto.
- Retorno 3.0.

**Cuánto podríamos ganar (prior).** Edge direccional chico pero de alta frecuencia
(hay un "handoff" todos los días). Si el efecto de continuación aguanta, se puede
componer seguido. Prior: modesto pero constante.

**Qué hace falta.** 3+ años de velas 1h de BTC/ETH + 10 alts líquidas. Entropía diaria
de volumen + z-score 30d + tag de sesión dominante + retornos con signo de sesión.
Bucketear retorno de la sesión siguiente por (tercil de z-score × sesión). **Se puede
probar esta semana.**

---

### #6 — Blob-fee KL Surprise (rotación risk-on a L2) · 🔵 Tier 3 · Score 3.7

**Cómo funciona (fácil).** Desde EIP-4844, el espacio de "blobs" en Ethereum se
cobra con un mecanismo **totalmente desacoplado** del gas de ejecución. Entonces un
salto en el fee de blobs es una lectura *limpia* de que los rollups (Base, Arbitrum,
etc.) están posteando más batches → **más actividad especulativa retail en L2**
(oleadas de memecoins/airdrops/mints). Medís la **sorpresa** de ese fee con
divergencia KL (distribución reciente vs baseline de 30 días) y, cuando sorprende al
alza, **te ponés long una canasta de tokens L2 (ARB/OP) contra BTC**.

**Score.** Mecanismo 4.0 · Lag 3.5 · Falsabilidad 4.0 · Costo test 2.5 (data
on-chain de blobs vía Dune/RPC — feed nuevo) · Novedad 4.5 (casi nadie lo mira) ·
Retorno 3.5.

**Cuánto podríamos ganar (prior).** Las rotaciones L2 vs BTC pueden ser jugosas
(betas altos). Prior media-alta *si* el lead-lag se confirma. Riesgo: los tokens L2
son volátiles y la señal puede llegar tarde.

**Qué hace falta.** Reconstruir la sorpresa KL horaria del blob-fee desde mar-2024
(RPC/Etherscan/Dune) + velas de ARB/OP/ETH/BTC. Regresión de retorno forward 1/2/4d
de la canasta L2 − BTC sobre la sorpresa firmada, controlando por funding y vol.
**Requiere montar un feed on-chain nuevo.**

---

### #3 — Quote-Lifetime Entropy Collapse (QLEC) · 🟡 Tier 2 · Score 3.6

**Cómo funciona (fácil).** La liquidez sana es una *ecología diversa*: límites de
retail pacientes, arbitrajistas, varios MMs con cadencias distintas, icebergs. Eso
produce una distribución **ancha** (alta entropía) de "cuánto tiempo vive cada precio
en el tope del book". Cuando la liquidez informada y paciente se retira antes de un
movimiento, queda solo un **monocultivo de bots MM** repriceando mecánicamente → la
entropía de esos tiempos de vida **colapsa**. Eso anticipa vol/movimiento en los
próximos 15–60 min.

**Score.** Mecanismo 4.0 · Lag 3.0 (edge de minutos, territorio HFT) · Falsabilidad
4.0 · Costo test 2.5 (reconstruir bookTicker histórico, pesado) · Novedad 4.5 ·
Retorno 3.5.

**⚠️ Fit bot bajo:** horizonte de minutos → nuestro scheduler no lo ejecuta bien.

**Cuánto podríamos ganar (prior).** Media, pero **capturarla requiere infra de baja
latencia** que hoy no tenemos. Más útil como *filtro de régimen* (no operar cuando la
liquidez es monocultivo) que como señal de entrada.

**Qué hace falta.** bookTicker + aggTrades históricos de data.binance.vision;
reconstruir entropía rolling de lifetimes + z-score; medir vol/retorno forward
condicionado al desbalance de agresor. Procesamiento pesado.

---

### #4 — Iceberg Absorption Surprise (IAS) · 🟡 Tier 2 · Score 3.5

**Cómo funciona (fácil).** Un jugador informado grande que quiere acumular sin
señalizarse usa un **iceberg**: muestra solo la punta y la recarga tras cada fill. El
book lo esconde, pero **la cinta de trades lo delata**: mucho volumen agresivo pega
contra un nivel y el precio **no logra atravesarlo**. Esa "absorción" (volumen
ejecutado ≫ profundidad visible, con precio clavado) revela un iceberg defendiendo un
nivel → drift forward hacia el lado defendido.

**Score.** Mecanismo 4.0 · Lag 3.0 · Falsabilidad 4.0 · Costo test 2.5 · Novedad 4.0
· Retorno 3.5. **⚠️ Fit bot bajo (minutos).**

**Cuánto podríamos ganar (prior).** Media. Buen mecanismo, pero mismo problema de
latencia que QLEC.

**Qué hace falta.** aggTrades + bookDepth snapshots; detectar episodios de absorción
(ratio alto, precio clavado); medir retorno forward 10/20/30 min vs control de mismo
volumen sin absorción.

---

### #7 — GPU-Spot → DePIN Spillover · 🔵 Tier 3 · Score 3.5

**Cómo funciona (fácil).** Las redes DePIN de cómputo descentralizado (Render, Akash,
etc.) monetizan el spread entre su costo marginal y el precio del cloud centralizado.
Cuando el **precio spot de alquiler de GPUs** (H100/A100 en Vast.ai/RunPod) sube, el
arbitraje de sustitución se ensancha y las cargas migran a la oferta descentralizada
más barata → sube la utilización y el valor del token. Como **los traders de cripto
no miran precios de GPU**, hay un lag de varios días → long canasta de tokens
compute-DePIN.

**Score.** Mecanismo 3.5 · **Lag 4.0** (lag real y grande — nadie mira ese dato) ·
Falsabilidad 3.5 · Costo test 1.5 (historia de GPU spot es fina/difícil) · **Novedad
5.0** (nadie lo usa) · Retorno 3.5.

**Cuánto podríamos ganar (prior).** Media-alta *si* el lead-lag se confirma con
Granger; es de las más originales. Riesgo principal: **conseguir historia confiable
de precios de GPU** es el cuello de botella.

**Qué hace falta.** Índice diario de precio GPU-hora (H100/A100) desde ~2023 (Vast.ai/
RunPod). Alinear a retornos de tokens. Primero lead-lag/Granger para confirmar que el
hardware **lidera** (no solo co-mueve); después event-study.

---

### #5 — Depth-Update Coupling / Layering TE · 🟡 Tier 2 · Score 3.2

**Cómo funciona (fácil).** Participantes independientes cotizando en varios niveles
del book producen cambios de tamaño casi independientes. Un **spoofer** que arma una
pared falsa postea y cancela órdenes grandes *coordinadas* en varios niveles del mismo
lado para simular presión. Esa coordinación se detecta con **información mutua** entre
los cambios de nivel: cuando salta sin agresión real detrás, es una pared falsa →
señal **contraria** (el precio irá al lado opuesto de la pared).

**Score.** Mecanismo 3.5 · Lag 2.5 (segundos–minutos) · Falsabilidad 3.5 · Costo test
2.0 (depth diffs, muy pesado) · Novedad 4.5 · Retorno 3.0. **⚠️ Fit bot bajo.**

**Cuánto podríamos ganar (prior).** Baja-media; mucho ruido y territorio HFT. La menos
prioritaria del lote.

**Qué hace falta.** Reconstruir @depth diffs; info mutua/transfer-entropy cross-nivel;
definir eventos de layering con baja agresión real; medir retorno forward 1/5/15 min
controlando por desbalance de agresor.

---

## 5. Estado de las validadas (contexto)

| # | Hipótesis | Veredicto | Números |
|---|---|---|---|
| **#6** | Funding Dispersion Collapse | ✅ **Edge chico pero real** (doble-verificado) | Backtest 1,34a: **+44%/año, Sharpe 2.0, maxDD −15%**, neto de fees+funding. Bate 8× al short indiscriminado (Sharpe 0.35) → el timing es real. **PERO** muestra de 1 solo régimen bajista + in-sample → expectativa realista descontada ~15–25%/año. Falta forward-test + muestra alcista. |
| **#7** | Coin-Margined Convexity | ❌ **No soportado / data insuficiente** | Binance solo da ~20–30d de OI histórico; en esa ventana el signo salió opuesto al thesis. Necesita fuente de OI larga (Coinglass/Coinalyze) para testear en serio. En pausa. |

> Detalle del método de #6/#7 y del estado de la ideación: ver memoria
> `signal-research-state`.

---

## 6. Recomendación (actualizada 2026-07-14 tras backtestear #1 y #2)

Estado del embudo Tier 1: **#2 refutada** (detector coincidente, no predictor); **#1
débil pero real** (Sharpe 0.43 — no operable sola, sí valiosa como filtro de régimen).

**Lección metodológica:** el score a priori (#2 tenía 4.3, el más alto) **no predijo
el resultado**. Confirma que el score ordena *qué probar*, no *qué gana* — el dato
manda. Dos de tres validadas (#2, #7) cayeron; el patrón hasta ahora es que los edges
sobrevivientes (#6, #1) son **reales pero chicos**, no máquinas de imprimir.

### Backtests adicionales (2026-07-14)

- **Combinar #6 + #1 (filtro de régimen) → ❌ NO MEJORA.** Filtrar el short de #6 por
  el régimen de #1 baja el Sharpe (1.81 baseline → 1.35 excl-concentrado / 1.41
  solo-difuso). #6 rinde parejo en todos los regímenes (retorno-short: concentrado
  +0.28% / neutro +0.53% / difuso +0.24%). **Hallazgo:** #6 es **robusta a régimen**,
  no necesita condicionamiento; los dos edges no son sinérgicos. Combinación cerrada.
- **Weekend/CME-gap reversal (del pool de 630) → ❌ REFUTADA.** IC +0.065 (signo
  equivocado: los findes *continúan*, no revierten), permutación p=0.86, P&L fadeando
  el finde −85% total / Sharpe −0.80. Descartada.

### Estado del embudo (6 hipótesis testeadas)

| Hipótesis | Veredicto |
|---|---|
| #6 Funding Dispersion | ✅ edge operable real (Sharpe ~1.8, robusto a régimen) |
| #1 Timezone Entropy | ⚠️ real pero flojo (Sharpe 0.43), no combina con #6 |
| #7 Coin-M Convexity | ❌ data insuficiente |
| #2 Peg Synchronization | ❌ detector coincidente, no predictor |
| #6+#1 combinación | ❌ no mejora |
| Weekend reversal | ❌ refutada |

**Lectura:** en cripto líquido los edges direccionales fáciles ya están arbitrados;
solo #6 sobrevive con edge operable. Seguir perforando ideas klines-only especulativas
tiene rendimiento decreciente (4 de las últimas 5 murieron).

### Recomendación (2026-07-14)

1. **Forward-test de #6 en demo** — es la ÚNICA con edge operable confirmado.
   Validarla en vivo fuera de muestra es el paso de mayor valor/riesgo-bajo.
2. **Ideas no-testeadas de mayor esfuerzo** (blob L2, microestructura order-book):
   requieren montar feeds de data nuevos; abordarlas solo si se decide invertir en eso.
3. **Dejar de perforar ideas klines-only especulativas** — el embudo muestra
   rendimiento decreciente.
