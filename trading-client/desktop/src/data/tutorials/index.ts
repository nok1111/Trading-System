// ─── Tutorial data for Alvora Academy ─────────────────────────────────────────

export type TutorialCategory =
  | "Primeros pasos"
  | "Trading"
  | "Bots"
  | "Risk Management"
  | "DeFi"
  | "AI Trading";

export type Difficulty = "beginner" | "intermediate" | "advanced";

export interface TutorialStep {
  title: string;
  content: string;
  codeExample?: string;
}

export interface Tutorial {
  id: string;
  title: string;
  category: TutorialCategory;
  difficulty: Difficulty;
  description: string;
  estimatedMinutes: number;
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
    steps: [
      {
        title: "Conectar tu Exchange",
        content:
          "Antes de operar, necesitas conectar tu exchange (Binance, OKX, o Bybit). Ve a la pestaña 'Connections' y haz clic en 'Add Connection'. Ingresa tu API key y secret. Tus claves se cifran con AES-256 y nunca se almacenan en texto plano.",
        codeExample: `# API Key permissions needed:
# - Spot Trading (Read + Trade)
# - Futures Trading (if using futures)
# - NO withdrawal permission needed`,
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
        codeExample: `# Market Order: executes immediately
# Limit Order: executes only at your specified price
# Stop-Loss: automatically sells if price drops to a level
# Take-Profit: automatically sells when price reaches your target`,
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
    steps: [
      {
        title: "¿Qué es Grid Trading?",
        content:
          "El grid trading divide un rango de precios en niveles (grid). Coloca órdenes de compra en los niveles inferiores y órdenes de venta en los niveles superiores. Cuando el precio sube, vende; cuando baja, compra. Genera beneficios de la volatilidad sin necesidad de predecir la dirección del mercado.",
        codeExample: `# Grid Bot Parameters:
# lower_price: $40,000  (bottom of range)
# upper_price: $60,000  (top of range)
# grid_count: 10         (number of levels)
# investment: $1,000     (total capital)
#
# Each grid level: ($60k - $40k) / 10 = $2,000 apart
# Buy at: $40k, $42k, $44k, $46k, $48k
# Sell at: $52k, $54k, $56k, $58k, $60k`,
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
        codeExample: `# Recommended settings for BTC/USDT:
# Range: ±10% from current price
# Grid count: 10-20 (more grids = more trades, less profit each)
# Investment: 10-20% of your portfolio
# Monitor and adjust range as needed`,
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
    steps: [
      {
        title: "La Regla del 1-2%",
        content:
          "Nunca arriesgues más del 1-2% de tu capital total en una sola operación. Si tienes $10,000, tu pérdida máxima por trade debería ser $100-$200. Esto te permite sobrevivir rachas perdedoras sin arruinarte.",
        codeExample: `# Position sizing formula:
# risk_amount = portfolio * risk_pct  (e.g. $10,000 * 1% = $100)
# position_size = risk_amount / stop_loss_distance
#
# Example: BTC at $50,000, stop at $49,000 (2% drop)
# risk_amount = $100
# position_size = $100 / ($50,000 - $49,000) = 0.1 BTC`,
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
        codeExample: `# Risk/Reward ratio:
# Entry: $50,000
# Stop-loss: $49,000 (risk $1,000)
# Take-profit: $52,000 (reward $2,000)
# R:R = 1:2
#
# With 50% win rate and 1:2 R:R:
# Expected value = (0.5 * $2,000) - (0.5 * $1,000) = +$500/trade`,
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
    steps: [
      {
        title: "¿Qué es un Stop-Loss?",
        content:
          "Un stop-loss es una orden automática que cierra tu posición si el precio llega a un nivel determinado. Su función es limitar tus pérdidas. Sin stop-loss, una sola operación mala puede borrar semanas de ganancias.",
        codeExample: `# Types of stop-loss:
# 1. Fixed: "Sell if price drops to $49,000"
# 2. Percentage: "Sell if price drops 3% from entry"
# 3. Trailing: "Sell if price drops 2% from highest point"
# 4. ATR-based: "Sell if price drops 2x ATR from entry"`,
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
        codeExample: `# Trailing stop example:
# Entry: $50,000, trail: 5%
# Price goes to $55,000 -> stop moves to $52,250
# Price goes to $60,000 -> stop moves to $57,000
# Price drops to $57,000 -> position closed with +14% profit`,
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
    steps: [
      {
        title: "¿Qué es DCA?",
        content:
          "Dollar Cost Averaging (DCA) es una estrategia donde compras una cantidad fija de un activo a intervalos regulares, sin importar el precio. Al comprar en momentos diferentes, promedias el costo de entrada y reduces el impacto de la volatilidad.",
        codeExample: `# DCA Example: Buy $100 of BTC every week
# Week 1: BTC at $50,000 -> buy 0.002 BTC
# Week 2: BTC at $45,000 -> buy 0.00222 BTC
# Week 3: BTC at $52,000 -> buy 0.00192 BTC
# Average entry: ~$48,833 (lower than average market price)`,
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
        codeExample: `# DCA Bot settings:
# Symbol: BTC/USDT
# Buy amount: $50 per purchase
# Interval: 7 days (weekly)
# Max buys: 0 (unlimited)
# Take profit: 15% (auto-sell when up 15%)`,
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
    steps: [
      {
        title: "¿Qué es el AI Copilot?",
        content:
          "Alvora incluye un AI Copilot impulsado por modelos de lenguaje avanzados. Analiza tu portfolio, señales técnicas, noticias, y datos on-chain para ofrecerte sugerencias proactivas. No es solo un chatbot: tiene acceso a tus datos reales de trading.",
        codeExample: `# AI Copilot capabilities:
# - Portfolio analysis and risk assessment
# - Proactive trading suggestions
# - Market regime detection
# - Natural language queries about your positions
# - Automated strategy execution (with your approval)`,
      },
      {
        title: "Conversar con Alvora",
        content:
          "Usa el panel de chat para hacer preguntas en lenguaje natural. Ejemplos: '¿Cómo está mi portfolio?', '¿Qué piensas de BTC ahora?', '¿Debería cerrar mi posición de ETH?'. El AI analiza tus datos y responde con contexto real.",
        codeExample: `# Example queries:
# "Analyze my risk exposure"
# "What's the market sentiment today?"
# "Should I adjust my grid bot range?"
# "Find arbitrage opportunities between exchanges"`,
      },
      {
        title: "Señales de AI",
        content:
          "El AI genera señales de trading basadas en análisis multi-factor: técnicos, sentimiento, on-chain, y macro. Cada señal incluye un nivel de confianza y un razonamiento. Las señales de alta confianza (>70%) son las más confiables.",
        codeExample: `# Signal structure:
# {
#   "symbol": "BTCUSDT",
#   "direction": "long",
#   "confidence": 78,
#   "reasoning": "RSI oversold + bullish divergence + 
#                whale accumulation detected",
#   "entry": 49500,
#   "stop": 48000,
#   "target": 53000
# }`,
      },
      {
        title: "Visual Strategy Builder",
        content:
          "Con el Visual Strategy Builder, puedes crear estrategias personalizadas sin programar. Arrastra bloques de entrada, salida, sizing, y filtros de riesgo. El AI puede sugerirte bloques basados en tu perfil de riesgo. Exporta tu estrategia a JSON o ejecuta un backtest directamente.",
        codeExample: `# Strategy Builder blocks:
# Entry: price above/below, RSI level, MA cross, AI signal
# Exit: take profit %, stop loss %, trailing stop, time exit
# Sizing: fixed USD, % portfolio, Kelly criterion
# Risk: max positions, max drawdown, regime filter`,
      },
      {
        title: "Auto-Pilot Mode",
        content:
          "El Auto-Pilot permite al AI ejecutar operaciones automáticamente basadas en tu estrategia configurada. Siempre puedes ver qué hace el AI en tiempo real y detenerlo en cualquier momento. Se recomienda empezar en modo paper trading antes de ir en vivo.",
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
  "Bots",
  "Risk Management",
  "DeFi",
  "AI Trading",
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
