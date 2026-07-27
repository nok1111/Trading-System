import type {
  MarketOverview,
  FearGreedData,
  DominanceData,
  NewsItem,
  MacroEvent,
  WhaleActivity,
  DailyReport,
  SinceLastVisitData,
  TodayPrioritiesData,
  AIActivityData,
} from "./intelligenceTypes";

const now = new Date().toISOString();

function daysAgo(days: number): string {
  return new Date(Date.now() - days * 86400000).toISOString();
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3600000).toISOString();
}

export const MOCK_MARKET_OVERVIEW: MarketOverview = {
  regime: "RANGING",
  riskLevel: "medium",
  riskOnOff: "risk_on",
  capitalFlows: [
    { from: "BTC", to: "Stablecoins", amount: 1200000000 },
    { from: "Altcoins", to: "BTC", amount: 450000000 },
  ],
  summary:
    "Mercado en rango con sentimiento cauteloso. BTC consolidando entre 60K-68K. Capital rotando hacia stablecoins.",
  timestamp: now,
};

export const MOCK_FEAR_GREED: FearGreedData = {
  value: 72,
  classification: "Greed",
  previousValue: 65,
  previousClassification: "Greed",
  history: Array.from({ length: 7 }, (_, i) => ({
    timestamp: daysAgo(6 - i),
    value: 58 + Math.round(Math.random() * 20),
  })),
  timestamp: now,
};

export const MOCK_DOMINANCE: DominanceData = {
  btc: 54.2,
  eth: 17.8,
  others: 28.0,
  history: Array.from({ length: 7 }, (_, i) => ({
    timestamp: daysAgo(6 - i),
    btc: 52 + Math.round(Math.random() * 4),
    eth: 16 + Math.round(Math.random() * 3),
    others: 28 + Math.round(Math.random() * 3),
  })),
  timestamp: now,
};

export const MOCK_NEWS: NewsItem[] = [
  {
    id: "news-1",
    title: "Bitcoin ETF inflows reach $500M in weekly net flow",
    source: "CoinDesk",
    url: "#",
    timestamp: hoursAgo(2),
    sentiment: "positive",
    assets: ["BTC"],
    impact: "high",
    summary:
      "Institutional demand continues as spot Bitcoin ETFs see significant inflows.",
  },
  {
    id: "news-2",
    title: "Fed signals possible rate cut in next quarter",
    source: "Bloomberg",
    url: "#",
    timestamp: hoursAgo(5),
    sentiment: "positive",
    assets: ["BTC", "ETH"],
    impact: "high",
    summary:
      "Federal Reserve officials hint at dovish pivot, boosting risk assets.",
  },
  {
    id: "news-3",
    title: "Major exchange faces regulatory scrutiny in EU",
    source: "Reuters",
    url: "#",
    timestamp: hoursAgo(8),
    sentiment: "negative",
    assets: ["BTC", "ETH"],
    impact: "medium",
    summary:
      "European regulators launch investigation into compliance practices.",
  },
  {
    id: "news-4",
    title: "Ethereum network upgrade successfully deployed",
    source: "Decrypt",
    url: "#",
    timestamp: hoursAgo(12),
    sentiment: "positive",
    assets: ["ETH"],
    impact: "medium",
    summary: "Pectra upgrade goes live with improved scalability.",
  },
  {
    id: "news-5",
    title: "Stablecoin market cap reaches new all-time high",
    source: "The Block",
    url: "#",
    timestamp: hoursAgo(18),
    sentiment: "neutral",
    assets: ["USDT", "USDC"],
    impact: "low",
    summary: "Total stablecoin supply surpasses $200B, signaling liquidity.",
  },
];

export const MOCK_MACRO_EVENTS: MacroEvent[] = [
  {
    id: "macro-1",
    event: "FOMC Rate Decision",
    date: new Date(Date.now() + 3 * 86400000).toISOString(),
    country: "US",
    impact: "high",
    actual: null,
    forecast: "5.25%",
    previous: "5.50%",
  },
  {
    id: "macro-2",
    event: "CPI Data Release",
    date: new Date(Date.now() + 5 * 86400000).toISOString(),
    country: "US",
    impact: "high",
    actual: null,
    forecast: "3.1%",
    previous: "3.3%",
  },
  {
    id: "macro-3",
    event: "GDP Growth QoQ",
    date: new Date(Date.now() + 7 * 86400000).toISOString(),
    country: "US",
    impact: "medium",
    actual: null,
    forecast: "2.4%",
    previous: "2.8%",
  },
  {
    id: "macro-4",
    event: "ECB Interest Rate Decision",
    date: new Date(Date.now() + 10 * 86400000).toISOString(),
    country: "EU",
    impact: "medium",
    actual: null,
    forecast: "4.00%",
    previous: "4.25%",
  },
];

