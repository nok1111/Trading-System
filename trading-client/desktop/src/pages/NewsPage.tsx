import { useEffect, useState, useMemo } from "react";
import { NewsFeed } from "../components/intelligence/NewsFeed";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getNews } from "../lib/intelligenceApi";
import { cn } from "../lib/utils";
import type { NewsItem } from "../lib/intelligenceTypes";

type SentimentFilter = "all" | "positive" | "negative" | "neutral";
type ImpactFilter = "all" | "high" | "medium" | "low";

export function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sentiment, setSentiment] = useState<SentimentFilter>("all");
  const [impact, setImpact] = useState<ImpactFilter>("all");
  const [source, setSource] = useState<string>("all");

  useEffect(() => {
    let alive = true;
    const doLoad = async () => {
      try {
        const n = await getNews(50);
        if (!alive) return;
        setNews(n);
      } catch { /* ignore */ }
      if (alive) setLoading(false);
    };
    doLoad();
    const id = setInterval(doLoad, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const sources = useMemo(() => {
    const s = new Set<string>();
    news.forEach((n) => s.add(n.source));
    return ["all", ...Array.from(s).sort()];
  }, [news]);

  const filtered = useMemo(() => {
    return news.filter((n) => {
      if (sentiment !== "all" && n.sentiment !== sentiment) return false;
      if (impact !== "all" && n.impact !== impact) return false;
      if (source !== "all" && n.source !== source) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!n.title.toLowerCase().includes(q) && !n.summary.toLowerCase().includes(q) && !n.assets.some((a) => a.toLowerCase().includes(q))) return false;
      }
      return true;
    });
  }, [news, sentiment, impact, source, search]);

  const stats = useMemo(() => {
    const pos = news.filter((n) => n.sentiment === "positive").length;
    const neg = news.filter((n) => n.sentiment === "negative").length;
    const high = news.filter((n) => n.impact === "high").length;
    return { pos, neg, high, total: news.length };
  }, [news]);

  const filterBtn = (active: boolean) =>
    cn("px-2.5 h-7 rounded-[6px] text-[11px] font-bold transition-colors", active ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]");

  return (
    <div className="p-5 max-w-[800px] mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Noticias del Mercado</h2>
        <div className="flex items-center gap-3 text-[11px] text-[var(--color-text-muted)]">
          <span className="text-[var(--color-success)] font-bold">{stats.pos} positivas</span>
          <span className="text-[var(--color-danger)] font-bold">{stats.neg} negativas</span>
          <span className="text-[var(--color-warning)] font-bold">{stats.high} alto impacto</span>
        </div>
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Buscar por título, resumen o activo..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full h-9 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
      />

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex gap-1">
          <button className={filterBtn(sentiment === "all")} onClick={() => setSentiment("all")}>Todo</button>
          <button className={filterBtn(sentiment === "positive")} onClick={() => setSentiment("positive")}>Positivas</button>
          <button className={filterBtn(sentiment === "negative")} onClick={() => setSentiment("negative")}>Negativas</button>
          <button className={filterBtn(sentiment === "neutral")} onClick={() => setSentiment("neutral")}>Neutrales</button>
        </div>
        <span className="text-[var(--color-border)]">|</span>
        <div className="flex gap-1">
          <button className={filterBtn(impact === "all")} onClick={() => setImpact("all")}>Todo impacto</button>
          <button className={filterBtn(impact === "high")} onClick={() => setImpact("high")}>Alto</button>
          <button className={filterBtn(impact === "medium")} onClick={() => setImpact("medium")}>Medio</button>
          <button className={filterBtn(impact === "low")} onClick={() => setImpact("low")}>Bajo</button>
        </div>
        <span className="text-[var(--color-border)]">|</span>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="h-7 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[11px] font-bold text-[var(--color-text)] outline-none"
        >
          {sources.map((s) => (
            <option key={s} value={s}>{s === "all" ? "Todas las fuentes" : s}</option>
          ))}
        </select>
      </div>

      <div className="text-[11px] text-[var(--color-text-muted)]">
        {filtered.length} de {news.length} noticias
      </div>

      {loading ? <LoadingSkeleton lines={6} /> : <NewsFeed news={filtered} />}
    </div>
  );
}
