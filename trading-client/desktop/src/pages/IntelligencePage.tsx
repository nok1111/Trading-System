import { useEffect, useState } from "react";
import { RegimeBanner } from "../components/intelligence/RegimeBanner";
import { FearGreedGauge } from "../components/intelligence/FearGreedGauge";
import { DominanceChart } from "../components/intelligence/DominanceChart";
import { NewsFeed } from "../components/intelligence/NewsFeed";
import { MacroCalendar } from "../components/intelligence/MacroCalendar";
import { WhaleFeed } from "../components/intelligence/WhaleFeed";
import { AISuggestionsPanel } from "../components/intelligence/AISuggestionsPanel";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { InfoPanel } from "../components/common/Tooltip";
import {
  getMarketOverview,
  getFearGreed,
  getDominance,
  getNews,
  getMacroEvents,
  getWhaleActivity,
} from "../lib/intelligenceApi";
import type {
  MarketOverview,
  FearGreedData,
  DominanceData,
  NewsItem,
  MacroEvent,
  WhaleActivity,
} from "../lib/intelligenceTypes";

export function IntelligencePage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [dominance, setDominance] = useState<DominanceData | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [macro, setMacro] = useState<MacroEvent[]>([]);
  const [whales, setWhales] = useState<WhaleActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [ov, fg, dom, n, m, w] = await Promise.all([
        getMarketOverview(),
        getFearGreed(),
        getDominance(),
        getNews(10),
        getMacroEvents(),
        getWhaleActivity(10),
      ]);
      if (!alive) return;
      setOverview(ov);
      setFearGreed(fg);
      setDominance(dom);
      setNews(n);
      setMacro(m);
      setWhales(w);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 space-y-4 max-w-[1200px] mx-auto">
      <InfoPanel title="Market Intelligence - Que ver aqui" className="mb-4">
        <p><strong>Regime Banner:</strong> Muestra si el mercado esta en tendencia, lateral, o volatil. Te ayuda a elegir la estrategia correcta.</p>
        <p><strong>Fear & Greed:</strong> Indicador de sentimiento del mercado. Extremo fear = posible compra, extreme greed = posible venta.</p>
        <p><strong>BTC Dominance:</strong> Que porcentaje del mercado es BTC. Si sube, los altcoins suelen bajar.</p>
        <p><strong>Noticias y Eventos Macro:</strong> Eventos economicos que pueden mover precios (Fed, CPI, etc).</p>
        <p><strong>Actividad Whale:</strong> Grandes movimientos de ballenas que pueden indicar acumulacion o distribucion.</p>
      </InfoPanel>

      <RegimeBanner overview={overview} loading={loading} />

      <AISuggestionsPanel />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Fear & Greed</h3>
          <FearGreedGauge data={fearGreed} loading={loading} />
        </div>
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">BTC Dominance</h3>
          <DominanceChart data={dominance} loading={loading} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Noticias</h3>
          {loading ? <LoadingSkeleton lines={4} /> : <NewsFeed news={news} />}
        </div>
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Eventos Macro</h3>
          {loading ? <LoadingSkeleton lines={4} /> : <MacroCalendar events={macro} />}
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Actividad Whale</h3>
        {loading ? <LoadingSkeleton lines={4} /> : <WhaleFeed activities={whales} />}
      </div>
    </div>
  );
}
