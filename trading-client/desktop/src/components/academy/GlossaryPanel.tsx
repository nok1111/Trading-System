import { useState, useMemo } from "react";
import { Search, ChevronDown, BookOpen } from "lucide-react";
import {
  GLOSSARY_TERMS,
  GLOSSARY_CATEGORIES,
  GLOSSARY_CATEGORY_LABELS,
  type GlossaryTerm,
} from "../../data/glossary";

export function GlossaryPanel() {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [expandedTerm, setExpandedTerm] = useState<string | null>(null);

  const filteredTerms = useMemo(() => {
    let terms: GlossaryTerm[] =
      activeCategory === "all"
        ? GLOSSARY_TERMS
        : GLOSSARY_TERMS.filter((t) => t.category === activeCategory);

    if (query.trim()) {
      const q = query.toLowerCase();
      terms = terms.filter(
        (t) =>
          t.term.toLowerCase().includes(q) ||
          t.definition.toLowerCase().includes(q),
      );
    }

    return [...terms].sort((a, b) => a.term.localeCompare(b.term));
  }, [query, activeCategory]);

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar término..."
          className="w-full pl-9 pr-4 py-2.5 rounded-xl text-[13px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-colors"
        />
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setActiveCategory("all")}
          className="px-3 py-1 rounded-full text-[11px] font-bold transition-all"
          style={{
            background:
              activeCategory === "all"
                ? "var(--color-primary)"
                : "var(--color-surface-2)",
            color:
              activeCategory === "all"
                ? "white"
                : "var(--color-text-muted)",
            border:
              activeCategory === "all"
                ? "1px solid var(--color-primary)"
                : "1px solid var(--color-border)",
          }}
        >
          Todos ({GLOSSARY_TERMS.length})
        </button>
        {GLOSSARY_CATEGORIES.map((cat) => {
          const count = GLOSSARY_TERMS.filter((t) => t.category === cat).length;
          const isActive = activeCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="px-3 py-1 rounded-full text-[11px] font-bold transition-all"
              style={{
                background: isActive
                  ? "var(--color-primary)"
                  : "var(--color-surface-2)",
                color: isActive ? "white" : "var(--color-text-muted)",
                border: isActive
                  ? "1px solid var(--color-primary)"
                  : "1px solid var(--color-border)",
              }}
            >
              {GLOSSARY_CATEGORY_LABELS[cat]} ({count})
            </button>
          );
        })}
      </div>

      {/* Results count */}
      <div className="text-[11px] text-[var(--color-text-muted)] font-medium">
        {filteredTerms.length} {filteredTerms.length === 1 ? "término" : "términos"}
        {query && ` para "${query}"`}
      </div>

      {/* Terms list */}
      <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
        {filteredTerms.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <BookOpen
              size={32}
              className="text-[var(--color-text-muted)] mb-2 opacity-50"
            />
            <div className="text-[13px] text-[var(--color-text-muted)]">
              No se encontraron términos
            </div>
          </div>
        ) : (
          filteredTerms.map((term) => {
            const isExpanded = expandedTerm === term.term;
            return (
              <div
                key={term.term}
                className="rounded-xl overflow-hidden transition-all"
                style={{
                  background: isExpanded
                    ? "color-mix(in srgb, var(--color-primary) 6%, var(--color-surface))"
                    : "var(--color-surface)",
                  border: `1px solid ${
                    isExpanded
                      ? "color-mix(in srgb, var(--color-primary) 30%, transparent)"
                      : "var(--color-border)"
                  }`,
                }}
              >
                <button
                  onClick={() =>
                    setExpandedTerm(isExpanded ? null : term.term)
                  }
                  className="w-full flex items-center gap-3 p-3 text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-bold text-[var(--color-text)]">
                        {term.term}
                      </span>
                      <span
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase"
                        style={{
                          background: "var(--color-surface-2)",
                          color: "var(--color-text-muted)",
                        }}
                      >
                        {GLOSSARY_CATEGORY_LABELS[term.category]}
                      </span>
                    </div>
                    {!isExpanded && (
                      <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate">
                        {term.definition}
                      </div>
                    )}
                  </div>
                  <ChevronDown
                    size={16}
                    className="text-[var(--color-text-muted)] flex-shrink-0 transition-transform"
                    style={{
                      transform: isExpanded ? "rotate(180deg)" : "none",
                    }}
                  />
                </button>

                {isExpanded && (
                  <div className="px-3 pb-3 space-y-2 animate-fade-in-up">
                    <p className="text-[12px] text-[var(--color-text)] leading-relaxed">
                      {term.definition}
                    </p>
                    {term.example && (
                      <div
                        className="p-2.5 rounded-lg text-[11px] leading-relaxed"
                        style={{
                          background: "var(--color-surface-2)",
                          border: "1px solid var(--color-border)",
                        }}
                      >
                        <span className="font-bold text-[var(--color-text-muted)]">
                          Ejemplo:{" "}
                        </span>
                        <span className="text-[var(--color-text)]">
                          {term.example}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