export const MOCK_WHALE_ACTIVITY: WhaleActivity[] = [
  {
    id: "whale-1",
    asset: "BTC",
    amount: 1250,
    amountUsd: 78750000,
    direction: "outflow",
    fromAddress: "0xabc...123",
    toAddress: "0xdef...456",
    timestamp: hoursAgo(1),
    exchange: "Binance",
  },
  {
    id: "whale-2",
    asset: "ETH",
    amount: 25000,
    amountUsd: 87500000,
    direction: "inflow",
    fromAddress: "0x111...aaa",
    toAddress: "0x222...bbb",
    timestamp: hoursAgo(3),
    exchange: "Coinbase",
  },
  {
    id: "whale-3",
    asset: "USDT",
    amount: 50000000,
    amountUsd: 50000000,
    direction: "outflow",
    fromAddress: "0x333...ccc",
    toAddress: "0x444...ddd",
    timestamp: hoursAgo(6),
    exchange: "Kraken",
  },
  {
    id: "whale-4",
    asset: "BTC",
    amount: 800,
    amountUsd: 50400000,
    direction: "inflow",
    fromAddress: "0x555...eee",
    toAddress: "0x666...fff",
    timestamp: hoursAgo(9),
    exchange: null,
  },
];

export const MOCK_DAILY_REPORT: DailyReport = {
  date: now,
  summary:
    "Mercado cripto en fase de consolidación. BTC mantiene soporte en 60K con resistencia en 68K. Sentimiento institucional positivo por flujos ETF. Recomendación: cautela, vigilar ruptura de rango.",
  sections: {
    marketOverview:
      "BTC consolidando entre 60K-68K. Dominancia en 54%. Fear & Greed en 72 (Greed). Volumen decreciente sugiere falta de dirección.",
    keyEvents:
      "ETF inflows de $500M semanales. Fed hinta recorte de tasas. Upgrade de Ethereum desplegado exitosamente.",
    performance:
      "BTC +2.3% semanal, ETH +5.1%. Altcoins mixtas. Stablecoin supply en ATH ($200B).",
    outlook:
      "Corto plazo: rango probable. Medio plazo: sesgo alcista si BTC rompe 68K con volumen. Riesgo: CPI y FOMC en próximas semanas.",
  },
  timestamp: now,
};

export const MOCK_SINCE_LAST_VISIT: SinceLastVisitData = {
  lastLogin: hoursAgo(13),
  hoursSinceLogin: 13,
  greeting: "Buenos días",
  changes: [
    {
      id: "change-1",
      type: "new_opportunity",
      icon: "🟢",
      color: "green",
      title: "2 oportunidades nuevas",
      detail: "LINK y AVAX muestran setup alcista confirmado",
      timestamp: hoursAgo(8),
    },
    {
      id: "change-2",
      type: "invalidated",
      icon: "🔴",
      color: "red",
      title: "1 oportunidad invalidada",
      detail: "XRP no sostuvo soporte y se invalidó el setup",
      timestamp: hoursAgo(10),
    },
    {
      id: "change-3",
      type: "consensus_change",
      icon: "🟡",
      color: "yellow",
      title: "BTC cambió de HOLD → BUY ON PULLBACK",
      detail: "Technical Agent detectó ruptura de resistencia menor",
      timestamp: hoursAgo(6),
    },
    {
      id: "change-4",
      type: "institutional_flow",
      icon: "🔵",
      color: "blue",
      title: "ETH recibió acumulación institucional",
      detail: "ETF inflows de $120M en las últimas 24h",
      timestamp: hoursAgo(4),
    },
    {
      id: "change-5",
      type: "risk_change",
      icon: "🟠",
      color: "orange",
      title: "Tu riesgo total aumentó 8%",
      detail: "Mayor exposición en SOL sin stop-loss ajustado",
      timestamp: hoursAgo(5),
    },
    {
      id: "change-6",
      type: "portfolio_change",
      icon: "⚪",
      color: "white",
      title: "Tu portafolio ganó +2.3%",
      detail: "BTC y ETH lideraron las ganancias",
      timestamp: hoursAgo(1),
    },
    {
      id: "change-7",
      type: "macro_event",
      icon: "⚫",
      color: "black",
      title: "FED mañana",
      detail: "Decisión de tasas de interés - alto impacto esperado",
      timestamp: hoursAgo(2),
    },
  ],
  toReview: [
    { asset: "BTC", reason: "Cambio de consenso - requiere confirmación" },
    { asset: "SOL", reason: "Riesgo elevado sin stop-loss" },
    { asset: "LINK", reason: "Nueva oportunidad - revisar entrada" },
  ],
};

