// ─── Tutorial data for Alvora Academy ─────────────────────────────────────────

export type TutorialCategory =
  | "Primeros pasos"
  | "Trading"
  | "Technical Analysis"
  | "Bots"
  | "Risk Management"
  | "DeFi"
  | "AI Trading"
  | "Psychology"
  | "Taxes";

export type Difficulty = "beginner" | "intermediate" | "advanced";

export type WidgetType =
  | "order-form"
  | "candlestick-patterns"
  | "support-resistance"
  | "moving-averages"
  | "rsi-macd"
  | "volume-profile"
  | "grid-bot-viz"
  | "dca-averaging"
  | "position-sizing"
  | "correlation-matrix"
  | "fibonacci-retracement"
  | "bollinger-bands"
  | "tax-calculator"
  | "wallet-safety"
  | "staking-calculator"
  | "ai-signal-card"
  | "market-regime"
  | "risk-reward"
  | "leverage-calculator"
  | "sl-tp-visualizer";

export interface TutorialStep {
  title: string;
  content: string;
  /** Interactive widget that simulates real Alvora UI for hands-on learning */
  widget?: WidgetType;
  /** @deprecated Use `widget` instead — kept for backward compat */
  codeExample?: string;
  actionLabel?: string;
  actionTarget?: string;
}

export interface Tutorial {
  id: string;
  title: string;
  category: TutorialCategory;
  difficulty: Difficulty;
  description: string;
  estimatedMinutes: number;
  xpReward: number;
  steps: TutorialStep[];
}

