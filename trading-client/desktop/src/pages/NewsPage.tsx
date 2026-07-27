import { useEffect, useState } from "react";
import { NewsFeed } from "../components/intelligence/NewsFeed";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getNews } from "../lib/intelligenceApi";
import type { NewsItem } from "../lib/intelligenceTypes";

export function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const n = await getNews(30);
      if (!alive) return;
      setNews(n);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 max-w-[700px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Noticias</h2>
      {loading ? <LoadingSkeleton lines={6} /> : <NewsFeed news={news} />}
    </div>
  );
}
