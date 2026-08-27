import { useState, useEffect, useCallback, type ReactNode } from "react";
import { Wallet, CandlestickChart, Zap, Activity, Fish, Table, MessageSquare, Bot, Newspaper, Shield } from "lucide-react";
import { WidgetWrapper } from "./WidgetWrapper";
import { WidgetPalette, getWidgetMeta, type WidgetType } from "./WidgetPalette";
import { DashboardToolbar, type PresetName } from "./DashboardToolbar";

// ─── Types ────────────────────────────────────────────────────────────────────

interface WidgetInstance {
  id: string;
  type: WidgetType;
  span: number;
}

interface LayoutConfig {
  preset: PresetName;
  widgets: WidgetInstance[];
}

const LAYOUT_KEY = "dashboard_layout";

// ─── Presets ──────────────────────────────────────────────────────────────────

const PRESET_LAYOUTS: Record<Exclude<PresetName, "Custom">, WidgetType[]> = {
  "Day Trader": ["PortfolioHero", "PriceChart", "SignalFeed", "PositionsTable", "FearGreedGauge", "NetExposure"],
  HODLer: ["PortfolioHero", "PriceChart", "FearGreedGauge", "NewsFeed", "NetExposure"],
  "Bot Operator": ["PortfolioHero", "BotStatus", "PriceChart", "PositionsTable", "AlvoraChat"],
  Analyst: ["PortfolioHero", "PriceChart", "SignalFeed", "WhaleFeed", "FearGreedGauge", "NewsFeed", "NetExposure"],
};

function buildPresetLayout(preset: Exclude<PresetName, "Custom">): WidgetInstance[] {
  const types = PRESET_LAYOUTS[preset] || [];
  return types.map((type, i) => ({
    id: `${type}_${i}`,
    type,
    span: getWidgetMeta(type)?.defaultSpan || 1,
  }));
}

const DEFAULT_LAYOUT: LayoutConfig = {
  preset: "Day Trader",
  widgets: buildPresetLayout("Day Trader"),
};

// ─── Widget content renderers ─────────────────────────────────────────────────
// These are placeholder renderers that show a summary view.
// In production, these would render the actual full widget components.

function WidgetContent({ type }: { type: WidgetType }): ReactNode {
  switch (type) {
    case "PortfolioHero":
      return (
        <div className="space-y-2">
          <div className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">Total Equity</div>
          <div className="text-[28px] font-extrabold text-[var(--color-text)]">$--</div>
          <div className="text-[12px] text-[var(--color-text-muted)]">Connect a broker to see your portfolio</div>
        </div>
      );
    case "PriceChart":
      return (
        <div className="flex items-center justify-center h-[200px] text-[var(--color-text-muted)] text-sm">
          <CandlestickChart size={32} className="opacity-30" />
        </div>
      );
    case "SignalFeed":
      return (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
              <Zap size={12} className="text-[var(--color-warning)]" />
              <span>Loading signals...</span>
            </div>
          ))}
        </div>
      );
    case "FearGreedGauge":
      return (
        <div className="flex items-center justify-center h-[120px]">
          <div className="text-center">
            <Activity size={32} className="text-[var(--color-warning)] mx-auto mb-2" />
            <div className="text-[12px] text-[var(--color-text-muted)]">Sentiment loading...</div>
          </div>
        </div>
      );
    case "WhaleFeed":
      return (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
              <Fish size={12} className="text-[var(--color-primary)]" />
              <span>Waiting for whale activity...</span>
            </div>
          ))}
        </div>
      );
    case "PositionsTable":
      return (
        <div className="text-center py-8 text-[var(--color-text-muted)] text-sm">
          <Table size={24} className="mx-auto mb-2 opacity-30" />
          No open positions
        </div>
      );
    case "AlvoraChat":
      return (
        <div className="flex items-center justify-center h-[150px] text-[var(--color-text-muted)] text-sm">
          <MessageSquare size={24} className="opacity-30 mr-2" />
          Ask Alvora anything...
        </div>
      );
    case "BotStatus":
      return (
        <div className="text-center py-6 text-[var(--color-text-muted)] text-sm">
          <Bot size={24} className="mx-auto mb-2 opacity-30" />
          No active bots
        </div>
      );
    case "NewsFeed":
      return (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
              <Newspaper size={12} className="text-[var(--color-text-muted)]" />
              <span>Loading news...</span>
            </div>
          ))}
        </div>
      );
    case "NetExposure":
      return (
        <div className="text-center py-6 text-[var(--color-text-muted)] text-sm">
          <Shield size={24} className="mx-auto mb-2 opacity-30" />
          No exposure data
        </div>
      );
    default:
      return null;
  }
}

const WIDGET_ICONS: Record<WidgetType, ReactNode> = {
  PortfolioHero: <Wallet size={14} />,
  PriceChart: <CandlestickChart size={14} />,
  SignalFeed: <Zap size={14} />,
  FearGreedGauge: <Activity size={14} />,
  WhaleFeed: <Fish size={14} />,
  PositionsTable: <Table size={14} />,
  AlvoraChat: <MessageSquare size={14} />,
  BotStatus: <Bot size={14} />,
  NewsFeed: <Newspaper size={14} />,
  NetExposure: <Shield size={14} />,
};

