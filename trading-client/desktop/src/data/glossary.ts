// ─── Trading glossary for Alvora Academy ──────────────────────────────────────

export interface GlossaryTerm {
  term: string;
  category: "trading" | "crypto" | "technical" | "defi" | "risk" | "tax";
  definition: string;
  example?: string;
}

export const GLOSSARY_CATEGORIES = [
  "trading",
  "crypto",
  "technical",
  "defi",
  "risk",
  "tax",
] as const;

export const GLOSSARY_CATEGORY_LABELS: Record<string, string> = {
  trading: "Trading",
  crypto: "Crypto",
  technical: "Technical",
  defi: "DeFi",
  risk: "Risk",
  tax: "Tax",
};

export const GLOSSARY_TERMS: GlossaryTerm[] = [
  // ─── Trading (17) ────────────────────────────────────────────────────────────
  {
    term: "Bid",
    category: "trading",
    definition:
      "El precio máximo que un comprador está dispuesto a pagar por un activo. Representa la demanda en el order book.",
    example: "Si el bid de BTC es $49,000, alguien está dispuesto a comprar a ese precio.",
  },
  {
    term: "Ask",
    category: "trading",
    definition:
      "El precio mínimo al que un vendedor está dispuesto a vender un activo. Representa la oferta en el order book.",
    example: "Si el ask de BTC es $49,050, alguien está dispuesto a vender a ese precio.",
  },
  {
    term: "Spread",
    category: "trading",
    definition:
      "La diferencia entre el precio de compra (bid) y el precio de venta (ask). Un spread estrecho indica alta liquidez.",
    example: "Bid $49,000 - Ask $49,050 = Spread de $50.",
  },
  {
    term: "Slippage",
    category: "trading",
    definition:
      "La diferencia entre el precio esperado de una orden y el precio al que se ejecuta realmente. Ocurre en órdenes market con bajo volumen.",
    example: "Pides comprar a $50,000 pero se ejecuta a $50,020 → slippage de $20.",
  },
  {
    term: "Leverage",
    category: "trading",
    definition:
      "El uso de capital prestado para amplificar el tamaño de una posición. Multiplica tanto ganancias como pérdidas.",
    example: "Con 10x leverage, un movimiento del 1% se convierte en un 10% en tu P&L.",
  },
  {
    term: "Margin",
    category: "trading",
    definition:
      "El colateral necesario para abrir y mantener una posición con leverage. Puede ser initial margin o maintenance margin.",
    example: "Para una posición de $10,000 con 5x leverage, necesitas $2,000 de margin.",
  },
  {
    term: "Liquidation",
    category: "trading",
    definition:
      "El cierre forzoso de una posición con leverage cuando el margin cae por debajo del nivel mínimo requerido.",
    example: "Si tu maintenance margin es $500 y tu equity cae a $480, se liquida tu posición.",
  },
  {
    term: "Long",
    category: "trading",
    definition:
      "Abrir una posición de compra con la expectativa de que el precio suba. Ganancias si el precio aumenta.",
    example: "Ir long en BTC a $50,000 esperando que suba a $55,000.",
  },
  {
    term: "Short",
    category: "trading",
    definition:
      "Abrir una posición de venta con la expectativa de que el precio baje. Ganancias si el precio disminuye.",
    example: "Ir short en BTC a $50,000 esperando que baje a $45,000.",
  },
  {
    term: "Hedging",
    category: "trading",
    definition:
      "Estrategia de abrir una posición opuesta para reducir el riesgo de una posición existente.",
    example: "Si tienes BTC long, puedes abrir un short en futuros para hedge.",
  },
  {
    term: "Arbitrage",
    category: "trading",
    definition:
      "Aprovechar diferencias de precio del mismo activo en diferentes mercados para obtener ganancia sin riesgo.",
    example: "Comprar BTC a $49,000 en Binance y vender a $49,200 en OKX = $200 de profit.",
  },
  {
    term: "Order Book",
    category: "trading",
    definition:
      "Registro en tiempo real de todas las órdenes de compra y venta pendientes, organizadas por precio.",
    example: "Muestra bids y asks con sus respectivos volúmenes a cada lado.",
  },
  {
    term: "Market Maker",
    category: "trading",
    definition:
      "Participante que coloca órdenes limit que proporcionan liquidez al mercado. Cobra el spread como compensación.",
    example: "Coloca órdenes de compra y venta simultáneamente para capturar el spread.",
  },
  {
    term: "Taker",
    category: "trading",
    definition:
      "Participante que ejecuta órdenes market contra el order book, removiendo liquidez. Suele pagar comisiones más altas.",
    example: "Un taker compra con orden market al mejor ask disponible.",
  },
  {
    term: "Position",
    category: "trading",
    definition:
      "Una operación abierta en el mercado. Puede ser long o short, con un tamaño y un P&L no realizado.",
    example: "Tienes una posición long de 0.5 BTC con +$150 de P&L no realizado.",
  },
  {
    term: "Entry",
    category: "trading",
    definition:
      "El punto de precio al que abres una posición. Determina tu costo base y tu P&L inicial.",
    example: "Entry en $50,000 para una posición long de BTC.",
  },
  {
    term: "Exit",
    category: "trading",
    definition:
      "El punto de precio al que cierras una posición. Puede ser manual o automático vía stop-loss/take-profit.",
    example: "Exit en $55,000 con +10% de ganancia.",
  },

  // ─── Crypto (17) ─────────────────────────────────────────────────────────────
  {
    term: "Blockchain",
    category: "crypto",
    definition:
      "Un registro digital distribuido e inmutable que almacena transacciones en bloques encadenados criptográficamente.",
    example: "Bitcoin usa una blockchain donde cada bloque contiene transacciones verificadas.",
  },
  {
    term: "Bitcoin",
    category: "crypto",
    definition:
      "La primera criptomoneda descentralizada, creada en 2009 por Satoshi Nakamoto. Usa PoW y tiene un suministro máximo de 21 millones.",
    example: "BTC es el ticker de Bitcoin, la criptomoneda más grande por capitalización.",
  },
  {
    term: "Altcoin",
    category: "crypto",
    definition:
      "Cualquier criptomoneda que no es Bitcoin. Incluye Ethereum, Solana, Cardano, y miles más.",
    example: "ETH, SOL, ADA son altcoins populares.",
  },
  {
    term: "Token",
    category: "crypto",
    definition:
      "Un activo digital creado sobre una blockchain existente (no nativa). Puede representar utilidad, gobernanza, o activos.",
    example: "USDT es un token stablecoin sobre Ethereum, Tron, y otras blockchains.",
  },
  {
    term: "Stablecoin",
    category: "crypto",
    definition:
      "Criptomoneda cuyo valor está anclado a un activo estable, generalmente el dólar estadounidense.",
    example: "USDT, USDC, y DAI son stablecoins que mantienen un valor cercano a $1.",
  },
  {
    term: "Mining",
    category: "crypto",
    definition:
      "Proceso de validar transacciones y crear nuevos bloques en una blockchain PoW. Los mineros reciben recompensas en cripto.",
    example: "Los mineros de BTC usan hardware ASIC para resolver hashes y ganar BTC.",
  },
  {
    term: "Halving",
    category: "crypto",
    definition:
      "Evento programado en Bitcoin que reduce a la mitad la recompensa de minación. Ocurre cada ~4 años (cada 210,000 bloques).",
    example: "El halving de 2024 redujo la recompensa de 6.25 a 3.125 BTC por bloque.",
  },
  {
    term: "Gas",
    category: "crypto",
    definition:
      "La tarifa pagada para ejecutar transacciones o smart contracts en Ethereum. Varía según la congestión de la red.",
    example: "Transferir un token puede costar $2 de gas en época tranquila o $50 en congestion.",
  },
  {
    term: "Wallet",
    category: "crypto",
    definition:
      "Software o hardware que almacena las claves criptográficas para acceder y gestionar criptomonedas.",
    example: "MetaMask es un wallet software; Ledger es un wallet hardware.",
  },
  {
    term: "Seed Phrase",
    category: "crypto",
    definition:
      "Secuencia de 12-24 palabras que genera todas las claves de un wallet. Es el backup maestro: quien la tiene, controla los fondos.",
    example: "apple banana cherry dog elephant fox... (nunca compartas tu seed phrase).",
  },
  {
    term: "Public Key",
    category: "crypto",
    definition:
      "Dirección criptográfica que puedes compartir públicamente para recibir fondos. Derivada de la private key.",
    example: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bE1 es una public key de Ethereum.",
  },
  {
    term: "Private Key",
    category: "crypto",
    definition:
      "Clave secreta que autoriza transacciones. Quien la posee controla los fondos. NUNCA debe compartirse.",
    example: "Una private key se ve como: 5Kb8kLf9zgWQnogidDA76MzPL6TsZZY36hWXMssSzNydYXYB9KF",
  },
  {
    term: "Hash",
    category: "crypto",
    definition:
      "Función criptográfica que convierte datos de cualquier tamaño en una cadena de longitud fija. Usada para verificar integridad.",
    example: "SHA-256 produce un hash de 64 caracteres hexadecimales.",
  },
  {
    term: "Consensus",
    category: "crypto",
    definition:
      "Mecanismo por el cual los nodos de una blockchain acuerdan el estado de la red. Garantiza descentralización y seguridad.",
    example: "Bitcoin usa PoW, Ethereum usa PoS como mecanismos de consensus.",
  },
  {
    term: "Proof of Work (PoW)",
    category: "crypto",
    definition:
      "Mecanismo de consensus donde los mineros compiten resolciendo puzzles criptográficos. Seguro pero energéticamente intensivo.",
    example: "Bitcoin usa PoW: los mineros gastan energía computacional para validar bloques.",
  },
  {
    term: "Proof of Stake (PoS)",
    category: "crypto",
    definition:
      "Mecanismo de consensus donde los validadores bloquean (stake) cripto para validar bloques. Más eficiente que PoW.",
    example: "Ethereum 2.0 usa PoS: necesitas 32 ETH para ser validador.",
  },
  {
    term: "Smart Contract",
    category: "crypto",
    definition:
      "Programa auto-ejecutable en una blockchain que ejecuta reglas predefinidas sin intermediarios.",
    example: "Un smart contract de DEX ejecuta swaps automáticamente cuando se cumplen las condiciones.",
  },

  // ─── Technical (17) ───────────────────────────────────────────────────────────
  {
    term: "RSI (Relative Strength Index)",
    category: "technical",
    definition:
      "Oscilador de momentum que mide la velocidad y magnitud de los movimientos de precio. Rango 0-100. Sobrecompra >70, sobreventa <30.",
    example: "RSI de 25 indica sobreventa → posible rebote. RSI de 75 indica sobrecompra → posible corrección.",
  },
  {
    term: "MACD (Moving Average Convergence Divergence)",
    category: "technical",
    definition:
      "Indicador de momentum que muestra la relación entre dos EMAs. Compuesto por línea MACD, señal y histograma.",
    example: "Cruce alcista: línea MACD cruza por encima de la señal → señal de compra.",
  },
  {
    term: "EMA (Exponential Moving Average)",
    category: "technical",
    definition:
      "Media móvil que da más peso a los precios recientes. Reacciona más rápido que la SMA a los cambios de precio.",
    example: "EMA de 20 periodos sigue el precio más de cerca que la SMA de 20.",
  },
  {
    term: "SMA (Simple Moving Average)",
    category: "technical",
    definition:
      "Media móvil que calcula el promedio de precios en un periodo. Todos los precios tienen el mismo peso.",
    example: "SMA de 50 = promedio de los últimos 50 precios de cierre.",
  },
  {
    term: "Bollinger Bands",
    category: "technical",
    definition:
      "Indicador de volatilidad con tres líneas: SMA central y dos bandas a ±2 desviaciones estándar. El ancho refleja volatilidad.",
    example: "Bandas estrechas = baja volatilidad (squeeze). Bandas anchas = alta volatilidad.",
  },
  {
    term: "Fibonacci Retracement",
    category: "technical",
    definition:
      "Niveles de soporte/resistencia basados en ratios de Fibonacci (23.6%, 38.2%, 50%, 61.8%, 78.6%). Usados para identificar pullbacks.",
    example: "Tras un rally, el precio puede rebotar en el nivel 61.8% de Fibonacci.",
  },
  {
    term: "Candlestick",
    category: "technical",
    definition:
      "Representación visual de precio que muestra apertura, cierre, máximo y mínimo (OHLC) en un periodo. Verde/roja indica dirección.",
    example: "Una vela verde larga indica fuerte momentum alcista en ese periodo.",
  },
  {
    term: "Support",
    category: "technical",
    definition:
      "Nivel de precio donde la demanda es suficientemente fuerte para detener una caída. Actúa como un 'suelo' psicológico.",
    example: "BTC ha rebotado tres veces en $40,000 → ese es un nivel de support fuerte.",
  },
  {
    term: "Resistance",
    category: "technical",
    definition:
      "Nivel de precio donde la oferta es suficientemente fuerte para detener una subida. Actúa como un 'techo' psicológico.",
    example: "BTC ha fallado tres veces en romper $60,000 → ese es un nivel de resistance.",
  },
  {
    term: "Trendline",
    category: "technical",
    definition:
      "Línea diagonal dibujada conectando máximos o mínimos sucesivos. Muestra la dirección de la tendencia actual.",
    example: "Una trendline alcista conecta mínimos crecientes en un chart de BTC.",
  },
  {
    term: "Breakout",
    category: "technical",
    definition:
      "Movimiento de precio que rompe un nivel clave de soporte o resistencia, generalmente con aumento de volumen.",
    example: "BTC rompe resistance de $60,000 con alto volumen → breakout alcista.",
  },
  {
    term: "Pullback",
    category: "technical",
    definition:
      "Retroceso temporal del precio contra la tendencia principal. Ofrece oportunidades de entrada en tendencia.",
    example: "En una tendencia alcista, un pullback al EMA de 20 es una oportunidad de compra.",
  },
  {
    term: "Volume",
    category: "technical",
    definition:
      "Cantidad de un activo negociado en un periodo. Alto volumen confirma la fuerza de un movimiento de precio.",
    example: "Un breakout con volumen 3x superior al promedio es más confiable.",
  },
  {
    term: "OBV (On-Balance Volume)",
    category: "technical",
    definition:
      "Indicador que acumula volumen: suma volumen en días alcistas y resta en días bajistas. Detecta divergencias de flujo.",
    example: "Si el precio está plano pero OBV sube, hay acumulación silenciosa.",
  },
  {
    term: "ATR (Average True Range)",
    category: "technical",
    definition:
      "Indicador de volatilidad que mide el rango promedio de precio. Útil para ajustar stop-loss según volatilidad.",
    example: "ATR de $2,000 en BTC → un stop de 2x ATR sería $4,000.",
  },
  {
    term: "Stochastic Oscillator",
    category: "technical",
    definition:
      "Oscilador de momentum que compara el cierre actual con el rango de precios en un periodo. Rango 0-100.",
    example: "Stochastic por encima de 80 = sobrecompra; por debajo de 20 = sobreventa.",
  },
  {
    term: "VWAP (Volume Weighted Average Price)",
    category: "technical",
    definition:
      "Precio promedio ponderado por volumen. Usado por institucionales como benchmark de ejecución.",
    example: "Si el precio está por encima del VWAP, los compradores están en control.",
  },

  // ─── DeFi (13) ───────────────────────────────────────────────────────────────
  {
    term: "DEX (Decentralized Exchange)",
    category: "defi",
    definition:
      "Exchange descentralizado que opera sin intermediario mediante smart contracts. Permite trading peer-to-peer.",
    example: "Uniswap, PancakeSwap, y Curve son DEXs populares.",
  },
  {
    term: "Liquidity Pool",
    category: "defi",
    definition:
      "Reserva de tokens bloqueados en un smart contract que proporciona liquidez para trading en un DEX.",
    example: "Un pool ETH/USDT con $10M permite a los usuarios swap entre ETH y USDT.",
  },
  {
    term: "AMM (Automated Market Maker)",
    category: "defi",
    definition:
      "Mecanismo de pricing que usa una fórmula matemática (x*y=k) para determinar precios en un DEX sin order book.",
    example: "Uniswap usa AMM: el precio cambia automáticamente según el ratio del pool.",
  },
  {
    term: "Yield Farming",
    category: "defi",
    definition:
      "Estrategia de prestar o bloquear cripto en protocolos DeFi para ganar recompensas, generalmente tokens adicionales.",
    example: "Bloquear USDC en Aave para ganar 8% APY + tokens de gobernanza.",
  },
  {
    term: "Staking",
    category: "defi",
    definition:
      "Bloquear cripto en una red PoS para validar transacciones y ganar recompensas. Equivalente al mining en PoW.",
    example: "Stakear 32 ETH en Ethereum 2.0 para ganar ~4-6% APY.",
  },
  {
    term: "TVL (Total Value Locked)",
    category: "defi",
    definition:
      "Métrica que mide el total de activos bloqueados en un protocolo DeFi. Indica el tamaño y adopción del protocolo.",
    example: "Aave tiene $12B de TVL → es uno de los protocolos DeFi más grandes.",
  },
  {
    term: "Impermanent Loss",
    category: "defi",
    definition:
      "Pérdida temporal que ocurre cuando el precio de los tokens en un liquidity pool cambia respecto al momento de depósito.",
    example: "Si ETH sube 50% y tu pool ETH/USDT se reequilibra, pierdes vs. simplemente持有 ETH.",
  },
  {
    term: "Bridge",
    category: "defi",
    definition:
      "Protocolo que permite transferir activos entre diferentes blockchains. Conecta ecosistemas aislados.",
    example: "Un bridge ETH↔Solana permite mover USDC de Ethereum a Solana.",
  },
  {
    term: "Oracle",
    category: "defi",
    definition:
      "Servicio que proporciona datos externos a smart contracts. Esencial para DeFi que necesita precios en tiempo real.",
    example: "Chainlink es un oracle que alimenta precios a protocolos como Aave.",
  },
  {
    term: "Governance Token",
    category: "defi",
    definition:
      "Token que otorga derechos de voto en la gobernanza de un protocolo DeFi. Los holders deciden cambios y actualizaciones.",
    example: "UNI es el governance token de Uniswap: los holders votan propuestas.",
  },
  {
    term: "Liquidity Mining",
    category: "defi",
    definition:
      "Recompensar a los usuarios que proporcionan liquidez con tokens del protocolo. Incentiva la participación temprana.",
    example: "Proporcionar liquidez a un pool nuevo y recibir tokens del proyecto como recompensa.",
  },
  {
    term: "Slippage Tolerance",
    category: "defi",
    definition:
      "Configuración en DEXs que define el máximo deslizamiento de precio aceptable en un swap. Protege contra ejecuciones malas.",
    example: "Slippage tolerance de 1%: la transacción se revierte si el precio cambia más de 1%.",
  },
  {
    term: "Flash Loan",
    category: "defi",
    definition:
      "Préstamo sin colateral que debe ser devuelto en la misma transacción. Usado para arbitraje y refinanciamiento.",
    example: "Pedir $1M prestado, comprar en DEX A, vender en DEX B, devolver préstamo — todo en una tx.",
  },

  // ─── Risk (13) ───────────────────────────────────────────────────────────────
  {
    term: "Drawdown",
    category: "risk",
    definition:
      "La caída máxima desde un pico de equity hasta un valle. Mide la peor pérdida experimentada. Un drawdown del 50% requiere +100% para recuperarse.",
    example: "Si tu equity va de $10,000 a $6,000, el drawdown es del 40%.",
  },
  {
    term: "Sharpe Ratio",
    category: "risk",
    definition:
      "Métrica que mide el retorno ajustado al riesgo. (Retorno - Risk-free rate) / Desviación estándar. >1 es bueno, >2 es excelente.",
    example: "Sharpe de 1.5 significa que generas 1.5% de retorno por cada 1% de volatilidad.",
  },
  {
    term: "Sortino Ratio",
    category: "risk",
    definition:
      "Variante del Sharpe que solo considera volatilidad negativa (downside deviation). Más preciso para traders asimétricos.",
    example: "Sortino penaliza solo las pérdidas, no las ganancias, a diferencia del Sharpe.",
  },
  {
    term: "VaR (Value at Risk)",
    category: "risk",
    definition:
      "Estimación de la pérdida máxima esperada en un horizonte temporal con un nivel de confianza dado.",
    example: "VaR 95% de $1,000 → hay 95% de probabilidad de no perder más de $1,000 en un día.",
  },
  {
    term: "Kelly Criterion",
    category: "risk",
    definition:
      "Fórmula matemática para calcular el tamaño óptimo de posición basado en win rate y ratio riesgo/recompensa.",
    example: "Con 55% win rate y 1:2 R:R, Kelly sugiere arriesgar ~10% del capital por trade.",
  },
  {
    term: "Position Sizing",
    category: "risk",
    definition:
      "Determinar cuánto capital asignar a cada operación. La gestión del tamaño de posición es más importante que la selección de trades.",
    example: "Arriesgar 1% de $10,000 = $100 de riesgo máximo por operación.",
  },
  {
    term: "Risk/Reward Ratio",
    category: "risk",
    definition:
      "Relación entre la cantidad arriesgada y la cantidad potencial de ganancia. Un ratio de 1:2 significa arriesgar $1 para ganar $2.",
    example: "Entry $50k, stop $49k (risk $1k), target $52k (reward $2k) → R:R 1:2.",
  },
  {
    term: "Diversification",
    category: "risk",
    definition:
      "Distribuir el capital entre diferentes activos para reducir el riesgo no sistemático. 'No pongas todos los huevos en una canasta'.",
    example: "Portfolio: 40% BTC, 30% ETH, 20% altcoins, 10% stablecoins.",
  },
  {
    term: "Correlation",
    category: "risk",
    definition:
      "Medida estadística de cómo se mueven dos activos juntos. Correlación de +1 = movimiento idéntico, -1 = opuesto, 0 = independiente.",
    example: "BTC y ETH tienen correlación ~0.8 → se mueven mayormente juntos.",
  },
  {
    term: "Beta",
    category: "risk",
    definition:
      "Mide la volatilidad de un activo relativa al mercado. Beta >1 = más volátil que el mercado, <1 = menos volátil.",
    example: "Una altcoin con beta 2.5 se mueve 2.5x más que BTC en cada dirección.",
  },
  {
    term: "Alpha",
    category: "risk",
    definition:
      "El retorno excesivo de una estrategia respecto al benchmark. Alpha positivo indica que la estrategia supera al mercado.",
    example: "Si BTC sube 10% y tu estrategia sube 15%, tu alpha es +5%.",
  },
  {
    term: "Maximum Drawdown",
    category: "risk",
    definition:
      "La peor caída histórica desde un pico hasta un valle en la curva de equity. Métrica clave de riesgo de ruina.",
    example: "Max drawdown del 35% significa que en el peor momento perdiste 35% desde tu pico.",
  },
  {
    term: "Risk of Ruin",
    category: "risk",
    definition:
      "La probabilidad de perder todo el capital. Depende del win rate, ratio R:R, y tamaño de posición.",
    example: "Con 1% de riesgo por trade y 40% win rate, el risk of ruin es casi 0%.",
  },

  // ─── Tax (11) ─────────────────────────────────────────────────────────────────
  {
    term: "Capital Gains",
    category: "tax",
    definition:
      "Ganancia obtenida al vender un activo por más de su costo de adquisición. En cripto, se genera al vender, intercambiar, o usar.",
    example: "Comprar BTC a $30,000 y vender a $50,000 = $20,000 de capital gain.",
  },
  {
    term: "FIFO (First In, First Out)",
    category: "tax",
    definition:
      "Método contable donde las primeras unidades compradas se consideran las primeras vendidas. Puede generar mayores ganancias en mercados alcistas.",
    example: "Compras: 1 BTC a $20k, 1 BTC a $40k. Vendes 1 BTC → se usa el costo de $20k (FIFO).",
  },
  {
    term: "LIFO (Last In, First Out)",
    category: "tax",
    definition:
      "Método contable donde las últimas unidades compradas se consideran las primeras vendidas. Puede reducir ganancias en mercados alcistas.",
    example: "Compras: 1 BTC a $20k, 1 BTC a $40k. Vendes 1 BTC → se usa el costo de $40k (LIFO).",
  },
  {
    term: "HIFO (Highest In, First Out)",
    category: "tax",
    definition:
      "Método que usa las unidades con mayor costo de adquisición primero. Minimiza ganancias reportadas en ventas parciales.",
    example: "De tus compras a $20k, $40k, y $50k, al vender se usa el costo de $50k primero.",
  },
  {
    term: "Cost Basis",
    category: "tax",
    definition:
      "El precio de adquisición de un activo, más comisiones. Se usa para calcular la ganancia o pérdida al vender.",
    example: "Compras BTC a $40,000 + $10 de fee → cost basis = $40,010.",
  },
  {
    term: "Disposal Event",
    category: "tax",
    definition:
      "Cualquier evento que genera una obligación fiscal en cripto: venta, intercambio por otra cripto, o uso como pago.",
    example: "Cambiar BTC por ETH es un disposal event: debes reportar la ganancia del BTC.",
  },
  {
    term: "Short-term Capital Gains",
    category: "tax",
    definition:
      "Ganancias de activos mantenidos menos de un año. Generalmente tributadas a tasas ordinarias (más altas).",
    example: "Comprar BTC en enero y vender en junio → short-term gain, tasa ordinaria.",
  },
  {
    term: "Long-term Capital Gains",
    category: "tax",
    definition:
      "Ganancias de activos mantenidos más de un año. Generalmente tributadas a tasas preferenciales (más bajas).",
    example: "Comprar BTC en 2023 y vender en 2025 → long-term gain, tasa reducida.",
  },
  {
    term: "Wash Sale Rule",
    category: "tax",
    definition:
      "Regla que prohíbe deducir pérdidas si recompras el mismo o un activo 'sustancialmente idéntico' dentro de 30 días. Nota: no aplica oficialmente a cripto en EE.UU. (aún).",
    example: "Vender BTC con pérdida y recomprar en 5 días → la pérdida podría no ser deducible (acciones).",
  },
  {
    term: "Like-kind Exchange",
    category: "tax",
    definition:
      "Intercambio de activos similares sin generar evento fiscal inmediato. En EE.UU., ya no aplica a cripto desde 2018.",
    example: "Antes de 2018, algunos cambiaban BTC por ETH sin reportar. Ahora no es posible.",
  },
  {
    term: "Tax Loss Harvesting",
    category: "tax",
    definition:
      "Estrategia de vender activos con pérdida para compensar ganancias y reducir la carga fiscal.",
    example: "Vender altcoins perdedoras en diciembre para offsetear ganancias de BTC.",
  },
  // ─── Additional terms (12) ────────────────────────────────────────────────────
  {
    term: "FOMO",
    category: "trading",
    definition:
      "Fear Of Missing Out. Miedo a perderse una oportunidad. Lleva a comprar en máximos por impulsividad.",
    example: "BTC sube 20% en un día → compras por FOMO en el top → el precio cae.",
  },
  {
    term: "FUD",
    category: "trading",
    definition:
      "Fear, Uncertainty, Doubt. Noticias o rumores negativos que generan pánico y ventas irracionales.",
    example: "Un tweet falso sobre un hackeo de exchange genera FUD y el precio cae 10%.",
  },
  {
    term: "Rekt",
    category: "trading",
    definition:
      "Slang de trading que significa 'destruido' — perdiste una gran parte de tu capital en una operación.",
    example: "Abriste un long 10x en BTC y cayó 10% → te liquidaron → te rekt.",
  },
  {
    term: "DYOR",
    category: "crypto",
    definition:
      "Do Your Own Research. Haz tu propia investigación antes de invertir. No sigas ciegamente a influencers.",
    example: "Un influencer recomienda una altcoin → DYOR antes de comprar.",
  },
  {
    term: "HODL",
    category: "crypto",
    definition:
      "Estrategia de mantener criptomonedas a largo plazo sin importar la volatilidad. Originado de un typo de 'hold'.",
    example: "Compraste BTC en 2018 a $6k y lo HODLaste hasta 2021 → $60k.",
  },
  {
    term: "Fibonacci Retracement",
    category: "technical",
    definition:
      "Herramienta de análisis técnico que usa ratios matemáticos (23.6%, 38.2%, 50%, 61.8%, 78.6%) para identificar soportes y resistencias.",
    example: "BTC sube de $40k a $50k → retracement 61.8% = $43,820 (posible soporte).",
  },
  {
    term: "Bollinger Bands",
    category: "technical",
    definition:
      "Indicador de volatilidad: una SMA(20) central con dos bandas a ±2 desviaciones estándar. Bandas estrechas = baja volatilidad (squeeze).",
    example: "Bandas estrechas por días → squeeze → breakout inminente con alto volumen.",
  },
  {
    term: "Supertrend",
    category: "technical",
    definition:
      "Indicador de tendencia basado en ATR que cambia de color (verde/rojo) según la dirección. Línea verde = alcista, roja = bajista.",
    example: "Supertrend cambia a verde en 4h → señal de compra, stop-loss debajo de la línea.",
  },
  {
    term: "TVL",
    category: "defi",
    definition:
      "Total Value Locked. Valor total de activos depositados en un protocolo DeFi. Indica su tamaño y adopción.",
    example: "Aave TVL = $10B → es uno de los protocolos DeFi más grandes.",
  },
  {
    term: "Impermanent Loss",
    category: "defi",
    definition:
      "Pérdida que sufren los liquidity providers cuando el precio de los tokens en el pool cambia respecto al momento de depósito.",
    example: "Depositas ETH/USDC → ETH sube 100% → IL = ~5.7% vs simplemente HODL.",
  },
  {
    term: "Rug Pull",
    category: "defi",
    definition:
      "Estafa donde los creadores de un token/proyecto retiran toda la liquidez del pool, dejando a los inversores con tokens sin valor.",
    example: "Compras un token nuevo → los devs retiran liquidez → el token cae a $0.",
  },
  {
    term: "Sharpe Ratio",
    category: "risk",
    definition:
      "Medida de retorno ajustado al riesgo. Sharpe = (retorno - risk-free) / desviación estándar. >1 bueno, >2 excelente.",
    example: "Estrategia con 20% retorno y 10% volatilidad → Sharpe = 2.0 (excelente).",
  },
];

// ─── Helper functions ─────────────────────────────────────────────────────────

export function searchGlossary(query: string): GlossaryTerm[] {
  const q = query.toLowerCase();
  return GLOSSARY_TERMS.filter(
    (t) =>
      t.term.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q),
  );
}

export function getGlossaryByCategory(category: string): GlossaryTerm[] {
  return GLOSSARY_TERMS.filter((t) => t.category === category);
}

export function getSortedGlossary(
  category: string | "all",
): GlossaryTerm[] {
  const terms =
    category === "all" ? GLOSSARY_TERMS : getGlossaryByCategory(category);
  return [...terms].sort((a, b) => a.term.localeCompare(b.term));
}