export const TUTORIALS: Tutorial[] = [
  // ─── 1. First Trade ─────────────────────────────────────────────────────────
  {
    id: "first_trade",
    title: "Tu Primera Operación en Alvora",
    category: "Primeros pasos",
    difficulty: "beginner",
    description: "Aprende a conectar tu exchange y realizar tu primera operación con Alvora.",
    estimatedMinutes: 10,
    xpReward: 75,
    steps: [
      {
        title: "Conectar tu Exchange",
        content:
          "Antes de operar, necesitas conectar tu exchange (Binance, OKX, o Bybit). Ve a la pestaña 'Connections' y haz clic en 'Add Connection'. Ingresa tu API key y secret. Tus claves se cifran con AES-256 y nunca se almacenan en texto plano.",
widget: "order-form",
      },
      {
        title: "Explorar el Dashboard",
        content:
          "El dashboard muestra tu equity total, P&L, posiciones abiertas, y señales del AI. Tómate unos minutos para familiarizarte con los widgets disponibles. Puedes personalizar el layout arrastrando y soltando widgets.",
      },
      {
        title: "Realizar tu Primera Operación",
        content:
          "Ve a la pestaña 'Trading'. Selecciona el par (ej. BTCUSDT), elige el tipo de orden (Market o Limit), ingresa la cantidad, y haz clic en 'Buy' o 'Sell'. Las órdenes Market se ejecutan inmediatamente al mejor precio disponible.",
widget: "order-form",
      },
      {
        title: "Monitorear tu Posición",
        content:
          "Después de operar, ve a 'Positions' para ver tu posición abierta. Verás el P&L no realizado en tiempo real. Puedes cerrar la posición parcial o totalmente desde esta pantalla.",
      },
    ],
  },

  // ─── 2. Grid Bot Explained ──────────────────────────────────────────────────
  {
    id: "grid_bot_explained",
    title: "Cómo Funciona un Grid Bot",
    category: "Bots",
    difficulty: "intermediate",
    description: "Entiende el grid trading y configura tu primer Grid Bot en Alvora.",
    estimatedMinutes: 15,
    xpReward: 125,
    steps: [
      {
        title: "¿Qué es Grid Trading?",
        content:
          "El grid trading divide un rango de precios en niveles (grid). Coloca órdenes de compra en los niveles inferiores y órdenes de venta en los niveles superiores. Cuando el precio sube, vende; cuando baja, compra. Genera beneficios de la volatilidad sin necesidad de predecir la dirección del mercado.",
widget: "grid-bot-viz",
      },
      {
        title: "Cuándo Usar Grid Trading",
        content:
          "El grid trading funciona mejor en mercados laterales (ranging markets) con alta volatilidad. En tendencias fuertes alcistas, el grid puede vender demasiado pronto. En tendencias bajistas, puede acumular posiciones perdedoras. Usa el filtro de régimen de mercado para activar el bot solo en condiciones adecuadas.",
      },
      {
        title: "Configurar tu Grid Bot",
        content:
          "Ve a la pestaña 'Bots' > 'Grid Bot'. Define el rango de precios (lower/upper), el número de grids, y la inversión total. El bot distribuirá tu capital entre los niveles automáticamente. Haz clic en 'Start' para activarlo.",
widget: "grid-bot-viz",
      },
      {
        title: "Monitorear el Rendimiento",
        content:
          "El dashboard del bot muestra órdenes colocadas, órdenes ejecutadas, P&L realizado, y el estado del grid. Puedes pausar o detener el bot en cualquier momento. Las órdenes pendientes se cancelan automáticamente al detener.",
      },
    ],
  },

  // ─── 3. Risk Management ─────────────────────────────────────────────────────
  {
    id: "risk_management",
    title: "Gestión de Riesgo para Traders",
    category: "Risk Management",
    difficulty: "intermediate",
    description: "Aprende las reglas de oro para proteger tu capital en cada operación.",
    estimatedMinutes: 12,
    xpReward: 125,
    steps: [
      {
        title: "La Regla del 1-2%",
        content:
          "Nunca arriesgues más del 1-2% de tu capital total en una sola operación. Si tienes $10,000, tu pérdida máxima por trade debería ser $100-$200. Esto te permite sobrevivir rachas perdedoras sin arruinarte.",
widget: "position-sizing",
      },
      {
        title: "Diversificación entre Activos",
        content:
          "No pongas todo tu capital en un solo activo. Diversifica entre BTC, ETH, y altcoins. Una buena regla: máximo 30% en un solo activo, máximo 60% en una sola categoría (ej. DeFi tokens). Alvora muestra alertas de concentración automáticamente.",
      },
      {
        title: "Stop-Loss y Take-Profit",
        content:
          "Siempre define tu stop-loss antes de entrar en una operación. NUNCA muevas el stop-loss más lejos para 'darle espacio'. Define también tu take-profit. Un ratio riesgo/recompensa de 1:2 significa que arriesgas $1 para ganar $2.",
widget: "position-sizing",
      },
      {
        title: "Drawdown Máximo",
        content:
          "El drawdown máximo es la mayor caída desde tu pico de equity. Un drawdown del 50% requiere un 100% de ganancia para recuperarse. Configura alertas de drawdown en Alvora para detener el trading si pierdes demasiado.",
      },
    ],
  },

  // ─── 4. SL/TP Basics ────────────────────────────────────────────────────────
  {
    id: "sl_tp_basics",
    title: "Stop-Loss y Take-Profit: Lo Básico",
    category: "Trading",
    difficulty: "beginner",
    description: "Domina las herramientas más importantes para proteger tus ganancias.",
    estimatedMinutes: 8,
    xpReward: 75,
    steps: [
      {
        title: "¿Qué es un Stop-Loss?",
        content:
          "Un stop-loss es una orden automática que cierra tu posición si el precio llega a un nivel determinado. Su función es limitar tus pérdidas. Sin stop-loss, una sola operación mala puede borrar semanas de ganancias.",
widget: "sl-tp-visualizer",
      },
      {
        title: "¿Qué es un Take-Profit?",
        content:
          "Un take-profit es una orden automática que cierra tu posición cuando alcanzas tu objetivo de ganancia. Te ayuda a asegurar ganancias sin dejarte llevar por la codicia. Muchos traders fallan por no tomar ganancias a tiempo.",
      },
      {
        title: "Trailing Stop: Maximizar Tendencias",
        content:
          "El trailing stop se mueve con el precio. Si el precio sube, el stop sube también. Si el precio baja, el stop se mantiene. Esto te permite capturar grandes tendencias mientras proteges ganancias acumuladas.",
widget: "sl-tp-visualizer",
      },
      {
        title: "Configurar SL/TP en Alvora",
        content:
          "Al crear una orden en Alvora, puedes configurar stop-loss y take-profit en la misma pantalla. También puedes añadirlos a posiciones existentes desde la pestaña 'Positions'. Los niveles se muestran visualmente en el chart.",
      },
    ],
  },

  // ─── 5. DCA Bot Explained ───────────────────────────────────────────────────
  {
    id: "dca_bot_explained",
    title: "DCA Bot: Inversión Sistemática",
    category: "Bots",
    difficulty: "beginner",
    description: "Aprende cómo el Dollar Cost Averaging reduce el impacto de la volatilidad.",
    estimatedMinutes: 10,
    xpReward: 100,
    steps: [
      {
        title: "¿Qué es DCA?",
        content:
          "Dollar Cost Averaging (DCA) es una estrategia donde compras una cantidad fija de un activo a intervalos regulares, sin importar el precio. Al comprar en momentos diferentes, promedias el costo de entrada y reduces el impacto de la volatilidad.",
widget: "dca-averaging",
      },
      {
        title: "Ventajas del DCA",
        content:
          "1. Elimina la necesidad de 'timing the market'. 2. Reduce el impacto emocional de la volatilidad. 3. Compra más cuando el precio está bajo y menos cuando está alto (automáticamente). 4. Ideal para inversores a largo plazo que creen en el activo.",
      },
      {
        title: "Configurar tu DCA Bot",
        content:
          "Ve a 'Bots' > 'DCA Bot'. Selecciona el símbolo, la cantidad de USD por compra, el intervalo (diario, semanal, mensual), y opcionalmente un take-profit porcentual. El bot ejecutará las compras automáticamente.",
widget: "dca-averaging",
      },
      {
        title: "DCA con Take-Profit",
        content:
          "Puedes configurar un take-profit en tu DCA bot. Cuando el promedio de todas tus compras sube X%, el bot vende todo y reinicia el ciclo. Esto convierte el DCA en una estrategia que genera flujo de caja regular.",
      },
    ],
  },

  // ─── 6. AI Trading Intro ────────────────────────────────────────────────────
  {
    id: "ai_trading_intro",
    title: "Introducción al AI Trading con Alvora",
    category: "AI Trading",
    difficulty: "advanced",
    description: "Descubre cómo el AI Copilot de Alvora puede mejorar tu trading.",
    estimatedMinutes: 15,
    xpReward: 150,
    steps: [
      {
        title: "¿Qué es el AI Copilot?",
        content:
          "Alvora incluye un AI Copilot impulsado por modelos de lenguaje avanzados. Analiza tu portfolio, señales técnicas, noticias, y datos on-chain para ofrecerte sugerencias proactivas. No es solo un chatbot: tiene acceso a tus datos reales de trading.",
widget: "ai-signal-card",
      },
      {
        title: "Conversar con Alvora",
        content:
          "Usa el panel de chat para hacer preguntas en lenguaje natural. Ejemplos: '¿Cómo está mi portfolio?', '¿Qué piensas de BTC ahora?', '¿Debería cerrar mi posición de ETH?'. El AI analiza tus datos y responde con contexto real.",
widget: "ai-signal-card",
      },
      {
        title: "Señales de AI",
        content:
          "El AI genera señales de trading basadas en análisis multi-factor: técnicos, sentimiento, on-chain, y macro. Cada señal incluye un nivel de confianza y un razonamiento. Las señales de alta confianza (>70%) son las más confiables.",
widget: "ai-signal-card",
      },
      {
        title: "Visual Strategy Builder",
        content:
          "Con el Visual Strategy Builder, puedes crear estrategias personalizadas sin programar. Arrastra bloques de entrada, salida, sizing, y filtros de riesgo. El AI puede sugerirte bloques basados en tu perfil de riesgo. Exporta tu estrategia a JSON o ejecuta un backtest directamente.",
widget: "ai-signal-card",
      },
      {
        title: "Auto-Pilot Mode",
        content:
          "El Auto-Pilot permite al AI ejecutar operaciones automáticamente basadas en tu estrategia configurada. Siempre puedes ver qué hace el AI en tiempo real y detenerlo en cualquier momento. Se recomienda empezar en modo paper trading antes de ir en vivo.",
      },
    ],
  },

  // ─── 7. What is Crypto ──────────────────────────────────────────────────────
  {
    id: "what_is_crypto",
    title: "Qué es Bitcoin y las Criptomonedas",
    category: "Primeros pasos",
    difficulty: "beginner",
    description: "Entiende qué son las criptomonedas, cómo funcionan y por qué existen.",
    estimatedMinutes: 8,
    xpReward: 50,
    steps: [
      {
        title: "¿Qué es Bitcoin?",
        content:
          "Bitcoin es una moneda digital descentralizada creada en 2009 por Satoshi Nakamoto. No está controlada por ningún gobierno o banco. Las transacciones se verifican por una red de computadoras usando criptografía. El suministro máximo es de 21 millones de bitcoins, lo que lo hace escaso y deflacionario.",
      },
      {
        title: "¿Qué es la Blockchain?",
        content:
          "Una blockchain es un libro contable público distribuido. Cada bloque contiene transacciones y está conectado al bloque anterior mediante un hash criptográfico. Esto hace que sea prácticamente imposible modificar transacciones pasadas. Cada nodo de la red mantiene una copia completa de la blockchain.",
      },
      {
        title: "Altcoins y Tokens",
        content:
          "Cualquier criptomoneda que no es Bitcoin se llama 'altcoin'. Ethereum (ETH) es la más conocida, pero hay miles. Los tokens viven sobre otra blockchain (ej. ERC-20 tokens sobre Ethereum). Los stablecoins (USDT, USDC) están pegados al dólar para reducir la volatilidad.",
widget: "wallet-safety",
      },
      {
        title: "Wallets y Claves",
        content:
          "Una wallet almacena tus claves privadas, no tus monedas (las monedas viven en la blockchain). Tu clave privada demuestra que eres dueño de los fondos. NUNCA compartas tu clave privada o seed phrase. Si la pierdes, pierdes acceso a tus fondos permanentemente.",
      },
    ],
  },

  // ─── 8. What is Trading ─────────────────────────────────────────────────────
  {
    id: "what_is_trading",
    title: "Qué es el Trading: Spot, Futures, Margin",
    category: "Primeros pasos",
    difficulty: "beginner",
    description: "Conoce los diferentes tipos de trading y cuál se adapta a ti.",
    estimatedMinutes: 10,
    xpReward: 50,
    steps: [
      {
        title: "¿Qué es el Trading?",
        content:
          "Trading es comprar y vender activos para obtener ganancias de las fluctuaciones de precio. A diferencia de invertir (largo plazo), el trading es a corto plazo. El objetivo es comprar barato y vender caro, o viceversa (short). Requiere disciplina, estrategia y gestión de riesgo.",
      },
      {
        title: "Spot Trading",
        content:
          "En spot trading compras y vendes el activo real. Si compras 1 BTC a $50,000 y sube a $55,000, ganas $5,000. No hay apalancamiento. Es el tipo más seguro de trading y el recomendado para principiantes.",
widget: "leverage-calculator",
      },
      {
        title: "Futures Trading",
        content:
          "Los futures son contratos que te obligan a comprar/vender un activo a un precio futuro. Permiten apalancamiento (ej. 10x significa que controlas $10,000 con $1,000). También permiten short (ganar cuando el precio baja). El apalancamiento amplifica ganancias Y pérdidas.",
      },
      {
        title: "Margin Trading",
        content:
          "Margin trading es pedir prestado dinero al exchange para operar con más capital del que tienes. Usas tu capital como garantía (margen). Si tu posición pierde demasiado, el exchange liquida tu posición automáticamente. El interés se paga sobre lo prestado.",
      },
      {
        title: "¿Cuál Elegir?",
        content:
          "Principiantes: empieza con SPOT, sin apalancamiento. Aprende a leer gráficos y gestionar riesgo antes de considerar futures. El 90% de traders novatos pierden dinero con apalancamiento. En Alvora puedes operar spot y futures desde la misma interfaz.",
      },
    ],
  },

  // ─── 9. Order Types ─────────────────────────────────────────────────────────
  {
    id: "order_types",
    title: "Tipos de Órdenes: Market, Limit, Stop, OCO",
    category: "Trading",
    difficulty: "beginner",
    description: "Domina los diferentes tipos de órdenes para ejecutar tus estrategias.",
    estimatedMinutes: 10,
    xpReward: 75,
    steps: [
      {
        title: "Market Order",
        content:
          "Una orden Market se ejecuta inmediatamente al mejor precio disponible. Es la más simple pero puede sufrir slippage en mercados poco líquidos. Úsala cuando la velocidad de ejecución sea más importante que el precio exacto.",
widget: "order-form",
      },
      {
        title: "Limit Order",
        content:
          "Una orden Limit se ejecuta solo a tu precio especificado o mejor. Buy limit: compra a tu precio o menos. Sell limit: vende a tu precio o más. Puede no ejecutarse si el precio no llega. Úsala cuando quieras un precio específico.",
widget: "sl-tp-visualizer",
      },
      {
        title: "Stop-Loss Order",
        content:
          "Un stop-loss se activa cuando el precio alcanza tu nivel de stop. Una vez activado, se convierte en una orden Market. Úsalo para limitar pérdidas automáticamente. Es la herramienta más importante de gestión de riesgo.",
widget: "sl-tp-visualizer",
      },
      {
        title: "OCO (One-Cancels-Other)",
        content:
          "OCO coloca dos órdenes: take-profit y stop-loss. Cuando una se ejecuta, la otra se cancela automáticamente. Perfecto para definir tu plan de salida antes de entrar. Alvora soporta OCO nativamente.",
widget: "order-form",
      },
      {
        title: "Órdenes en Alvora",
        content:
          "En la pestaña Trading de Alvora, puedes seleccionar el tipo de orden desde el formulario. Para limit y stop, verás el precio en el chart. Las órdenes OCO se configuran en la sección avanzada. Todas las órdenes se registran en la pestaña Orders.",
        actionLabel: "Ir a Trading",
        actionTarget: "trading",
      },
    ],
  },

  // ─── 10. Reading Charts ─────────────────────────────────────────────────────
  {
    id: "reading_charts",
    title: "Cómo Leer un Gráfico de Trading",
    category: "Trading",
    difficulty: "beginner",
    description: "Aprende a interpretar velas, timeframes y tendencias.",
    estimatedMinutes: 12,
    xpReward: 100,
    steps: [
      {
        title: "Timeframes",
        content:
          "Cada vela en un gráfico representa un periodo de tiempo. Timeframes cortos (1m, 5m, 15m) muestran más detalle pero más ruido. Timeframes largos (1d, 1w) muestran tendencias claras pero menos señales. Day traders usan 5m-1h; swing traders usan 4h-1d.",
widget: "candlestick-patterns",
      },
      {
        title: "Velas Japonesas",
        content:
          "Cada vela muestra 4 precios: apertura, cierre, máximo, mínimo. Vela verde (alcista): cierre > apertura. Vela roja (bajista): cierre < apertura. El cuerpo es la diferencia entre apertura y cierre. Las mechas (shadows) muestran el máximo y mínimo alcanzados.",
      },
      {
        title: "Tendencias",
        content:
          "Una tendencia alcista hace 'higher highs' y 'higher lows'. Una tendencia bajista hace 'lower highs' y 'lower lows'. Un mercado lateral se mueve en un rango. SIEMPRE opera a favor de la tendencia. 'The trend is your friend' es la regla #1 del trading.",
widget: "support-resistance",
      },
      {
        title: "Soporte y Resistencia Básico",
        content:
          "Soporte: nivel donde el precio tiende a rebotar al alza. Resistencia: nivel donde el precio tiende a rebotar a la baja. Estos niveles se forman donde ha habido mucho volumen de compra/venta en el pasado. Cuantas más veces el precio toca un nivel, más fuerte es.",
      },
      {
        title: "Volumen",
        content:
          "El volumen muestra cuántas unidades se negociaron en cada vela. Volumen alto confirma movimientos. Volumen bajo sugiere falta de interés. Un breakout con volumen alto es más confiable que uno con volumen bajo. El volumen es la segunda métrica más importante después del precio.",
        actionLabel: "Ver Charts",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 11. Candlestick Patterns ───────────────────────────────────────────────
  {
    id: "candlestick_patterns",
    title: "Patrones de Velas Japonesas",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "Aprende los patrones de velas más fiables para predecir movimientos.",
    estimatedMinutes: 15,
    xpReward: 100,
    steps: [
      {
        title: "Doji",
        content:
          "Un Doji tiene apertura y cierre casi iguales (cuerpo muy pequeño). Indica indecisión. Después de una tendencia alcista, sugiere posible reversión. Después de una bajista, posible suelo. La mecha larga muestra la lucha entre compradores y vendedores.",
widget: "candlestick-patterns",
      },
      {
        title: "Hammer y Hanging Man",
        content:
          "Hammer: vela con cuerpo pequeño arriba y mecha inferior larga. Aparece tras una tendencia bajista = señal de reversión alcista. Hanging Man: misma forma pero tras tendencia alcista = señal de reversión bajista. La mecha debe ser al menos 2x el cuerpo.",
      },
      {
        title: "Engulfing Patterns",
        content:
          "Bullish Engulfing: una vela roja pequeña seguida de una verde grande que la 'engulle' completamente. Bearish Engulfing: viceversa. Son de los patrones de reversión más fiables, especialmente en timeframes de 1h o mayor.",
widget: "candlestick-patterns",
      },
      {
        title: "Morning Star y Evening Star",
        content:
          "Morning Star: 3 velas — roja grande, pequeña con gap abajo, verde grande. Señal de reversión alcista. Evening Star: lo opuesto. Estos patrones de 3 velas son muy fiables cuando se confirman con volumen creciente.",
      },
      {
        title: "Consejos Prácticos",
        content:
          "1. Los patrones de velas funcionan mejor en timeframes de 1h+. 2. Nunca operes solo por un patrón — busca confirmación. 3. Combina con soporte/resistencia y volumen. 4. Un patrón en un nivel clave es 10x más valioso que uno en medio de la nada.",
        actionLabel: "Practicar en Chart Studio",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 12. Support and Resistance ─────────────────────────────────────────────
  {
    id: "support_resistance",
    title: "Soporte y Resistencia",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "Identifica los niveles clave donde el precio reacciona.",
    estimatedMinutes: 12,
    xpReward: 100,
    steps: [
      {
        title: "¿Qué es el Soporte?",
        content:
          "Soporte es un nivel de precio donde la presión compradora supera a la vendedora. El precio tiende a rebotar al alza al tocarlo. Se forma donde muchos traders tienen órdenes de compra o stop-loss de posiciones short.",
      },
      {
        title: "¿Qué es la Resistencia?",
        content:
          "Resistencia es un nivel donde la presión vendedora supera a la compradora. El precio tiende a rebotar a la baja. Se forma donde hay órdenes de venta acumuladas o take-profits de posiciones long.",
widget: "support-resistance",
      },
      {
        title: "Cómo Identificar Niveles",
        content:
          "1. Busca zonas donde el precio ha rebotado múltiples veces. 2. Cuantos más toques, más fuerte el nivel. 3. Niveles con alto volumen son más significativos. 4. Niveles redondos ($50k, $100k) actúan como soporte/resistencia psicológico. 5. Usa timeframes mayores para niveles más fiables.",
      },
      {
        title: "Breakout y Fakeout",
        content:
          "Breakout: el precio rompe un nivel con volumen alto. Fakeout: el precio lo rompe pero vuelve atrás (trampa). Para distinguirlos: espera a que el precio cierre por encima/debajo del nivel, no solo que lo toque. Confirma con volumen alto.",
      },
    ],
  },

  // ─── 13. Moving Averages ────────────────────────────────────────────────────
  {
    id: "moving_averages",
    title: "Medias Móviles: SMA, EMA, WMA",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "El indicador más usado: medias móviles para identificar tendencias.",
    estimatedMinutes: 12,
    xpReward: 100,
    steps: [
      {
        title: "SMA (Simple Moving Average)",
        content:
          "SMA calcula el promedio de los últimos N precios. SMA(50) = promedio de las últimas 50 velas. Suaviza el ruido del precio. Si el precio está sobre la SMA, hay tendencia alcista. Las SMAs más usadas: 20, 50, 100, 200.",
widget: "moving-averages",
      },
      {
        title: "EMA (Exponential Moving Average)",
        content:
          "EMA da más peso a los precios recientes. Reacciona más rápido que la SMA a cambios de precio. Los traders prefieren EMA para trading a corto plazo y SMA para análisis de tendencia a largo plazo. EMA(12) y EMA(26) se usan en el MACD.",
      },
      {
        title: "Cruces de Medias Móviles",
        content:
          "Golden Cross: EMA(50) cruza por encima de EMA(200) = señal alcista. Death Cross: EMA(50) cruza por debajo = señal bajista. Estos cruces son señales de largo plazo. Para corto plazo, usa cruces de EMA(9) con EMA(21).",
widget: "moving-averages",
      },
      {
        title: "Soporte/Resistencia Dinámico",
        content:
          "Las medias móviles actúan como soporte y resistencia dinámico. En tendencias alcistas, el precio suele rebotar en la EMA(20) o EMA(50). En bajistas, actúan como techo. Compra cuando el precio toque la EMA en una tendencia alcista confirmada.",
        actionLabel: "Ver en Chart Studio",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 14. RSI and MACD ────────────────────────────────────────────────────────
  {
    id: "rsi_macd",
    title: "RSI y MACD: Osciladores Clave",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "Los dos osciladores más populares para timing de entradas.",
    estimatedMinutes: 15,
    xpReward: 125,
    steps: [
      {
        title: "RSI (Relative Strength Index)",
        content:
          "RSI mide la velocidad y magnitud de los cambios de precio en una escala de 0-100. RSI > 70 = sobrecomprado (posible reversión bajista). RSI < 30 = sobrevendido (posible reversión alcista). El RSI(14) es el más usado.",
widget: "rsi-macd",
      },
      {
        title: "MACD (Moving Average Convergence Divergence)",
        content:
          "MACD muestra la diferencia entre EMA(12) y EMA(26). La línea de señal es EMA(9) del MACD. Cuando MACD cruza por encima de la señal = alcista. Por debajo = bajista. El histograma muestra la distancia entre ambos.",
widget: "rsi-macd",
      },
      {
        title: "Divergencias",
        content:
          "Una divergencia ocurre cuando el precio y el indicador se mueven en direcciones opuestas. Divergencia alcista: precio hace un mínimo más bajo pero RSI hace un mínimo más alto. Divergencia bajista: precio hace máximo más alto pero RSI hace máximo más bajo. Las divergencias son señales de reversión muy potentes.",
      },
      {
        title: "Combinar RSI y MACD",
        content:
          "Mejor estrategia: usa RSI para identificar sobrecompra/sobreventa y MACD para confirmar la dirección. Ejemplo: RSI < 30 (sobrevendido) + MACD cruza alcista = señal de compra fuerte. Nunca uses un solo indicador — la confirmación es clave.",
      },
      {
        title: "Configurar en Alvora",
        content:
          "En el Chart Studio de Alvora, puedes activar RSI y MACD desde el Indicator Picker. Ambos se muestran en paneles separados debajo del chart principal. Puedes ajustar los parámetros (periodo) según tu estrategia.",
        actionLabel: "Abrir Chart Studio",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 15. Chart Patterns ─────────────────────────────────────────────────────
  {
    id: "chart_patterns",
    title: "Patrones Gráficos: Triángulos, Banderas",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "Patrones de precio que predicen la dirección del siguiente movimiento.",
    estimatedMinutes: 15,
    xpReward: 125,
    steps: [
      {
        title: "Triángulos",
        content:
          "Triángulo ascendente: resistencia horizontal + soporte ascendente = breakout alcista probable. Triángulo descendente: soporte horizontal + resistencia descendente = breakout bajista probable. Simétrico: ambas líneas convergen = dirección incierta, opera el breakout.",
widget: "candlestick-patterns",
      },
      {
        title: "Banderas y Pennants",
        content:
          "Bull flag: fuerte movimiento alcista seguido de un canal bajista pequeño. Continuación alcista. Bear flag: lo opuesto. Pennant: similar pero con convergencia de líneas. Estos patrones de continuación son muy fiables cuando el volumen confirma.",
      },
      {
        title: "Cabeza y Hombros",
        content:
          "Head & Shoulders: tres picos donde el central es más alto. Línea de cuello (neckline) conecta los valles. Cuando el precio rompe la neckline, confirma reversión bajista. Inverse H&S: lo opuesto, señal alcista. Mide el objetivo proyectando la altura del patrón.",
widget: "support-resistance",
      },
      {
        title: "Doble Techo y Doble Suelo",
        content:
          "Doble techo (Double Top): precio toca resistencia dos veces y cae. Señal bajista. Doble suelo (Double Bottom): precio toca soporte dos veces y sube. Señal alcista. El objetivo es la altura del patrón proyectada desde el punto de breakout.",
      },
      {
        title: "Consejos Prácticos",
        content:
          "1. Los patrones funcionan mejor en timeframes de 1h+. 2. Espera a que el precio rompa el patrón con volumen. 3. Usa stop-loss justo debajo/de encima del patrón. 4. Los patrones de continuación son más fiables que los de reversión. 5. Combina con RSI y MACD para confirmación.",
        actionLabel: "Practicar en Chart Studio",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 16. Volume Analysis ────────────────────────────────────────────────────
  {
    id: "volume_analysis",
    title: "Análisis de Volumen y OBV",
    category: "Technical Analysis",
    difficulty: "intermediate",
    description: "El volumen confirma o niega los movimientos de precio.",
    estimatedMinutes: 12,
    xpReward: 100,
    steps: [
      {
        title: "Por qué el Volumen Importa",
        content:
          "El volumen es la fuerza detrás del movimiento de precio. Precio sube con volumen alto = movimiento fuerte. Precio sube con volumen bajo = movimiento débil, posible fake. Volumen creciente en la dirección de la tendencia confirma su fuerza.",
widget: "volume-profile",
      },
      {
        title: "OBV (On-Balance Volume)",
        content:
          "OBV acumula volumen: suma volumen cuando el precio cierra positivo, resta cuando cierra negativo. OBV subiendo = acumulación (compradores fuertes). OBV bajando = distribución (vendedores fuertes). Divergencia entre OBV y precio es señal de reversión.",
      },
      {
        title: "Volume Profile",
        content:
          "Volume Profile muestra el volumen por nivel de precio (no por tiempo). Los niveles con más volumen actúan como soporte/resistencia fuerte. POC (Point of Control) = nivel con más volumen. El precio tiende a volver al POC cuando no hay tendencia clara.",
widget: "volume-profile",
      },
      {
        title: "Señales de Volumen",
        content:
          "1. Breakout con volumen 2x+ del promedio = fiable. 2. Volumen que disminuye durante una tendencia = tendencia perdiendo fuerza. 3. Pico de volumen tras un movimiento largo = posible clímax. 4. Volumen alto en soporte/resistencia = nivel fuerte.",
        actionLabel: "Ver Volumen en Charts",
        actionTarget: "chart-studio",
      },
    ],
  },

  // ─── 17. Bot Backtesting ────────────────────────────────────────────────────
  {
    id: "bot_backtesting",
    title: "Backtesting de Bots: Valida tu Estrategia",
    category: "Bots",
    difficulty: "intermediate",
    description: "Aprende a probar tus bots con datos históricos antes de arriesgar dinero.",
    estimatedMinutes: 12,
    xpReward: 125,
    steps: [
      {
        title: "¿Qué es el Backtesting?",
        content:
          "Backtesting ejecuta tu estrategia sobre datos históricos para ver cómo habría funcionado. Te muestra ROI, drawdown máximo, win rate, y Sharpe ratio. Es obligatorio antes de usar un bot en vivo. Un bot sin backtest es una apuesta ciega.",
widget: "grid-bot-viz",
      },
      {
        title: "Configurar un Backtest en Alvora",
        content:
          "Ve a Backtest, selecciona la estrategia, símbolo, intervalo, y rango de fechas. Alvora descarga datos históricos y simula la ejecución. Puedes ajustar parámetros como comisiones y slippage para mayor realismo. Los resultados se muestran con gráficos de equity curve.",
        actionLabel: "Ir a Backtest",
        actionTarget: "backtest",
      },
      {
        title: "Interpretar Resultados",
        content:
          "ROI alto con drawdown bajo = buena estrategia. ROI alto con drawdown alto = estrategia arriesgada. Win rate del 40-60% es normal; no busques 90%. Sharpe > 1 es bueno, > 2 es excelente. Profit factor > 1.5 es aceptable. Cuidado con overfitting.",
widget: "grid-bot-viz",
      },
      {
        title: "Overfitting: El Enemigo #1",
        content:
          "Overfitting = optimizar parámetros hasta que el backtest se ve perfecto, pero en vivo no funciona. Síntomas: ROI irreal (>200%), win rate >80%, resultados que cambian drásticamente con pequeños cambios de parámetros. Solución: usa walk-forward analysis y datos out-of-sample.",
      },
    ],
  },

  // ─── 18. Bot Optimization ───────────────────────────────────────────────────
  {
    id: "bot_optimization",
    title: "Optimización con Monte Carlo",
    category: "Bots",
    difficulty: "advanced",
    description: "Usa simulación Monte Carlo para evaluar la robustez de tus estrategias.",
    estimatedMinutes: 15,
    xpReward: 150,
    steps: [
      {
        title: "¿Qué es Monte Carlo?",
        content:
          "Monte Carlo simula miles de escenarios aleatorios basados en tus trades históricos. En lugar de un solo backtest, obtienes una distribución de resultados posibles. Te dice: ¿cuál es la probabilidad de perder X%? ¿Cuál es el peor escenario realista?",
      },
      {
        title: "Por qué es Mejor que un Backtest Simple",
        content:
          "Un backtest te da un resultado. Monte Carlo te da un rango. El orden de tus trades importa: 10 pérdidas seguidas al inicio puede liquidarte, incluso si el resultado total es positivo. Monte Carlo modela este riesgo secuencial.",
      },
      {
        title: "Monte Carlo en Alvora",
        content:
          "Alvora incluye simulación Monte Carlo en la pestaña Backtest. Selecciona tu estrategia, ejecuta el backtest, y luego haz clic en 'Monte Carlo'. Verás un gráfico con múltiples equity curves y estadísticas de riesgo: max drawdown percentil 95, probabilidad de ruina, y más.",
        actionLabel: "Probar Monte Carlo",
        actionTarget: "backtest",
      },
      {
        title: "Interpretar Resultados",
        content:
          "Mira el percentil 5 (peor caso realista). Si muestra -30% drawdown, prepárate para eso. Probabilidad de ruina > 5% = estrategia demasiado arriesgada. El percentil 50 (mediana) es tu resultado más probable. Usa estos datos para dimensionar tu posición.",
      },
    ],
  },

  // ─── 19. Strategy Builder ───────────────────────────────────────────────────
  {
    id: "strategy_builder",
    title: "Visual Strategy Builder sin Código",
    category: "Bots",
    difficulty: "intermediate",
    description: "Crea estrategias de trading arrastrando bloques visuales.",
    estimatedMinutes: 15,
    xpReward: 150,
    steps: [
      {
        title: "Cómo Funciona",
        content:
          "El Visual Strategy Builder te permite crear estrategias sin programar. Arrastra bloques de 4 categorías: Entry (cuándo comprar), Exit (cuándo vender), Sizing (cuánto comprar), y Risk (filtros de seguridad). Los bloques se conectan visualmente en un canvas.",
widget: "grid-bot-viz",
      },
      {
        title: "Tu Primera Estrategia",
        content:
          "Ejemplo: Entry = RSI < 30 (sobrevendido). Exit = Take Profit 5% + Stop Loss 2%. Sizing = 2% del portfolio. Risk = máximo 3 posiciones simultáneas. Esta estrategia simple compra cuando RSI está sobrevendido y vende con 5% de ganancia o 2% de pérdida.",
widget: "grid-bot-viz",
      },
      {
        title: "Validar y Backtest",
        content:
          "Antes de ejecutar, valida tu estrategia. El builder comprueba que tenga al menos un Entry, un Exit, y un Sizing. Luego puedes hacer backtest directamente desde el builder. Si los resultados son buenos, puedes publicar la estrategia en el Marketplace.",
        actionLabel: "Abrir Strategy Builder",
        actionTarget: "strategy-builder",
      },
      {
        title: "Estrategias Avanzadas",
        content:
          "Combina múltiples bloques: Entry = MA cross + RSI confirmación + AI signal. Exit = Trailing stop + Time exit (cerrar después de 7 días). Sizing = Kelly criterion. Risk = Market regime filter (solo operar en tendencia). Cuantos más filtros, más conservadora la estrategia.",
      },
      {
        title: "Publicar en Marketplace",
        content:
          "Si tu estrategia tiene buenos resultados en backtest, puedes publicarla en el Strategy Marketplace. Otros usuarios pueden suscribirse (free o premium). Recibirás reseñas y ratings. Es una forma de monetizar tu conocimiento de trading.",
        actionLabel: "Ver Marketplace",
        actionTarget: "marketplace",
      },
    ],
  },

  // ─── 20. Position Sizing ────────────────────────────────────────────────────
  {
    id: "position_sizing",
    title: "Position Sizing: Kelly, Fijo, Porcentual",
    category: "Risk Management",
    difficulty: "advanced",
    description: "La habilidad más importante: cuánto comprar/vender en cada operación.",
    estimatedMinutes: 15,
    xpReward: 150,
    steps: [
      {
        title: "Por qué el Position Sizing es #1",
        content:
          "Van Tharp demostró que el position sizing determina el 90% de los resultados de trading. Puedes tener una estrategia con 40% de win rate y ganar dinero si dimensionas bien, o perder con 70% de win rate si dimensionas mal. Es más importante que la estrategia misma.",
      },
      {
        title: "Position Sizing Fijo",
        content:
          "Arriesgas una cantidad fija por trade, ej. $100. Simple pero no se adapta al crecimiento de tu cuenta. Si tu cuenta crece de $10k a $20k, $100 de riesgo es solo 0.5% (muy conservador). Si cae a $5k, $100 es 2% (demasiado arriesgado).",
widget: "position-sizing",
      },
      {
        title: "Position Sizing Porcentual",
        content:
          "Arriesgas un % fijo de tu cuenta, ej. 1%. Si tienes $10,000, arriesgas $100. Si tu cuenta crece a $12,000, arriesgas $120. Se adapta automáticamente. Es el método más recomendado. La regla del 1-2% usa este método.",
widget: "position-sizing",
      },
      {
        title: "Kelly Criterion",
        content:
          "Kelly formula calcula el tamaño óptimo basado en tu win rate y ratio R:R. f = W - (1-W)/R, donde W = win rate, R = win/loss ratio. Ejemplo: 55% win rate, R:R 1.5: f = 0.55 - 0.45/1.5 = 0.25 (25% de la cuenta). Demasiado agresivo; usa 'Half Kelly' (12.5%).",
widget: "position-sizing",
      },
      {
        title: "Cuál Usar",
        content:
          "Principiantes: 1% porcentual (simple y seguro). Intermedios: 1-2% porcentual con ajuste por confianza. Avanzados: Half Kelly con cap del 5%. NUNCA uses Full Kelly — es demasiado volátil. En Alvora, el position sizing se configura en la sección Risk de cada estrategia o bot.",
      },
    ],
  },

  // ─── 21. Portfolio Correlation ──────────────────────────────────────────────
  {
    id: "portfolio_correlation",
    title: "Correlación y Diversificación",
    category: "Risk Management",
    difficulty: "advanced",
    description: "No diversificar es arriesgar todo en una sola dirección.",
    estimatedMinutes: 12,
    xpReward: 150,
    steps: [
      {
        title: "¿Qué es la Correlación?",
        content:
          "Correlación mide cómo se mueven dos activos juntos. Correlación +1 = se mueven idénticos. Correlación -1 = se mueven opuestos. Correlación 0 = sin relación. BTC y ETH tienen correlación ~0.85 (muy alta). BTC y oro tienen correlación ~0.1 (baja).",
widget: "correlation-matrix",
      },
      {
        title: "Por qué Importa",
        content:
          "Si tienes BTC, ETH, y SOL, no estás diversificado — todos caen juntos. Una caída de BTC arrastrará todo tu portfolio. Diversificación real requiere activos con baja correlación: crypto + stablecoins + oro + acciones. Alvora muestra la correlación en el Portfolio Heatmap.",
      },
      {
        title: "Diversificación Efectiva",
        content:
          "1. No más del 40% en un solo activo. 2. Combina activos con correlación < 0.5. 3. Incluye stablecoins como refugio. 4. Considera activos no-crypto (oro, S&P500). 5. Revisa la correlación mensualmente — cambia con el tiempo. En crisis, todo tiende a correlacionar +1.",
widget: "correlation-matrix",
      },
      {
        title: "Correlación en Crisis",
        content:
          "En mercados normales, la correlación es moderada. En crisis, TODO cae junto (correlación → 1). Esto se llama 'contagio'. Por eso los stop-loss son cruciales: no puedes depender de la diversificación sola durante un crash. Alvora detecta aumento de correlación y alerta.",
        actionLabel: "Ver Portfolio",
        actionTarget: "dashboard",
      },
    ],
  },

  // ─── 22. DeFi Basics ────────────────────────────────────────────────────────
  {
    id: "defi_basics",
    title: "Qué es DeFi: Uniswap, Aave, Compound",
    category: "DeFi",
    difficulty: "intermediate",
    description: "Introducción a las finanzas descentralizadas y sus principales protocolos.",
    estimatedMinutes: 15,
    xpReward: 125,
    steps: [
      {
        title: "¿Qué es DeFi?",
        content:
          "DeFi (Decentralized Finance) son servicios financieros sin bancos. Funcionan mediante smart contracts en blockchains como Ethereum. No hay intermediarios: tú interactúas directamente con el protocolo. Ventajas: 24/7, sin KYC, transparente. Riesgos: bugs en smart contracts, impermanent loss.",
      },
      {
        title: "Uniswap (DEX)",
        content:
          "Uniswap es el exchange descentralizado más grande. Permite intercambiar tokens sin order book usando AMM (Automated Market Maker). Los usuarios proveen liquidez a pools y ganan comisiones. Cada swap tiene un fee del 0.3% que se distribuye a los liquidity providers.",
widget: "staking-calculator",
      },
      {
        title: "Aave (Lending)",
        content:
          "Aave permite prestar y pedir prestado crypto sin banco. Depositas USDC y ganas interés. Puedes pedir prestado usando tu crypto como colateral. Las tasas de interés son dinámicas (basadas en oferta/demanda). Aave ha procesado miles de millones en préstamos sin un solo intermediario.",
      },
      {
        title: "Compound (Lending)",
        content:
          "Compound es similar a Aave. Depositas activos y recibes cTokens (tokens que representan tu depósito + interés). Los intereses se acumulan automáticamente en cada bloque. El governance token COMP permite votar en decisiones del protocolo.",
      },
      {
        title: "DeFi en Alvora",
        content:
          "Alvora incluye una pestaña DeFi donde puedes conectar tu wallet, ver tus balances ERC-20, posiciones en Aave/Uniswap, y hacer swaps en DEXs vía 0x API. También verás analytics on-chain: TVL, gas tracker, y whale movements.",
        actionLabel: "Explorar DeFi",
        actionTarget: "defi",
      },
    ],
  },

  // ─── 23. Wallet Safety ──────────────────────────────────────────────────────
  {
    id: "wallet_safety",
    title: "Seguridad de Wallets: Hot vs Cold",
    category: "DeFi",
    difficulty: "beginner",
    description: "Protege tus criptomonedas con las prácticas de seguridad correctas.",
    estimatedMinutes: 10,
    xpReward: 100,
    steps: [
      {
        title: "Hot Wallets",
        content:
          "Hot wallets están conectadas a internet (MetaMask, Trust Wallet, Phantom). Convenientes para uso diario y DeFi. Riesgo: si tu dispositivo se compromete, tus fondos pueden ser robados. NUNCA guardes grandes cantidades en una hot wallet.",
widget: "wallet-safety",
      },
      {
        title: "Cold Wallets",
        content:
          "Cold wallets (hardware wallets) están offline (Ledger, Trezor, GridPlus). Tus claves privadas nunca tocan internet. Para transacciones, firmas offline y luego transmites. Es el estándar de seguridad para almacenar grandes cantidades de crypto.",
widget: "wallet-safety",
      },
      {
        title: "Seed Phrase Security",
        content:
          "Tu seed phrase (12-24 palabras) es la clave maestra de tu wallet. Si alguien la obtiene, roba todos tus fondos. Reglas: 1. Escríbela en papel (no digital). 2. Guárdala en 2+ ubicaciones seguras. 3. NUNCA la pongas en internet, fotos, o cloud. 4. Considera grabarla en metal para resistir fuego/agua.",
widget: "wallet-safety",
      },
      {
        title: "Reglas de Oro",
        content:
          "1. Verifica siempre la URL antes de conectar tu wallet. 2. No hagas clic en links sospechosos. 3. Usa 2FA en todos los exchanges. 4. Separa hot y cold wallets. 5. Revisa permisos de smart contracts regularmente (revoke.cash). 6. Desconfía de DMs y ofertas demasiado buenas.",
        actionLabel: "Ver Seguridad",
        actionTarget: "security",
      },
    ],
  },

  // ─── 24. DEX Trading ────────────────────────────────────────────────────────
  {
    id: "dex_trading",
    title: "Trading en DEXs: Slippage e Impermanent Loss",
    category: "DeFi",
    difficulty: "advanced",
    description: "Entiende los riesgos únicos del trading en exchanges descentralizados.",
    estimatedMinutes: 15,
    xpReward: 150,
    steps: [
      {
        title: "Slippage en DEXs",
        content:
          "Slippage = diferencia entre el precio esperado y el precio real de ejecución. En DEXs, los pools pequeños tienen más slippage. Un swap de $100k en un pool de $500k moverá el precio significativamente. Configura slippage tolerance para evitar ejecuciones malas.",
      },
      {
        title: "Impermanent Loss (IL)",
        content:
          "IL afecta a liquidity providers. Cuando el precio de los tokens en el pool cambia, el valor de tu posición es menor que si simplemente hubieras mantenido los tokens. Es 'impermanent' porque solo se realiza si retiras la liquidez. Cuanto mayor el cambio de precio, mayor el IL.",
      },
      {
        title: "MEV y Front-Running",
        content:
          "MEV (Maximal Extractable Value): bots monitorizan la mempool y 'adelantan' tus transacciones. Si compras un token, el bot compra primero (subiendo el precio) y te vende más caro. Solución: usa MEV protection (Flashbots, 0x API con RFQ) o transacciones privadas.",
      },
      {
        title: "Mejores Prácticas",
        content:
          "1. Usa slippage tolerance del 0.5-1% para tokens líquidos. 2. Para tokens poco líquidos, usa 3-5%. 3. Verifica el contrato del token antes de comprar (rug pulls). 4. Usa 0x API o 1inch para mejor routing. 5. Considera gas costs en transacciones pequeñas. 6. No proveas liquidez sin entender IL.",
      },
      {
        title: "DEX Trading en Alvora",
        content:
          "Alvora integra 0x API para swaps en DEXs. En la pestaña DeFi, puedes obtener quotes, ver gas estimado, y preparar transacciones. Los swaps se ejecutan desde tu wallet conectada. Alvora muestra el routing (qué DEXs se usan) y los fees.",
        actionLabel: "Probar DEX Swap",
        actionTarget: "defi",
      },
    ],
  },

  // ─── 25. Staking and Liquidity ──────────────────────────────────────────────
  {
    id: "staking_liquidity",
    title: "Staking y Liquidity Mining",
    category: "DeFi",
    difficulty: "intermediate",
    description: "Gana rendimientos pasivos con tus criptomonedas.",
    estimatedMinutes: 12,
    xpReward: 125,
    steps: [
      {
        title: "¿Qué es Staking?",
        content:
          "Staking = bloquear tus tokens para asegurar una red Proof-of-Stake (PoS). A cambio, recibes recompensas. Ethereum, Solana, Cardano usan PoS. El APY varía: 4-10% en Ethereum, 5-8% en Solana. Staking reduce el suministro circulante, lo que puede subir el precio.",
widget: "staking-calculator",
      },
      {
        title: "Liquidity Mining (Yield Farming)",
        content:
          "Liquidity mining = proveer liquidez a un DEX y recibir tokens de gobernanza como recompensa. Además de las comisiones del pool (0.3%), recibes tokens extra. APY puede ser 20-100%+ pero los tokens de gobernanza pueden perder valor. Riesgo: impermanent loss + token depreciation.",
      },
      {
        title: "Lido y Rocket Pool",
        content:
          "Lido permite staking líquido: depositas ETH y recibes stETH (que puedes usar en DeFi). No necesitas 32 ETH ni ser validator. stETH sube de valor diariamente con las recompensas. Rocket Pool es similar pero más descentralizado. Ambos ofrecen ~4-5% APY.",
widget: "staking-calculator",
      },
      {
        title: "Riesgos",
        content:
          "1. Smart contract risk (bugs pueden perder tus fondos). 2. Slashing (validators malos pierden stake). 3. Impermanent loss (liquidity mining). 4. Token depreciation (APY alto pero token cae). 5. Lock-up periods (no puedes vender). Diversifica entre protocolos y no persigas APYs irreales (>100%).",
        actionLabel: "Ver DeFi",
        actionTarget: "defi",
      },
    ],
  },

  // ─── 26. AI Signals ─────────────────────────────────────────────────────────
  {
    id: "ai_signals",
    title: "Cómo Interpretar Señales de AI",
    category: "AI Trading",
    difficulty: "advanced",
    description: "Aprende a leer y usar las señales generadas por el AI de Alvora.",
    estimatedMinutes: 12,
    xpReward: 150,
    steps: [
      {
        title: "Anatomía de una Señal",
        content:
          "Cada señal de AI incluye: símbolo, dirección (long/short), nivel de confianza (0-100), razonamiento, entry price, stop-loss, y take-profit. La confianza indica qué tan seguro está el AI. Señales >70% son de alta confianza. El razonamiento explica qué factores técnicos, on-chain, y de sentimiento llevaron a la señal.",
widget: "ai-signal-card",
      },
      {
        title: "Niveles de Confianza",
        content:
          "70-100%: señal de alta confianza — considera ejecutar. 50-70%: señal moderada — usa confirmación adicional. <50%: señal débil — no operar solo por esto. La confianza NO es garantía de éxito. Incluso señales del 90% pueden fallar. Usa position sizing basado en confianza.",
widget: "ai-signal-card",
      },
      {
        title: "Factores que Analiza el AI",
        content:
          "El AI de Alvora analiza: 1. Técnicos (RSI, MACD, MA, volumen). 2. Sentimiento (news, social media). 3. On-chain (whale movements, exchange flows). 4. Macro (DXY, rates, correlation). 5. Funding rates y open interest. Cada factor tiene un peso que el AI ajusta según el régimen de mercado.",
      },
      {
        title: "Confirmación y Filtros",
        content:
          "No ejecutes señales a ciegas. Confirma con: 1. Precio cerca del entry sugerido. 2. Volumen confirmando la dirección. 3. No hay noticias contradictorias. 4. Market regime favorable (no operar long en tendencia bajista fuerte). 5. Correlación con BTC/ETH no adversa. El AI es una herramienta, no un oráculo.",
        actionLabel: "Ver Inteligencia",
        actionTarget: "intelligence",
      },
    ],
  },

  // ─── 27. Copilot Mastery ────────────────────────────────────────────────────
  {
    id: "copilot_mastery",
    title: "Dominando el Alvora Copilot",
    category: "AI Trading",
    difficulty: "intermediate",
    description: "Saca el máximo provecho del AI Copilot con prompts efectivos.",
    estimatedMinutes: 12,
    xpReward: 125,
    steps: [
      {
        title: "Qué Puede Hacer el Copilot",
        content:
          "El Copilot puede: analizar tu portfolio, sugerir trades, explicar señales, ajustar bots, responder preguntas de mercado, generar reportes, y ejecutar órdenes con tu confirmación. Tiene acceso a tus datos reales: posiciones, P&L, historial de trades, y configuración de bots.",
      },
      {
        title: "Prompts Efectivos",
        content:
          "Sé específico. En vez de '¿Qué hago?', pregunta '¿Debería cerrar mi posición de ETH de 2 ETH comprada a $3200 ahora que está en $2900, considerando que RSI está sobrevendido?'. Cuanto más contexto des, mejor será la respuesta. El AI usa tus datos reales para responder.",
widget: "ai-signal-card",
      },
      {
        title: "Confirmation Cards",
        content:
          "Cuando el Copilot sugiere una acción (comprar, vender, ajustar bot), muestra una Confirmation Card con todos los detalles. Revisa: símbolo, cantidad, precio, stop-loss, take-profit. Solo se ejecuta si haces clic en 'Confirm'. Puedes editar los parámetros antes de confirmar.",
      },
      {
        title: "Command Palette (Cmd+K)",
        content:
          "El Command Palette te da acceso rápido a acciones del Copilot. Pulsa Cmd+K (o Ctrl+K) para abrirlo. Escribe comandos como 'buy 0.1 btc', 'close eth position', 'start grid bot'. El Copilot interpreta tu intención y muestra la Confirmation Card correspondiente.",
        actionLabel: "Probar Copilot",
        actionTarget: "ai-agent",
      },
    ],
  },

  // ─── 28. Auto-Pilot ─────────────────────────────────────────────────────────
  {
    id: "auto_pilot",
    title: "Auto-Pilot: Trading Automático con AI",
    category: "AI Trading",
    difficulty: "advanced",
    description: "Deja que el AI opere por ti con salvaguardas de seguridad.",
    estimatedMinutes: 15,
    xpReward: 175,
    steps: [
      {
        title: "¿Qué es Auto-Pilot?",
        content:
          "Auto-Pilot permite al AI Copilot ejecutar operaciones automáticamente basadas en tu estrategia configurada. El AI monitoriza el mercado 24/7, genera señales, y ejecuta trades sin tu intervención. Tú configuras las reglas: qué pares, cuánto riesgo, qué estrategia.",
widget: "ai-signal-card",
      },
      {
        title: "Salvaguardas",
        content:
          "Auto-Pilot tiene múltiples salvaguardas: 1. Max risk por trade (configurable). 2. Max daily loss (detiene el bot). 3. Max open positions. 4. Pares whitelist/blacklist. 5. Stop-loss obligatorio en cada trade. 6. Puedes detenerlo en cualquier momento. 7. Audit log de todas las decisiones del AI.",
      },
      {
        title: "Modo Paper vs Live",
        content:
          "EMPIEZA SIEMPRE en modo paper. Paper trading usa dinero virtual pero datos reales. Ejecuta al menos 100 trades en paper antes de ir live. Verifica: win rate, drawdown, y consistencia. Si los resultados son buenos, cambia a live con una cantidad pequeña (ej. $500).",
widget: "ai-signal-card",
      },
      {
        title: "Monitorear el Auto-Pilot",
        content:
          "Mientras Auto-Pilot está activo, puedes ver todas las decisiones del AI en tiempo real. Cada trade muestra: razonamiento, confianza, y resultado. El Agent Transparency Panel muestra estadísticas: total trades, win rate, P&L, y los factores que más influyeron en cada decisión.",
        actionLabel: "Ver AI Agent",
        actionTarget: "ai-agent",
      },
      {
        title: "Cuándo Detenerlo",
        content:
          "Detén Auto-Pilot si: 1. El drawdown supera tu límite. 2. El win rate cae por debajo del 40% en 50+ trades. 3. Las condiciones de mercado cambiaron drásticamente. 4. El AI hace trades que no entiendes. 5. Tu confianza en la estrategia disminuye. La transparencia es clave: si no entiendes qué hace, deténlo.",
      },
    ],
  },

  // ─── 29. Trading Psychology ─────────────────────────────────────────────────
  {
    id: "trading_psychology",
    title: "Psicología del Trading: FOMO y FUD",
    category: "Psychology",
    difficulty: "intermediate",
    description: "El mayor enemigo del trader no es el mercado, es su propia mente.",
    estimatedMinutes: 15,
    xpReward: 125,
    steps: [
      {
        title: "FOMO (Fear Of Missing Out)",
        content:
          "FOMO: comprar porque ves que algo sube y no quieres quedarte fuera. Es la causa #1 de pérdidas en principiantes. Compras en el top, el precio cae, y vendes con pérdida. Solución: NUNCA compres algo que ya subió 20%+ sin un pullback. Espera tu entrada. El mercado siempre da segundas oportunidades.",
      },
      {
        title: "FUD (Fear, Uncertainty, Doubt)",
        content:
          "FUD: vender por miedo sin razón técnica. Noticias negativas, tweets alarmistas, o simplemente ver rojo en tu portfolio. Solución: 1. Define tu thesis antes de comprar. 2. Si la thesis no cambió, no vendas. 3. Ignora el ruido de redes sociales. 4. Usa stop-loss para que el miedo no tome decisiones por ti.",
      },
      {
        title: "Revenge Trading",
        content:
          "Revenge trading: intentar recuperar una pérdida inmediatamente con un trade más grande y arriesgado. Es destructivo. Después de una pérdida: 1. Cierra la pantalla. 2. Toma 24h de descanso. 3. Revisa qué salió mal. 4. Vuelve con un trade pequeño. NUNCA aumentes el tamaño para 'recuperar'.",
      },
      {
        title: "Disciplina y Plan de Trading",
        content:
          "Un plan de trading define: qué operas, cuándo entras, cuándo sales, cuánto arriesgas. Escríbelo. Síguelo. La disciplina es lo que separa traders profesionales de amateurs. Los profesionales no operan por emoción; operan por su plan. Si no tienes plan, no operes.",
      },
      {
        title: "Journal de Trading",
        content:
          "Mantén un journal de cada trade: por qué entraste, cómo te sentiste, qué salió bien/mal. Revisa semanalmente. Encontrarás patrones: 'pierdo cuando opero después de las 10pm', 'gano cuando espero al cierre de la vela'. El journal es la herramienta de mejora continua más poderosa.",
      },
    ],
  },

  // ─── 30. Tax Reporting ──────────────────────────────────────────────────────
  {
    id: "tax_reporting",
    title: "Reportes Fiscales con Tax Studio",
    category: "Taxes",
    difficulty: "intermediate",
    description: "Genera reportes fiscales para 8+ países con Alvora Tax Studio.",
    estimatedMinutes: 12,
    xpReward: 125,
    steps: [
      {
        title: "Por qué Necesitas Reportes Fiscales",
        content:
          "En la mayoría de países, las ganancias de crypto son tributables. Cada vez que vendes, intercambias, o usas crypto, puede ser un evento fiscal. No reportar puede resultar en multas severas. Alvora Tax Studio calcula automáticamente tus ganancias/pérdidas y genera reportes para 8 países.",
widget: "tax-calculator",
      },
      {
        title: "Países Soportados",
        content:
          "Alvora Tax Studio soporta: España (IRPF), USA (Form 8949), UK (CGT), Alemania (Abgeltungsteuer), Australia (CGT), Canadá (Schedule 3), Francia (PFU), Japón (crypto tax). Cada país tiene reglas distintas: tasas, exenciones, métodos de cálculo. Selecciona tu país para un reporte correcto.",
widget: "tax-calculator",
      },
      {
        title: "Métodos de Cálculo",
        content:
          "FIFO (First In First Out): las primeras compras se venden primero. LIFO: las últimas primero. HIFO: las de mayor precio primero (minimiza ganancias). Cada país permite distintos métodos. USA permite FIFO, LIFO, HIFO. España requiere FIFO. Alemania usa FIFO. Selecciona el método correcto para tu país.",
widget: "tax-calculator",
      },
      {
        title: "Usar Tax Studio en Alvora",
        content:
          "Ve a la pestaña Tax Studio. Selecciona país, año, y método. Haz clic en 'Calculate'. Alvora analiza todos tus trades del año y genera: summary (ganancias, pérdidas, neto, impuesto estimado), disposiciones detalladas, y formulario específico del país. Exporta a CSV o guarda el reporte.",
        actionLabel: "Abrir Tax Studio",
        actionTarget: "tax",
      },
    ],
  },

  // ─── 31. Market Regimes ─────────────────────────────────────────────────────
  {
    id: "market_regimes",
    title: "Regímenes de Mercado: Trend, Range, Crisis",
    category: "Technical Analysis",
    difficulty: "advanced",
    description: "El mercado tiene distintas 'personalidades'. Adáptate o pierde.",
    estimatedMinutes: 12,
    xpReward: 150,
    steps: [
      {
        title: "Los 3 Regímenes Principales",
        content:
          "1. Trending (alcista o bajista): el precio se mueve en una dirección clara. Usa estrategias de trend following (MA crossover, breakout). 2. Ranging (lateral): el precio se mueve en un rango. Usa grid trading o mean reversion. 3. Crisis (high volatility): el mercado se desploma. Reduce exposición, usa stablecoins.",
widget: "market-regime",
      },
      {
        title: "Cómo Detectar el Régimen",
        content:
          "Indicadores: ADX (Average Directional Index) > 25 = tendencia fuerte. ADX < 20 = rango. Volatilidad (ATR): ATR alto = mercado volátil. Volume: volumen creciente confirma tendencia. Alvora detecta el régimen automáticamente y lo muestra en el dashboard. Usa esta info para activar/desactivar bots.",
      },
      {
        title: "Adaptar tu Estrategia",
        content:
          "Grid bot en rango = excelente. Grid bot en tendencia = pierde. Trend following en tendencia = excelente. Trend following en rango = muchas señales falsas. La clave es MATCH tu estrategia al régimen. Alvora puede pausar automáticamente tus bots si el régimen cambia a uno desfavorable.",
widget: "market-regime",
      },
      {
        title: "Gestión de Régimen en Alvora",
        content:
          "Alvora incluye un Market Regime Filter en los bots y estrategias. Cuando se activa, el bot solo opera si el régimen es favorable. Si el mercado pasa de rango a tendencia, el grid bot se pausa automáticamente. Si entra en crisis, todos los bots pueden pausarse. Configura esto en la sección Risk de cada bot.",
        actionLabel: "Ver Dashboard",
        actionTarget: "dashboard",
      },
    ],
  },
];

// ─── Helper functions ─────────────────────────────────────────────────────────

export function getTutorialsByCategory(category: TutorialCategory): Tutorial[] {
  return TUTORIALS.filter((t) => t.category === category);
}

export function getTutorialById(id: string): Tutorial | undefined {
  return TUTORIALS.find((t) => t.id === id);
}

export const TUTORIAL_CATEGORIES: TutorialCategory[] = [
  "Primeros pasos",
  "Trading",
  "Technical Analysis",
  "Bots",
  "Risk Management",
  "DeFi",
  "AI Trading",
  "Psychology",
  "Taxes",
];

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  beginner: "Principiante",
  intermediate: "Intermedio",
  advanced: "Avanzado",
};

export const DIFFICULTY_COLORS: Record<Difficulty, string> = {
  beginner: "var(--color-success)",
  intermediate: "var(--color-warning)",
  advanced: "var(--color-danger)",
};

// ─── Gamification: XP Levels ──────────────────────────────────────────────────

export interface XPLevel {
  level: number;
  title: string;
  icon: string;
  minXp: number;
}

export const XP_LEVELS: XPLevel[] = [
  { level: 1, title: "Novato", icon: "🌱", minXp: 0 },
  { level: 2, title: "Aprendiz", icon: "📚", minXp: 50 },
  { level: 3, title: "Trader Junior", icon: "📈", minXp: 150 },
  { level: 4, title: "Trader Intermedio", icon: "🎯", minXp: 300 },
  { level: 5, title: "Trader Avanzado", icon: "🔥", minXp: 500 },
  { level: 6, title: "Estratega", icon: "♟️", minXp: 800 },
  { level: 7, title: "Maestro Trading", icon: "👑", minXp: 1200 },
  { level: 8, title: "Alvora Legend", icon: "💎", minXp: 2000 },
];

export function getLevelForXp(xp: number): XPLevel {
  let current = XP_LEVELS[0];
  for (const lvl of XP_LEVELS) {
    if (xp >= lvl.minXp) current = lvl;
  }
  return current;
}

export function getNextLevel(level: number): XPLevel | null {
  return XP_LEVELS.find((l) => l.level === level + 1) || null;
}

// XP reward per tutorial based on difficulty (fallback if tutorial.xpReward not set)
export const XP_REWARDS: Record<Difficulty, number> = {
  beginner: 25,
  intermediate: 50,
  advanced: 100,
};

export function getXpForTutorial(tutorial: Tutorial): number {
  return tutorial.xpReward ?? XP_REWARDS[tutorial.difficulty];
}

// ─── Gamification: Badges ─────────────────────────────────────────────────────

export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  condition: (state: {
    completedTutorials: string[];
    perfectQuizzes: string[];
    xp: number;
    streak: number;
  }) => boolean;
}

export const BADGES: Badge[] = [
  {
    id: "first_steps",
    name: "Primeros Pasos",
    description: "Completa tu primer tutorial",
    icon: "🎯",
    condition: (s) => s.completedTutorials.length >= 1,
  },
  {
    id: "quick_learner",
    name: "Aprendiz Rápido",
    description: "Completa 3 tutoriales",
    icon: "⚡",
    condition: (s) => s.completedTutorials.length >= 3,
  },
  {
    id: "dedicated",
    name: "Dedicado",
    description: "Completa todos los tutoriales",
    icon: "🏆",
    condition: (s) => s.completedTutorials.length >= TUTORIALS.length,
  },
  {
    id: "perfect_quiz",
    name: "Quiz Perfecto",
    description: "Responde todas las preguntas de un tutorial correctamente",
    icon: "💯",
    condition: (s) => s.perfectQuizzes.length >= 1,
  },
  {
    id: "quiz_master",
    name: "Maestro de Quizzes",
    description: "Responde perfectamente 3 tutoriales",
    icon: "🧠",
    condition: (s) => s.perfectQuizzes.length >= 3,
  },
  {
    id: "streak_3",
    name: "Racha de 3",
    description: "Estudia 3 días seguidos",
    icon: "🔥",
    condition: (s) => s.streak >= 3,
  },
  {
    id: "streak_7",
    name: "Racha de 7",
    description: "Estudia 7 días seguidos",
    icon: "🚀",
    condition: (s) => s.streak >= 7,
  },
  {
    id: "level_5",
    name: "Trader Avanzado",
    description: "Alcanza el nivel 5",
    icon: "🎖️",
    condition: (s) => s.xp >= 500,
  },
  {
    id: "risk_aware",
    name: "Consciente del Riesgo",
    description: "Completa el tutorial de gestión de riesgo",
    icon: "🛡️",
    condition: (s) => s.completedTutorials.includes("risk_management"),
  },
  {
    id: "bot_master",
    name: "Maestro de Bots",
    description: "Completa todos los tutoriales de bots",
    icon: "🤖",
    condition: (s) => {
      const botTutorials = TUTORIALS.filter((t) => t.category === "Bots").map((t) => t.id);
      return botTutorials.every((id) => s.completedTutorials.includes(id));
    },
  },
  {
    id: "ai_pioneer",
    name: "Pionero de AI",
    description: "Completa el tutorial de AI Trading",
    icon: "🧬",
    condition: (s) => s.completedTutorials.includes("ai_trading_intro"),
  },
  {
    id: "xp_500",
    name: "500 XP",
    description: "Acumula 500 puntos de experiencia",
    icon: "⭐",
    condition: (s) => s.xp >= 500,
  },
  {
    id: "xp_1000",
    name: "1000 XP",
    description: "Acumula 1000 puntos de experiencia",
    icon: "🌟",
    condition: (s) => s.xp >= 1000,
  },
  {
    id: "streak_30",
    name: "Racha de 30",
    description: "Estudia 30 días seguidos",
    icon: "💎",
    condition: (s) => s.streak >= 30,
  },
  {
    id: "half_done",
    name: "Por la Mitad",
    description: "Completa el 50% de los tutoriales",
    icon: "🎯",
    condition: (s) => s.completedTutorials.length >= Math.ceil(TUTORIALS.length / 2),
  },
  {
    id: "ta_master",
    name: "Maestro del Análisis Técnico",
    description: "Completa todos los tutoriales de análisis técnico",
    icon: "📊",
    condition: (s) => {
      const taTutorials = TUTORIALS.filter((t) => t.category === "Technical Analysis").map((t) => t.id);
      return taTutorials.every((id) => s.completedTutorials.includes(id));
    },
  },
  {
    id: "defi_explorer_badge",
    name: "Explorador DeFi",
    description: "Completa todos los tutoriales de DeFi",
    icon: "⛓️",
    condition: (s) => {
      const defiTutorials = TUTORIALS.filter((t) => t.category === "DeFi").map((t) => t.id);
      return defiTutorials.every((id) => s.completedTutorials.includes(id));
    },
  },
  {
    id: "risk_expert",
    name: "Experto en Riesgo",
    description: "Completa todos los tutoriales de gestión de riesgo",
    icon: "🛡️",
    condition: (s) => {
      const riskTutorials = TUTORIALS.filter((t) => t.category === "Risk Management").map((t) => t.id);
      return riskTutorials.every((id) => s.completedTutorials.includes(id));
    },
  },
  {
    id: "quiz_master_5",
    name: "Quiz Master 5x",
    description: "Responde perfectamente 5 tutoriales",
    icon: "🎓",
    condition: (s) => s.perfectQuizzes.length >= 5,
  },
  {
    id: "path_beginner",
    name: "Beginner Path Complete",
    description: "Completa el learning path de principiante",
    icon: "🌱",
    condition: (s) => {
      const path = LEARNING_PATHS.find((p) => p.id === "beginner_trader");
      return path ? path.tutorialIds.every((id) => s.completedTutorials.includes(id)) : false;
    },
  },
  {
    id: "path_ta",
    name: "Technical Analyst Path",
    description: "Completa el learning path de análisis técnico",
    icon: "📈",
    condition: (s) => {
      const path = LEARNING_PATHS.find((p) => p.id === "technical_analyst");
      return path ? path.tutorialIds.every((id) => s.completedTutorials.includes(id)) : false;
    },
  },
];

// ─── Learning Paths ───────────────────────────────────────────────────────────

export interface LearningPath {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  tutorialIds: string[];
}

export const LEARNING_PATHS: LearningPath[] = [
  {
    id: "beginner_trader",
    title: "Beginner Trader Path",
    description: "De cero a primera operación — 7 tutoriales",
    icon: "🌱",
    color: "var(--color-success)",
    tutorialIds: ["what_is_crypto", "what_is_trading", "first_trade", "sl_tp_basics", "order_types", "reading_charts", "risk_management"],
  },
  {
    id: "technical_analyst",
    title: "Technical Analyst Path",
    description: "Domina el análisis de gráficos — 7 tutoriales",
    icon: "📊",
    color: "var(--color-primary)",
    tutorialIds: ["candlestick_patterns", "support_resistance", "moving_averages", "rsi_macd", "chart_patterns", "volume_analysis", "market_regimes"],
  },
  {
    id: "bot_master",
    title: "Bot Master Path",
    description: "Automatiza tu trading — 5 tutoriales",
    icon: "🤖",
    color: "var(--color-accent)",
    tutorialIds: ["grid_bot_explained", "dca_bot_explained", "bot_backtesting", "bot_optimization", "strategy_builder"],
  },
  {
    id: "ai_trader",
    title: "AI Trader Path",
    description: "Aprovecha la IA para tradear — 4 tutoriales",
    icon: "🧠",
    color: "var(--color-warning)",
    tutorialIds: ["ai_trading_intro", "ai_signals", "copilot_mastery", "auto_pilot"],
  },
  {
    id: "defi_explorer",
    title: "DeFi Explorer Path",
    description: "Explora las finanzas descentralizadas — 4 tutoriales",
    icon: "⛓️",
    color: "#f59e0b",
    tutorialIds: ["defi_basics", "wallet_safety", "dex_trading", "staking_liquidity"],
  },
  {
    id: "advanced_trader",
    title: "Advanced Trader Path",
    description: "Psicología, impuestos y estrategias pro — 4 tutoriales",
    icon: "🏆",
    color: "var(--color-danger)",
    tutorialIds: ["trading_psychology", "position_sizing", "portfolio_correlation", "tax_reporting"],
  },
];

// ─── Tutorial prerequisites ───────────────────────────────────────────────────

export const PREREQUISITES: Record<string, string[]> = {
  first_trade: ["what_is_crypto", "what_is_trading"],
  grid_bot_explained: ["first_trade"],
  risk_management: ["sl_tp_basics"],
  dca_bot_explained: ["first_trade"],
  ai_trading_intro: ["first_trade", "risk_management"],
  bot_backtesting: ["grid_bot_explained", "dca_bot_explained"],
  bot_optimization: ["bot_backtesting"],
  strategy_builder: ["grid_bot_explained"],
  position_sizing: ["risk_management"],
  portfolio_correlation: ["risk_management"],
  ai_signals: ["ai_trading_intro"],
  copilot_mastery: ["ai_trading_intro"],
  auto_pilot: ["copilot_mastery", "ai_signals"],
  dex_trading: ["defi_basics", "wallet_safety"],
  staking_liquidity: ["defi_basics"],
  tax_reporting: ["risk_management"],
  market_regimes: ["reading_charts"],
  rsi_macd: ["moving_averages"],
  chart_patterns: ["support_resistance"],
  volume_analysis: ["reading_charts"],
};

// ─── Quiz questions per tutorial ──────────────────────────────────────────────

export interface QuizQuestion {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export const QUIZZES: Record<string, QuizQuestion[]> = {
  first_trade: [
    {
      question: "¿Qué permisos de API key necesitas para operar?",
      options: [
        "Solo lectura",
        "Spot Trading (Read + Trade), sin permiso de retiro",
        "Withdrawal + Trading",
        "Solo withdrawal",
      ],
      correctIndex: 1,
      explanation:
        "Necesitas permisos de trading (spot/futures) pero NUNCA permiso de withdrawal. Tus claves se cifran con AES-256.",
    },
    {
      question: "¿Qué tipo de orden se ejecuta inmediatamente al mejor precio?",
      options: ["Limit Order", "Stop-Loss", "Market Order", "Take-Profit"],
      correctIndex: 2,
      explanation:
        "Las órdenes Market se ejecutan inmediatamente al mejor precio disponible. Las Limit se ejecutan solo a tu precio especificado.",
    },
    {
      question: "¿Dónde puedes ver tu P&L no realizado en tiempo real?",
      options: ["Dashboard", "Positions", "Bots", "Connections"],
      correctIndex: 1,
      explanation: "La pestaña 'Positions' muestra tus posiciones abiertas con el P&L no realizado en tiempo real.",
    },
    {
      question: "¿Cómo se cifran tus API keys en Alvora?",
      options: ["MD5", "AES-256", "Sin cifrado", "Base64"],
      correctIndex: 1,
      explanation: "Las claves se cifran con AES-256 y nunca se almacenan en texto plano.",
    },
  ],
  grid_bot_explained: [
    {
      question: "¿En qué tipo de mercado funciona mejor el grid trading?",
      options: [
        "Tendencias alcistas fuertes",
        "Tendencias bajistas fuertes",
        "Mercados laterales con volatilidad",
        "Mercados sin volatilidad",
      ],
      correctIndex: 2,
      explanation:
        "El grid trading funciona mejor en mercados laterales (ranging) con alta volatilidad, generando beneficios de los movimientos de precio.",
    },
    {
      question: "Si configuras un grid de $40k a $60k con 10 niveles, ¿cuánto espacio hay entre cada nivel?",
      options: ["$1,000", "$2,000", "$500", "$5,000"],
      correctIndex: 1,
      explanation: "($60,000 - $40,000) / 10 = $2,000 entre cada nivel del grid.",
    },
    {
      question: "¿Qué pasa cuando detienes el grid bot?",
      options: [
        "Las órdenes pendientes se cancelan automáticamente",
        "Las órdenes pendientes se mantienen",
        "Se cierran todas las posiciones",
        "No se puede detener",
      ],
      correctIndex: 0,
      explanation: "Al detener el bot, las órdenes pendientes se cancelan automáticamente.",
    },
    {
      question: "¿Qué porcentaje del portfolio se recomienda invertir en un grid bot?",
      options: ["100%", "50%", "10-20%", "1%"],
      correctIndex: 2,
      explanation: "Se recomienda invertir 10-20% de tu portfolio en un grid bot para diversificar el riesgo.",
    },
  ],
  risk_management: [
    {
      question: "¿Cuánto deberías arriesgar máximo por operación?",
      options: ["10% del capital", "5% del capital", "1-2% del capital", "50% del capital"],
      correctIndex: 2,
      explanation:
        "La regla del 1-2% te permite sobrevivir rachas perdedoras sin arruinarte. Con $10,000, tu pérdida máxima por trade sería $100-$200.",
    },
    {
      question: "Si tienes $10,000 y arriesgas 1%, ¿cuál es tu riesgo máximo por trade?",
      options: ["$10", "$100", "$1,000", "$500"],
      correctIndex: 1,
      explanation: "$10,000 * 1% = $100 de pérdida máxima por operación.",
    },
    {
      question: "¿Qué ratio riesgo/recompensa significa arriesgar $1 para ganar $2?",
      options: ["2:1", "1:2", "1:1", "1:3"],
      correctIndex: 1,
      explanation: "Un ratio R:R de 1:2 significa arriesgas $1 para ganar $2. Con 50% de win rate, el valor esperado es positivo.",
    },
    {
      question: "¿Cuánta ganancia necesitas para recuperarte de un drawdown del 50%?",
      options: ["50%", "75%", "100%", "25%"],
      correctIndex: 2,
      explanation: "Un drawdown del 50% requiere un 100% de ganancia para recuperarse. Por eso es crucial controlar el drawdown máximo.",
    },
  ],
  sl_tp_basics: [
    {
      question: "¿Cuál es la función principal de un stop-loss?",
      options: [
        "Asegurar ganancias",
        "Limitar pérdidas",
        "Aumentar posición",
        "Cerrar ganancias automáticamente",
      ],
      correctIndex: 1,
      explanation: "El stop-loss cierra tu posición si el precio llega a un nivel determinado, limitando tus pérdidas.",
    },
    {
      question: "¿Qué hace un trailing stop?",
      options: [
        "Se mantiene fijo",
        "Se mueve con el precio, solo sube",
        "Se mueve contra el precio",
        "Se cancela automáticamente",
      ],
      correctIndex: 1,
      explanation:
        "El trailing stop se mueve con el precio. Si sube, el stop sube. Si baja, se mantiene. Permite capturar tendencias mientras protege ganancias.",
    },
    {
      question: "¿Qué tipo de stop-loss se basa en la volatilidad?",
      options: ["Fixed", "Percentage", "Trailing", "ATR-based"],
      correctIndex: 3,
      explanation: "El stop-loss ATR-based usa el Average True Range para ajustar el stop según la volatilidad del activo.",
    },
    {
      question: "¿Por qué muchos traders fallan según el tutorial?",
      options: [
        "Por usar stop-loss muy ajustado",
        "Por no tomar ganancias a tiempo",
        "Por operar demasiado poco",
        "Por usar take-profit",
      ],
      correctIndex: 1,
      explanation: "Muchos traders fallan por no tomar ganancias a tiempo, dejándose llevar por la codicia.",
    },
  ],
  dca_bot_explained: [
    {
      question: "¿Qué significa DCA?",
      options: [
        "Dollar Cost Averaging",
        "Daily Capital Allocation",
        "Direct Crypto Acquisition",
        "Dynamic Cost Adjustment",
      ],
      correctIndex: 0,
      explanation: "Dollar Cost Averaging: comprar una cantidad fija a intervalos regulares, sin importar el precio.",
    },
    {
      question: "¿Cuál es una ventaja principal del DCA?",
      options: [
        "Predice el mercado perfectamente",
        "Elimina la necesidad de timing the market",
        "Garantiza ganancias",
        "Reduce los impuestos",
      ],
      correctIndex: 1,
      explanation: "El DCA elimina la necesidad de timing the market y reduce el impacto emocional de la volatilidad.",
    },
    {
      question: "¿Qué hace el take-profit en un DCA bot?",
      options: [
        "Detiene las compras",
        "Vende todo cuando el promedio sube X%",
        "Aumenta la cantidad de compra",
        "Cambia el intervalo",
      ],
      correctIndex: 1,
      explanation:
        "Cuando el promedio de todas las compras sube X%, el bot vende todo y reinicia el ciclo, generando flujo de caja regular.",
    },
    {
      question: "Si compras $100 de BTC cada semana a precios diferentes, ¿qué obtienes?",
      options: [
        "Siempre el mismo precio de entrada",
        "Un promedio que reduce el impacto de la volatilidad",
        "Garantía de ganancia",
        "Precio igual al mercado",
      ],
      correctIndex: 1,
      explanation: "Al comprar en momentos diferentes, promedias el costo de entrada, reduciendo el impacto de la volatilidad.",
    },
  ],
  ai_trading_intro: [
    {
      question: "¿Qué analiza el AI Copilot para dar sugerencias?",
      options: [
        "Solo el precio",
        "Portfolio, señales técnicas, noticias y datos on-chain",
        "Solo noticias",
        "Solo datos on-chain",
      ],
      correctIndex: 1,
      explanation:
        "El AI Copilot analiza tu portfolio, señales técnicas, noticias y datos on-chain para ofrecerte sugerencias proactivas.",
    },
    {
      question: "¿A partir de qué nivel de confianza se consideran las señales más confiables?",
      options: ["50%", "60%", "70%", "90%"],
      correctIndex: 2,
      explanation: "Las señales de alta confianza (>70%) son las más confiables según el tutorial.",
    },
    {
      question: "¿Qué puedes hacer con el Visual Strategy Builder?",
      options: [
        "Solo ejecutar estrategias predefinidas",
        "Crear estrategias arrastrando bloques sin programar",
        "Solo programar en Python",
        "Solo hacer backtests",
      ],
      correctIndex: 1,
      explanation:
        "El Visual Strategy Builder te permite crear estrategias personalizadas sin programar, arrastrando bloques de entrada, salida, sizing y filtros.",
    },
    {
      question: "¿Qué se recomienda antes de usar el Auto-Pilot en vivo?",
      options: [
        "Nada, usarlo directamente",
        "Empezar en modo paper trading",
        "Invertir todo el capital",
        "Desactivar el AI",
      ],
      correctIndex: 1,
      explanation: "Se recomienda empezar en modo paper trading antes de ir en vivo con el Auto-Pilot.",
    },
    {
      question: "¿Qué incluye cada señal de AI?",
      options: [
        "Solo dirección",
        "Dirección, confianza, razonamiento, entry, stop y target",
        "Solo precio de entrada",
        "Solo razonamiento",
      ],
      correctIndex: 1,
      explanation:
        "Cada señal incluye symbol, direction, confidence, reasoning, entry, stop y target para una decisión informada.",
    },
  ],
  what_is_crypto: [
    {
      question: "¿Cuál es el suministro máximo de Bitcoin?",
      options: ["100 millones", "21 millones", "Ilimitado", "1 millón"],
      correctIndex: 1,
      explanation: "Bitcoin tiene un suminuesto máximo de 21 millones de monedas, lo que lo hace escaso y deflacionario.",
    },
    {
      question: "¿Qué es una blockchain?",
      options: ["Una base de datos central", "Un libro contable público distribuido", "Un tipo de wallet", "Un exchange"],
      correctIndex: 1,
      explanation: "Una blockchain es un libro contable público distribuido donde cada bloque está conectado al anterior mediante hashes criptográficos.",
    },
    {
      question: "¿Qué es una seed phrase?",
      options: ["Una contraseña temporal", "12-24 palabras que regeneran tu wallet", "Un tipo de orden", "Un exchange"],
      correctIndex: 1,
      explanation: "La seed phrase son 12-24 palabras que pueden regenerar tu wallet completa. Si la pierdes, pierdes acceso a tus fondos.",
    },
    {
      question: "¿Qué es un stablecoin?",
      options: ["Una crypto con precio estable pegado a un activo", "Una crypto que nunca baja", "Un tipo de wallet", "Un exchange regulado"],
      correctIndex: 0,
      explanation: "Los stablecoins (USDT, USDC) están pegados a un activo (normalmente USD) para reducir la volatilidad.",
    },
  ],
  what_is_trading: [
    {
      question: "¿Cuál es la diferencia principal entre trading e invertir?",
      options: ["No hay diferencia", "Trading es a corto plazo, invertir a largo plazo", "Trading es más seguro", "Invertir requiere más capital"],
      correctIndex: 1,
      explanation: "Trading es a corto plazo (días/semanas), invertir es a largo plazo (meses/años). El trading busca ganancias de fluctuaciones de precio.",
    },
    {
      question: "¿Qué es el apalancamiento 10x?",
      options: ["Ganas 10x siempre", "Controlas $10,000 con $1,000", "Pierdes máximo 10%", "10 órdenes simultáneas"],
      correctIndex: 1,
      explanation: "10x significa que controlas $10,000 con $1,000 de capital. Amplifica ganancias Y pérdidas. Una caída del 10% = liquidación.",
    },
    {
      question: "¿Qué porcentaje de traders novatos pierden dinero con apalancamiento?",
      options: ["10%", "30%", "70%", "90%"],
      correctIndex: 3,
      explanation: "Aproximadamente el 90% de traders novatos pierden dinero con apalancamiento. Por eso se recomienda empezar con spot.",
    },
    {
      question: "¿Qué es el spot trading?",
      options: ["Comprar y vender el activo real sin apalancamiento", "Trading con apalancamiento 1x", "Trading en exchanges físicos", "Trading de futuros"],
      correctIndex: 0,
      explanation: "Spot trading es comprar y vender el activo real sin apalancamiento. Es el tipo más seguro y recomendado para principiantes.",
    },
  ],
  order_types: [
    {
      question: "¿Qué orden puede sufrir slippage en mercados poco líquidos?",
      options: ["Limit Order", "Market Order", "OCO", "Stop-Loss"],
      correctIndex: 1,
      explanation: "Las órdenes Market se ejecutan inmediatamente al mejor precio, que puede ser peor de lo esperado en mercados poco líquidos (slippage).",
    },
    {
      question: "¿Cuándo se ejecuta una Limit Buy a $49,000?",
      options: ["Inmediatamente", "Solo si el precio baja a $49,000 o menos", "Solo si el precio sube", "Nunca"],
      correctIndex: 1,
      explanation: "Una Limit Buy se ejecuta solo a tu precio o mejor (más barato). Si el precio no llega, la orden no se ejecuta.",
    },
    {
      question: "¿Qué es una orden OCO?",
      options: ["Una orden que se ejecuta dos veces", "Take-profit y stop-loss: cuando una se ejecuta, la otra se cancela", "Orden sin comisión", "Orden de mercado doble"],
      correctIndex: 1,
      explanation: "OCO (One-Cancels-Other) coloca take-profit y stop-loss. Cuando una se ejecuta, la otra se cancela automáticamente.",
    },
    {
      question: "¿Por qué el stop-loss es la herramienta más importante?",
      options: ["Porque genera ganancias", "Porque limita pérdidas automáticamente", "Porque acelera órdenes", "Porque reduce comisiones"],
      correctIndex: 1,
      explanation: "El stop-loss limita pérdidas automáticamente. Sin él, una sola operación mala puede borrar semanas de ganancias.",
    },
  ],
  reading_charts: [
    {
      question: "¿Qué timeframe usa típicamente un day trader?",
      options: ["1m", "5m, 15m, 1h", "1d, 1w", "1 mes"],
      correctIndex: 1,
      explanation: "Los day traders usan timeframes de 5m, 15m y 1h. Los scalpers usan 1m-5m, los swing traders 4h-1d.",
    },
    {
      question: "¿Qué muestra una vela verde (alcista)?",
      options: ["Cierre < apertura", "Cierre > apertura", "Solo el máximo", "Solo el mínimo"],
      correctIndex: 1,
      explanation: "Una vela verde significa que el precio de cierre es mayor que el de apertura (movimiento alcista).",
    },
    {
      question: "¿Qué es una tendencia alcista?",
      options: ["Precios bajando", "Higher highs y higher lows", "Precios laterales", "Volumen alto"],
      correctIndex: 1,
      explanation: "Una tendencia alcista hace 'higher highs' (máximos más altos) y 'higher lows' (mínimos más altos).",
    },
    {
      question: "¿Qué confirma un movimiento de precio?",
      options: ["El volumen", "El número de trades", "La hora del día", "El exchange"],
      correctIndex: 0,
      explanation: "El volumen confirma los movimientos. Volumen alto = movimiento fuerte. Volumen bajo = movimiento débil, posible fake.",
    },
  ],
  candlestick_patterns: [
    {
      question: "¿Qué indica un Doji?",
      options: ["Tendencia alcista fuerte", "Indecisión entre compradores y vendedores", "Volumen alto", "Breakout inminente"],
      correctIndex: 1,
      explanation: "Un Doji tiene apertura y cierre casi iguales, indicando indecisión. Tras una tendencia, sugiere posible reversión.",
    },
    {
      question: "¿Qué es un Bullish Engulfing?",
      options: ["Una vela roja seguida de verde", "Vela verde grande que engulle una roja pequeña", "Dos velas verdes", "Una vela con mecha larga"],
      correctIndex: 1,
      explanation: "Bullish Engulfing: una vela verde grande que engulle completamente a una roja pequeña anterior. Señal de reversión alcista.",
    },
    {
      question: "¿En qué timeframes funcionan mejor los patrones de velas?",
      options: ["1m y 5m", "1h o mayor", "Solo en diario", "Cualquier timeframe igual"],
      correctIndex: 1,
      explanation: "Los patrones de velas funcionan mejor en timeframes de 1h o mayor. En timeframes cortos hay demasiado ruido.",
    },
    {
      question: "¿Qué es un Hammer?",
      options: ["Vela con cuerpo pequeño arriba y mecha inferior larga", "Vela con cuerpo grande", "Doji con mechas largas", "Vela sin cuerpo"],
      correctIndex: 0,
      explanation: "Hammer: cuerpo pequeño arriba, mecha inferior larga (2x el cuerpo). Tras tendencia bajista = señal de reversión alcista.",
    },
  ],
  support_resistance: [
    {
      question: "¿Qué es el soporte?",
      options: ["Nivel donde el precio sube", "Nivel donde el precio tiende a rebotar al alza", "Un tipo de orden", "Un indicador técnico"],
      correctIndex: 1,
      explanation: "Soporte es un nivel donde la presión compradora supera a la vendedora, y el precio tiende a rebotar al alza.",
    },
    {
      question: "¿Cómo distingues un breakout de un fakeout?",
      options: ["No se puede distinguir", "El precio cierra por encima del nivel con volumen alto", "El precio toca el nivel", "Por la hora del día"],
      correctIndex: 1,
      explanation: "Un breakout real: el precio cierra por encima del nivel con volumen alto. Un fakeout: el precio lo rompe pero vuelve atrás con volumen bajo.",
    },
    {
      question: "¿Qué hace más fuerte un nivel de soporte?",
      options: ["Que el precio lo toque muchas veces", "Que esté en un número redondo", "Que esté cerca del máximo", "Que sea reciente"],
      correctIndex: 0,
      explanation: "Cuantas más veces el precio toca un nivel y rebota, más fuerte es ese nivel. Los niveles con alto volumen también son más fuertes.",
    },
  ],
  moving_averages: [
    {
      question: "¿Qué es un Golden Cross?",
      options: ["EMA50 cruza por encima de EMA200", "Precio cruza EMA20", "Dos SMAs iguales", "Volumen alto"],
      correctIndex: 0,
      explanation: "Golden Cross: EMA(50) cruza por encima de EMA(200). Es una señal alcista de largo plazo.",
    },
    {
      question: "¿Cuál es la diferencia entre SMA y EMA?",
      options: ["No hay diferencia", "EMA da más peso a precios recientes, reacciona más rápido", "SMA es más rápida", "EMA solo funciona en crypto"],
      correctIndex: 1,
      explanation: "EMA da más peso a los precios recientes, por lo que reacciona más rápido a cambios. SMA trata todos los precios por igual.",
    },
    {
      question: "¿Cómo actúan las medias móviles en una tendencia?",
      options: ["Como resistencia", "Como soporte/resistencia dinámico", "No tienen efecto", "Como indicador de volumen"],
      correctIndex: 1,
      explanation: "En tendencias alcistas, el precio suele rebotar en la EMA (soporte dinámico). En bajistas, actúa como techo (resistencia dinámico).",
    },
  ],
  rsi_macd: [
    {
      question: "¿Cuándo se considera un activo sobrecomprado según el RSI?",
      options: ["RSI < 30", "RSI > 70", "RSI = 50", "RSI > 100"],
      correctIndex: 1,
      explanation: "RSI > 70 = sobrecomprado (posible reversión bajista). RSI < 30 = sobrevendido (posible reversión alcista).",
    },
    {
      question: "¿Qué es una divergencia alcista?",
      options: ["Precio sube, RSI sube", "Precio hace mínimo más bajo, RSI hace mínimo más alto", "RSI > 70", "MACD cruza bajista"],
      correctIndex: 1,
      explanation: "Divergencia alcista: el precio hace un mínimo más bajo pero el RSI hace un mínimo más alto. Señal de reversión alcista muy potente.",
    },
    {
      question: "¿Qué muestra el histograma del MACD?",
      options: ["El volumen", "La distancia entre MACD y la línea de señal", "El precio", "El RSI"],
      correctIndex: 1,
      explanation: "El histograma del MACD muestra la distancia entre la línea MACD y la línea de señal. Cuando cruza cero, hay señal de compra/venta.",
    },
    {
      question: "¿Cómo combinar RSI y MACD?",
      options: ["Usar solo uno", "RSI para sobrecompra/sobreventa, MACD para confirmar dirección", "Ambos deben ser iguales", "Nunca combinarlos"],
      correctIndex: 1,
      explanation: "Mejor estrategia: RSI identifica sobrecompra/sobreventa, MACD confirma la dirección. Ejemplo: RSI < 30 + MACD cruza alcista = señal fuerte.",
    },
  ],
  chart_patterns: [
    {
      question: "¿Qué es un triángulo ascendente?",
      options: ["Resistencia horizontal + soporte ascendente", "Dos líneas descendentes", "Un patrón de reversión", "Un indicador"],
      correctIndex: 0,
      explanation: "Triángulo ascendente: resistencia horizontal + soporte ascendente. Breakout alcista probable.",
    },
    {
      question: "¿Qué es un Head and Shoulders?",
      options: ["Patrón de continuación alcista", "Tres picos donde el central es más alto, señal de reversión bajista", "Un tipo de vela", "Un indicador"],
      correctIndex: 1,
      explanation: "Head & Shoulders: tres picos (central más alto). Cuando el precio rompe la neckline, confirma reversión bajista.",
    },
    {
      question: "¿Qué es un Double Bottom?",
      options: ["Dos picos", "Dos valles (suelos) seguidos, señal alcista", "Un patrón bajista", "Un tipo de orden"],
      correctIndex: 1,
      explanation: "Double Bottom: el precio toca soporte dos veces y sube. Señal de reversión alcista. El objetivo es la altura del patrón desde el breakout.",
    },
  ],
  volume_analysis: [
    {
      question: "¿Qué significa precio sube con volumen bajo?",
      options: ["Movimiento fuerte", "Movimiento débil, posible fake", "Volumen no importa", "Breakout confirmado"],
      correctIndex: 1,
      explanation: "Precio sube con volumen bajo = movimiento débil, posible fake. El volumen confirma la fuerza del movimiento.",
    },
    {
      question: "¿Qué es OBV?",
      options: ["Un tipo de orden", "On-Balance Volume: acumula volumen por dirección del precio", "Un exchange", "Un indicador de volatilidad"],
      correctIndex: 1,
      explanation: "OBV (On-Balance Volume) acumula volumen: suma cuando el precio cierra positivo, resta cuando cierra negativo. Detecta acumulación/distribución.",
    },
    {
      question: "¿Qué es el POC en Volume Profile?",
      options: ["Point of Control: nivel con más volumen", "Price of Crypto", "Un tipo de orden", "Un exchange"],
      correctIndex: 0,
      explanation: "POC (Point of Control) es el nivel de precio con más volumen. El precio tiende a volver al POC cuando no hay tendencia clara.",
    },
  ],
  bot_backtesting: [
    {
      question: "¿Por qué es obligatorio el backtesting antes de usar un bot en vivo?",
      options: ["No es obligatorio", "Porque sin él es una apuesta ciega", "Porque lo exige la ley", "Para reducir comisiones"],
      correctIndex: 1,
      explanation: "Un bot sin backtest es una apuesta ciega. El backtesting te muestra ROI, drawdown, win rate y Sharpe ratio antes de arriesgar dinero.",
    },
    {
      question: "¿Qué es overfitting?",
      options: ["Cuando el bot gana demasiado", "Optimizar parámetros hasta que el backtest se ve perfecto pero en vivo no funciona", "Un tipo de backtest", "Cuando el bot pierde"],
      correctIndex: 1,
      explanation: "Overfitting: optimizar parámetros hasta que el backtest es perfecto, pero en vivo no funciona. Síntomas: ROI irreal, win rate >80%.",
    },
    {
      question: "¿Qué Sharpe ratio se considera bueno?",
      options: ["< 0.5", "> 1", "> 5", "Cualquiera"],
      correctIndex: 1,
      explanation: "Sharpe > 1 es bueno, > 2 es excelente. Mide el retorno ajustado al riesgo. Un Sharpe bajo significa mucho riesgo para poco retorno.",
    },
  ],
  bot_optimization: [
    {
      question: "¿Qué ventaja tiene Monte Carlo sobre un backtest simple?",
      options: ["Es más rápido", "Da un rango de resultados posibles en lugar de uno solo", "Siempre da mejores resultados", "No necesita datos"],
      correctIndex: 1,
      explanation: "Monte Carlo simula miles de escenarios aleatorios. En lugar de un resultado, obtienes una distribución: mediana, peor caso, probabilidad de ruina.",
    },
    {
      question: "¿Qué es la probabilidad de ruina?",
      options: ["La probabilidad de ganar", "La probabilidad de perder todo tu capital", "La probabilidad de un trade malo", "La probabilidad de un bug"],
      correctIndex: 1,
      explanation: "Probabilidad de ruina = probabilidad de perder todo tu capital. Si es > 5%, la estrategia es demasiado arriesgada.",
    },
    {
      question: "¿Qué debes mirar en los resultados de Monte Carlo?",
      options: ["Solo el mejor caso", "El percentil 5 (peor caso realista)", "Solo la mediana", "El promedio"],
      correctIndex: 1,
      explanation: "Mira el percentil 5 (peor caso realista). Si muestra -30% drawdown, prepárate para eso. El percentil 50 es tu resultado más probable.",
    },
  ],
  strategy_builder: [
    {
      question: "¿Qué categorías de bloques tiene el Strategy Builder?",
      options: ["Solo Entry", "Entry, Exit, Sizing, Risk", "Solo Buy y Sell", "Solo indicadores"],
      correctIndex: 1,
      explanation: "El Strategy Builder tiene 4 categorías: Entry (cuándo comprar), Exit (cuándo vender), Sizing (cuánto), y Risk (filtros de seguridad).",
    },
    {
      question: "¿Qué bloques son obligatorios para validar una estrategia?",
      options: ["Solo Entry", "Al menos un Entry, un Exit, y un Sizing", "Solo Risk", "Todos los bloques"],
      correctIndex: 1,
      explanation: "Para validar: necesitas al menos un Entry (cuándo comprar), un Exit (cuándo vender), y un Sizing (cuánto comprar).",
    },
    {
      question: "¿Qué puedes hacer después de crear y backtestear una estrategia?",
      options: ["Nada", "Publicarla en el Marketplace", "Solo guardarla", "Solo ejecutarla en paper"],
      correctIndex: 1,
      explanation: "Si tu estrategia tiene buenos resultados en backtest, puedes publicarla en el Strategy Marketplace para que otros la usen (free o premium).",
    },
  ],
  position_sizing: [
    {
      question: "¿Qué porcentaje de los resultados de trading determina el position sizing según Van Tharp?",
      options: ["10%", "50%", "90%", "100%"],
      correctIndex: 2,
      explanation: "Van Tharp demostró que el position sizing determina el 90% de los resultados. Es más importante que la estrategia misma.",
    },
    {
      question: "¿Qué es Half Kelly?",
      options: ["Usar 50% de tu capital", "Usar la mitad del tamaño óptimo calculado por Kelly", "Un tipo de orden", "Un indicador"],
      correctIndex: 1,
      explanation: "Half Kelly = usar la mitad del tamaño que la fórmula Kelly sugiere. Full Kelly es demasiado volátil; Half Kelly es más seguro.",
    },
    {
      question: "¿Por qué el position sizing porcentual es mejor que el fijo?",
      options: ["Es más simple", "Se adapta al crecimiento/caída de tu cuenta", "Siempre gana", "Reduce impuestos"],
      correctIndex: 1,
      explanation: "El sizing porcentual se adapta automáticamente: si tu cuenta crece, arriesgas más; si cae, arriesgas menos. El fijo no se adapta.",
    },
  ],
  portfolio_correlation: [
    {
      question: "¿Qué significa correlación +1?",
      options: ["Los activos se mueven opuestos", "Los activos se mueven idénticos", "Sin relación", "Correlación negativa"],
      correctIndex: 1,
      explanation: "Correlación +1 = los activos se mueven idénticos. BTC y ETH tienen correlación ~0.85 (muy alta).",
    },
    {
      question: "Si tienes BTC, ETH y SOL, ¿estás diversificado?",
      options: ["Sí, son 3 activos", "No, todos son crypto y caen juntos", "Sí, siempre", "Depende del exchange"],
      correctIndex: 1,
      explanation: "BTC, ETH y SOL tienen correlación alta (~0.75-0.85). En crisis, todos caen juntos. Diversificación real requiere activos con baja correlación.",
    },
    {
      question: "¿Qué pasa con la correlación durante una crisis?",
      options: ["Baja a 0", "Todo tiende a correlacionar +1 (contagio)", "No cambia", "Se vuelve negativa"],
      correctIndex: 1,
      explanation: "En crisis, TODO tiende a correlacionar +1 (contagio). Por eso los stop-loss son cruciales — no puedes depender solo de la diversificación.",
    },
  ],
  defi_basics: [
    {
      question: "¿Qué es DeFi?",
      options: ["Un exchange centralizado", "Servicios financieros sin bancos, mediante smart contracts", "Un tipo de wallet", "Un regulador"],
      correctIndex: 1,
      explanation: "DeFi (Decentralized Finance) son servicios financieros sin bancos. Funcionan con smart contracts en blockchains como Ethereum.",
    },
    {
      question: "¿Cómo funciona Uniswap?",
      options: ["Con order book", "Con AMM (Automated Market Maker) y pools de liquidez", "Con bancos", "Con subastas"],
      correctIndex: 1,
      explanation: "Uniswap usa AMM: los usuarios proveen liquidez a pools y ganan comisiones. No hay order book. El precio se determina por la fórmula x*y=k.",
    },
    {
      question: "¿Qué puedes hacer en Aave?",
      options: ["Solo comprar tokens", "Prestar y pedir prestado crypto sin banco", "Solo hacer swaps", "Solo staking"],
      correctIndex: 1,
      explanation: "Aave permite prestar (ganar interés) y pedir prestado (usando crypto como colateral) sin intermediarios. Las tasas son dinámicas.",
    },
  ],
  wallet_safety: [
    {
      question: "¿Qué es una hot wallet?",
      options: ["Una wallet offline", "Una wallet conectada a internet", "Una wallet sin claves", "Un exchange"],
      correctIndex: 1,
      explanation: "Hot wallet = conectada a internet (MetaMask, Trust). Conveniente pero menos segura. No guardes grandes cantidades en ella.",
    },
    {
      question: "¿Dónde NO deberías guardar tu seed phrase?",
      options: ["En papel", "En metal", "En Google Drive o fotos", "En una caja fuerte"],
      correctIndex: 2,
      explanation: "NUNCA guardes tu seed phrase en digital (Google Drive, fotos, cloud). Si alguien la obtiene, roba todos tus fondos. Usa papel o metal.",
    },
    {
      question: "¿Qué porcentaje de tus crypto debería estar en cold wallet?",
      options: ["10%", "50%", "90%+", "0%"],
      correctIndex: 2,
      explanation: "90%+ de tus crypto debería estar en cold wallet (hardware). Solo guarda en hot wallet lo que necesitas para uso diario/DeFi.",
    },
  ],
  dex_trading: [
    {
      question: "¿Qué es el slippage en DEXs?",
      options: ["Un tipo de fee", "Diferencia entre precio esperado y precio real de ejecución", "Un error del contrato", "Un tipo de wallet"],
      correctIndex: 1,
      explanation: "Slippage = diferencia entre el precio esperado y el precio real. En pools pequeños, swaps grandes mueven el precio significativamente.",
    },
    {
      question: "¿Qué es Impermanent Loss?",
      options: ["Pérdida permanente", "Pérdida de liquidity providers cuando el precio cambia", "Un fee del DEX", "Un tipo de slippage"],
      correctIndex: 1,
      explanation: "IL afecta a liquidity providers: cuando el precio de los tokens cambia, tu posición vale menos que si simplemente hubieras mantenido los tokens.",
    },
    {
      question: "¿Qué es MEV/front-running?",
      options: ["Un tipo de fee", "Bots que adelantan tus transacciones en la mempool", "Un exchange", "Un indicador"],
      correctIndex: 1,
      explanation: "MEV: bots monitorizan la mempool y adelantan tus transacciones. Compran antes que tú (subiendo el precio) y te venden más caro.",
    },
  ],
  staking_liquidity: [
    {
      question: "¿Qué es staking?",
      options: ["Vender crypto", "Bloquear tokens para asegurar una red PoS y ganar recompensas", "Comprar NFTs", "Un tipo de trade"],
      correctIndex: 1,
      explanation: "Staking = bloquear tus tokens para asegurar una red Proof-of-Stake. A cambio recibes recompensas (4-14% APY según la red).",
    },
    {
      question: "¿Qué es liquid staking (Lido)?",
      options: ["Staking con liquidación forzada", "Recibes un token líquido (stETH) que puedes usar en DeFi", "Staking sin recompensas", "Un tipo de exchange"],
      correctIndex: 1,
      explanation: "Liquid staking: depositas ETH y recibes stETH (que puedes usar en DeFi). stETH aprecia diariamente con las recompensas. No necesitas 32 ETH.",
    },
    {
      question: "¿Qué riesgo tiene el liquidity mining?",
      options: ["Ninguno", "Impermanent loss + depreciación del token de gobernanza", "Solo fees", "Solo slippage"],
      correctIndex: 1,
      explanation: "Liquidity mining: además de las comisiones, recibes tokens de gobernanza que pueden perder valor. Riesgo: IL + token depreciation.",
    },
  ],
  ai_signals: [
    {
      question: "¿A partir de qué confianza se considera una señal de alta confianza?",
      options: ["50%", "60%", "70%", "90%"],
      correctIndex: 2,
      explanation: "Señales >70% son de alta confianza. 50-70% moderadas. <50% débiles. La confianza NO es garantía de éxito.",
    },
    {
      question: "¿Qué factores analiza el AI de Alvora?",
      options: ["Solo precio", "Técnicos, sentimiento, on-chain, macro, funding", "Solo noticias", "Solo volumen"],
      correctIndex: 1,
      explanation: "El AI analiza: técnicos (RSI, MACD, MA), sentimiento (news, social), on-chain (whales, flows), macro (DXY, rates), y funding rates.",
    },
    {
      question: "¿Cómo dimensionar posición basada en confianza?",
      options: ["Siempre 2%", "90% confianza -> 2% risk, 50% -> 0.5%", "Confianza no afecta el tamaño", "10% siempre"],
      correctIndex: 1,
      explanation: "Position sizing basado en confianza: 90% -> 2% risk, 70% -> 1%, 50% -> 0.5%. <50% -> no operar. Reduce riesgo en señales débiles.",
    },
  ],
  copilot_mastery: [
    {
      question: "¿Qué datos reales tiene el Copilot sobre ti?",
      options: ["Ninguno", "Posiciones, P&L, historial de trades, configuración de bots", "Solo tu email", "Solo tu nombre"],
      correctIndex: 1,
      explanation: "El Copilot tiene acceso a tus datos reales: posiciones, P&L, historial de trades, y configuración de bots. Por eso puede dar sugerencias personalizadas.",
    },
    {
      question: "¿Cómo hacer un prompt efectivo al Copilot?",
      options: ["Decir solo 'qué hago'", "Dar contexto específico: tu posición, el precio, indicadores", "Usar una sola palabra", "Hablar en inglés"],
      correctIndex: 1,
      explanation: "Sé específico: 'Mi ETH está -8%, RSI es 28, MACD muestra divergencia alcista. Debería mantener, añadir, o cerrar?' Cuanto más contexto, mejor la respuesta.",
    },
    {
      question: "¿Qué es una Confirmation Card?",
      options: ["Un recibo", "Muestra detalles de una acción sugerida para que confirmes antes de ejecutar", "Un tipo de alerta", "Un reporte"],
      correctIndex: 1,
      explanation: "Confirmation Card: muestra símbolo, cantidad, precio, SL, TP de una acción sugerida. Solo se ejecuta si haces clic en 'Confirm'. Puedes editar parámetros.",
    },
  ],
  auto_pilot: [
    {
      question: "¿En qué modo deberías EMPEZAR con Auto-Pilot?",
      options: ["Live con todo tu capital", "Paper trading (dinero virtual)", "Live con $10,000", "No usar Auto-Pilot"],
      correctIndex: 1,
      explanation: "EMPIEZA SIEMPRE en paper trading. Ejecuta al menos 100 trades en paper antes de ir live. Luego live con cantidad pequeña ($500).",
    },
    {
      question: "¿Qué salvaguardas tiene Auto-Pilot?",
      options: ["Ninguna", "Max risk por trade, max daily loss, max positions, stop-loss obligatorio", "Solo stop-loss", "Solo whitelist"],
      correctIndex: 1,
      explanation: "Auto-Pilot tiene: max risk por trade, max daily loss (detiene el bot), max open positions, pares whitelist/blacklist, stop-loss obligatorio, y audit log.",
    },
    {
      question: "¿Cuándo deberías detener Auto-Pilot?",
      options: ["Nunca", "Si drawdown supera tu límite o win rate cae <40% en 50+ trades", "Solo si ganaste", "Solo los fines de semana"],
      correctIndex: 1,
      explanation: "Detén Auto-Pilot si: drawdown supera tu límite, win rate <40% en 50+ trades, condiciones de mercado cambiaron, o no entiendes los trades del AI.",
    },
  ],
  trading_psychology: [
    {
      question: "¿Qué es FOMO?",
      options: ["Fear Of Missing Out — comprar porque algo sube", "Un indicador técnico", "Un tipo de orden", "Un exchange"],
      correctIndex: 0,
      explanation: "FOMO: comprar porque ves que algo sube y no quieres quedarte fuera. Es la causa #1 de pérdidas en principiantes. Compras en el top.",
    },
    {
      question: "¿Qué es revenge trading?",
      options: ["Vengarse de un exchange", "Intentar recuperar una pérdida con un trade más grande y arriesgado", "Un tipo de estrategia", "Cerrar todas las posiciones"],
      correctIndex: 1,
      explanation: "Revenge trading: intentar recuperar una pérdida inmediatamente con un trade más grande. Es destructivo. Después de una pérdida: reduce tamaño, no lo aumentes.",
    },
    {
      question: "¿Qué deberías hacer después de una pérdida?",
      options: ["Operar más grande para recuperar", "Cerrar la pantalla, tomar 24h de descanso, revisar qué salió mal", "Comprar más", "Vender todo"],
      correctIndex: 1,
      explanation: "Después de una pérdida: cierra la pantalla, toma 24h de descanso, revisa qué salió mal, vuelve con un trade pequeño. NUNCA aumentes el tamaño.",
    },
    {
      question: "¿Por qué es importante un journal de trading?",
      options: ["No lo es", "Para encontrar patrones en tu trading y mejorar", "Para impuestos", "Para el exchange"],
      correctIndex: 1,
      explanation: "Un journal te ayuda a encontrar patrones: 'pierdo después de las 10pm', 'gano cuando espero al cierre de la vela'. Es la herramienta de mejora continua más poderosa.",
    },
  ],
  tax_reporting: [
    {
      question: "¿Qué eventos son típicamente tributables?",
      options: ["Solo comprar crypto", "Vender crypto, intercambiar crypto, usar crypto para comprar", "Transferir entre tus wallets", "Solo guardar"],
      correctIndex: 1,
      explanation: "Eventos tributables: vender por fiat, intercambiar crypto por crypto, usar crypto para comprar bienes/servicios, ganar staking rewards.",
    },
    {
      question: "¿Qué método de cálculo minimiza las ganancias reportadas?",
      options: ["FIFO", "LIFO", "HIFO (Highest In First Out)", "No importa"],
      correctIndex: 2,
      explanation: "HIFO vende primero las compras de mayor precio, minimizando la ganancia reportada. Pero no todos los países lo permiten (España requiere FIFO).",
    },
    {
      question: "¿Cuántos países soporta Tax Studio de Alvora?",
      options: ["3", "5", "8", "20"],
      correctIndex: 2,
      explanation: "Alvora Tax Studio soporta 8 países: España, USA, UK, Alemania, Australia, Canadá, Francia, y Japón. Cada uno con sus reglas específicas.",
    },
  ],
  market_regimes: [
    {
      question: "¿Qué ADX indica una tendencia fuerte?",
      options: ["ADX < 20", "ADX > 25", "ADX = 0", "ADX > 100"],
      correctIndex: 1,
      explanation: "ADX > 25 = tendencia fuerte. ADX < 20 = mercado en rango. El ADX mide la fuerza de la tendencia sin importar la dirección.",
    },
    {
      question: "¿Qué estrategia funciona mejor en un mercado lateral (rango)?",
      options: ["Trend following", "Grid trading", "Breakout", "Ninguna"],
      correctIndex: 1,
      explanation: "Grid trading funciona mejor en rangos: compra en el soporte y vende en la resistencia automáticamente. En tendencias, pierde.",
    },
    {
      question: "¿Qué pasa con la correlación en una crisis?",
      options: ["Baja", "Todo tiende a correlacionar +1 (contagio)", "No cambia", "Se vuelve negativa"],
      correctIndex: 1,
      explanation: "En crisis, todo tiende a correlacionar +1 (contagio). Por eso los stop-loss son cruciales — la diversificación sola no protege en crisis.",
    },
  ],
};

// ─── Helper: get quiz for a tutorial ──────────────────────────────────────────

export function getQuizForTutorial(tutorialId: string): QuizQuestion[] | undefined {
  return QUIZZES[tutorialId];
}

// ─── Helper: check if prerequisites are met ───────────────────────────────────

export function arePrerequisitesMet(
  tutorialId: string,
  completedTutorials: string[],
): boolean {
  const prereqs = PREREQUISITES[tutorialId];
  if (!prereqs || prereqs.length === 0) return true;
  return prereqs.every((id) => completedTutorials.includes(id));
}
