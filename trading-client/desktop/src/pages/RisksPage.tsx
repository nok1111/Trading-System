import { useEffect, useState } from "react";
import { TrendingDown, Waves, AlertTriangle, Zap } from "lucide-react";
import { CrashRiskGauge } from "../components/intelligence/CrashRiskGauge";
import { WhaleFeed } from "../components/intelligence/WhaleFeed";
import { AlertList } from "../components/intelligence/AlertList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getAlerts, getWhaleActivity, getNews } from "../lib/intelligenceApi";
import type { IntelligenceAlert, WhaleActivity, NewsItem } from "../lib/intelligenceTypes";
import { cn } from "../lib/utils";

export function RisksPage() {
  const [alerts, setAlerts] = useState<IntelligenceAlert[]>([]);
  const [whales, setWhales] = useState<WhaleActivity[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [a, w, n] = await Promise.all([
        getAlerts(20),
        getWhaleActivity(15),
        getNews(20),
      ]);
      if (!alive) return;
      setAlerts(a);
      setWhales(w);
      setNews(n);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  const crashRisk = alerts.find((a) => a.crashRisk != null)?.crashRisk ?? null;
  const highImpactNews = news.filter((n) => n.impact === "high");
  const largeWhales = whales.filter((w) => w.amountUsd >= 500000);

  return (
    <div className="p-5 space-y-4 max-w-[900px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-[var(--color-warning)]" />
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Alertas de Mercado</h2>
      </div>

      {/* Crash Risk + Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
            <TrendingDown size={14} className="text-[var(--color-danger)]" />
            Crash Risk
          </h3>
          {loading ? <LoadingSkeleton lines={3} /> : <CrashRiskGauge crashRisk={crashRisk} />}
        </div>
        <div className="panel p-4 space-y-2">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1 flex items-center gap-2">
            <Waves size={14} className="text-[var(--color-primary)]" />
            Whale Alerts
          </h3>
          <div className="text-[24px] font-extrabold text-[var(--color-text)]">{largeWhales.length}</div>
          <p className="text-[10px] text-[var(--color-text-muted)]">Movimientos &gt; $500K detectados</p>
        </div>
        <div className="panel p-4 space-y-2">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1 flex items-center gap-2">
            <AlertTriangle size={14} className="text-[var(--color-warning)]" />
            Noticias de Alto Impacto
          </h3>
          <div className="text-[24px] font-extrabold text-[var(--color-text)]">{highImpactNews.length}</div>
          <p className="text-[10px] text-[var(--color-text-muted)]">Eventos que pueden mover el mercado</p>
        </div>
      </div>

      {/* High-impact news */}
      {highImpactNews.length > 0 && (
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
            <AlertTriangle size={14} className="text-[var(--color-warning)]" />
            Noticias de Alto Impacto
          </h3>
          <div className="space-y-2">
            {highImpactNews.map((n) => (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-warning)]/30 border-l-3 border-l-[var(--color-warning)] p-3 hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-bold text-[var(--color-text)]">{n.source}</span>
                  <span className={cn(
                    "text-[10px] font-bold uppercase px-2 h-5 rounded flex items-center",
                    n.sentiment === "negative" ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]" :
                    n.sentiment === "positive" ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" :
                    "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                  )}>
                    {n.sentiment}
                  </span>
                </div>
                <p className="text-[12px] text-[var(--color-text)] font-semibold">{n.title}</p>
                {n.summary && <p className="text-[11px] text-[var(--color-text-muted)] mt-1 line-clamp-2">{n.summary}</p>}
                {n.assets.length > 0 && (
                  <div className="flex gap-1 mt-2">
                    {n.assets.slice(0, 5).map((a) => (
                      <span key={a} className="text-[10px] font-bold px-1.5 h-4 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] flex items-center">
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Large whale movements */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
          <Waves size={14} className="text-[var(--color-primary)]" />
          Movimientos Whale Grandes
        </h3>
        {loading ? <LoadingSkeleton lines={4} /> : <WhaleFeed activities={largeWhales.length > 0 ? largeWhales : whales} />}
      </div>

      {/* Risk alerts */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
          <AlertTriangle size={14} className="text-[var(--color-danger)]" />
          Alertas de Riesgo Activas
        </h3>
        {loading ? <LoadingSkeleton lines={4} /> : <AlertList alerts={alerts} />}
      </div>
    </div>
  );
}