export const MOCK_TODAY_PRIORITIES: TodayPrioritiesData = {
  priorities: [
    {
      id: "prio-1",
      asset: "BTC",
      recommendation: "BUY ON PULLBACK",
      confidence: 82,
      risk: "medium",
      mainReason: "Ruptura de resistencia menor confirmada con volumen",
      expiresAt: new Date(Date.now() + 6 * 3600000).toISOString(),
      reasons: [
        { label: "Technical", confirmed: true },
        { label: "On-chain", confirmed: true },
        { label: "News", confirmed: true },
        { label: "Macro", confirmed: false },
      ],
    },
    {
      id: "prio-2",
      asset: "SOL",
      recommendation: "HOLD",
      confidence: 68,
      risk: "high",
      mainReason: "Alta volatilidad y sobreexposición en portafolio",
      expiresAt: null,
      reasons: [
        { label: "Technical", confirmed: true },
        { label: "On-chain", confirmed: false },
        { label: "News", confirmed: true },
        { label: "Macro", confirmed: false },
      ],
    },
    {
      id: "prio-3",
      asset: "LINK",
      recommendation: "BUY",
      confidence: 75,
      risk: "low",
      mainReason: "Acumulación institucional detectada + breakout de canal",
      expiresAt: new Date(Date.now() + 12 * 3600000).toISOString(),
      reasons: [
        { label: "Technical", confirmed: true },
        { label: "On-chain", confirmed: true },
        { label: "News", confirmed: false },
        { label: "Macro", confirmed: true },
      ],
    },
  ],
};

export const MOCK_AI_ACTIVITY: AIActivityData = {
  entries: [
    {
      id: "act-1",
      timestamp: hoursAgo(0.5),
      agent: "Consensus",
      action: "Consenso actualizado",
      detail: "BTC → BUY ON PULLBACK con 82% de confianza",
      decision: "BUY",
      confidence: 82,
    },
    {
      id: "act-2",
      timestamp: hoursAgo(1),
      agent: "News",
      action: "Noticia detectada",
      detail: "ETF Ethereum aprobado - impacto alto en ETH",
    },
    {
      id: "act-3",
      timestamp: hoursAgo(2),
      agent: "On-chain",
      action: "Acumulación detectada",
      detail: "Ballena movió 14k BTC a cold wallet - bullish",
    },
    {
      id: "act-4",
      timestamp: hoursAgo(3),
      agent: "Contrarian",
      action: "No confirma",
      detail: "Sentimiento demasiado greed - precaución",
    },
    {
      id: "act-5",
      timestamp: hoursAgo(4),
      agent: "Technical",
      action: "Señal generada",
      detail: "BTC rompió resistencia de 64K con volumen",
      decision: "BUY",
      confidence: 78,
    },
    {
      id: "act-6",
      timestamp: hoursAgo(5),
      agent: "Macro",
      action: "Sin cambios",
      detail: "DXY estable, funding positivo, sin eventos inmediatos",
    },
    {
      id: "act-7",
      timestamp: hoursAgo(6),
      agent: "Consensus",
      action: "Oportunidad enviada",
      detail: "LINK - BUY con 75% confianza - riesgo bajo",
      decision: "BUY",
      confidence: 75,
    },
    {
      id: "act-8",
      timestamp: hoursAgo(8),
      agent: "Technical",
      action: "Invalidación",
      detail: "XRP no sostuvo soporte de 0.58 - setup invalidado",
    },
  ],
};