// ─── Main component ───────────────────────────────────────────────────────────

export function DashboardGrid() {
  const [layout, setLayout] = useState<LayoutConfig>(DEFAULT_LAYOUT);
  const [editMode, setEditMode] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Load layout from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LAYOUT_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as LayoutConfig;
        if (parsed.widgets && parsed.widgets.length > 0) {
          setLayout(parsed);
        }
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  // Persist layout to localStorage whenever it changes
  const saveLayout = useCallback((newLayout: LayoutConfig) => {
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(newLayout));
    } catch {
      // ignore storage errors
    }
  }, []);

  const updateLayout = useCallback(
    (updater: (prev: LayoutConfig) => LayoutConfig) => {
      setLayout((prev) => {
        const next = updater(prev);
        saveLayout(next);
        return next;
      });
    },
    [saveLayout],
  );

  // ─── Drag and drop handlers ─────────────────────────────────────────────────

  const handleDragStart = (index: number) => (e: React.DragEvent) => {
    if (!editMode) {
      e.preventDefault();
      return;
    }
    setDragIndex(index);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
  };

  const handleDragOver = (index: number) => (e: React.DragEvent) => {
    if (!editMode) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverIndex !== index) setDragOverIndex(index);
  };

  const handleDrop = (index: number) => (e: React.DragEvent) => {
    if (!editMode) return;
    e.preventDefault();
    const fromIndex = dragIndex;
    if (fromIndex === null || fromIndex === index) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }

    updateLayout((prev) => {
      const widgets = [...prev.widgets];
      const [moved] = widgets.splice(fromIndex, 1);
      widgets.splice(index, 0, moved);
      return { ...prev, widgets, preset: "Custom" };
    });

    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  // ─── Widget management ──────────────────────────────────────────────────────

  const handleAddWidget = (type: WidgetType) => {
    updateLayout((prev) => ({
      ...prev,
      preset: "Custom",
      widgets: [...prev.widgets, { id: `${type}_${Date.now()}`, type, span: getWidgetMeta(type)?.defaultSpan || 1 }],
    }));
  };

  const handleRemoveWidget = (id: string) => {
    updateLayout((prev) => ({
      ...prev,
      preset: "Custom",
      widgets: prev.widgets.filter((w) => w.id !== id),
    }));
  };

  const handlePresetChange = (preset: PresetName) => {
    if (preset === "Custom") return;
    const widgets = buildPresetLayout(preset);
    const newLayout = { preset, widgets };
    setLayout(newLayout);
    saveLayout(newLayout);
  };

  const handleReset = () => {
    const newLayout = { ...DEFAULT_LAYOUT };
    setLayout(newLayout);
    saveLayout(newLayout);
  };

  const handleToggleEdit = () => {
    setEditMode((prev) => !prev);
    setShowPalette(false);
  };

  const activeTypes = layout.widgets.map((w) => w.type);

  return (
    <div className="space-y-4">
      <DashboardToolbar
        activePreset={layout.preset}
        onPresetChange={handlePresetChange}
        onAddWidget={() => setShowPalette(!showPalette)}
        onReset={handleReset}
        editMode={editMode}
        onToggleEdit={handleToggleEdit}
      />

      {showPalette && editMode && (
        <WidgetPalette onAdd={(type) => { handleAddWidget(type); }} activeTypes={activeTypes} />
      )}

      {editMode && (
        <div className="panel p-3 border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/5">
          <p className="text-[12px] text-[var(--color-primary)] flex items-center gap-2">
            <Activity size={14} />
            Edit mode active — drag widgets to reorder, click X to remove, or add new widgets from the palette.
          </p>
        </div>
      )}

      {/* Grid layout */}
      <div
        className="grid gap-4"
        style={{
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
        }}
      >
        {layout.widgets.map((widget, index) => {
          const meta = getWidgetMeta(widget.type);
          if (!meta) return null;
          return (
            <div
              key={widget.id}
              style={{
                gridColumn: widget.span > 1 ? `span ${Math.min(widget.span, 3)}` : undefined,
              }}
            >
              <WidgetWrapper
                title={meta.label}
                icon={WIDGET_ICONS[widget.type]}
                onRemove={() => handleRemoveWidget(widget.id)}
                onDragStart={handleDragStart(index)}
                onDragEnd={handleDragEnd}
                onDragOver={handleDragOver(index)}
                onDrop={handleDrop(index)}
                isDragging={dragIndex === index}
                isDragOver={dragOverIndex === index && dragIndex !== index}
                editMode={editMode}
              >
                <WidgetContent type={widget.type} />
              </WidgetWrapper>
            </div>
          );
        })}
      </div>

      {layout.widgets.length === 0 && (
        <div className="panel p-12 text-center">
          <p className="text-[var(--color-text-muted)] text-sm mb-4">No widgets on your dashboard</p>
          <button
            onClick={() => setShowPalette(true)}
            className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-[13px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            Add your first widget
          </button>
        </div>
      )}
    </div>
  );
}
