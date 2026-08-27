import { useRef, useState } from "react";
import { getBlockDef, CATEGORY_COLORS, type BlockCategory } from "./BlockPalette";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface StrategyBlock {
  id: string;
  type: string;
  category: BlockCategory;
  params: Record<string, number | string | boolean>;
}

interface BlockCanvasProps {
  blocks: StrategyBlock[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onRemove: (id: string) => void;
  onAddBlock: (type: string) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function BlockCanvas({
  blocks,
  selectedId,
  onSelect,
  onRemove,
  onAddBlock,
  onReorder,
}: BlockCanvasProps) {
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const blockType = e.dataTransfer.getData("blockType");
    if (blockType) {
      onAddBlock(blockType);
    }
    setDragOverIndex(null);
    setDragIndex(null);
  };

  const handleBlockDragStart = (index: number) => (e: React.DragEvent) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("blockIndex", String(index));
  };

  const handleBlockDragOver = (index: number) => (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverIndex(index);
  };

  const handleBlockDrop = (index: number) => (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const fromIndexStr = e.dataTransfer.getData("blockIndex");
    const fromIndex = fromIndexStr ? parseInt(fromIndexStr, 10) : null;
    if (fromIndex !== null && fromIndex !== index) {
      onReorder(fromIndex, index);
    }
    setDragOverIndex(null);
    setDragIndex(null);
  };

  // ─── Render SVG connections ─────────────────────────────────────────────────
  const connections: { x1: number; y1: number; x2: number; y2: number }[] = [];
  for (let i = 0; i < blocks.length - 1; i++) {
    // Each block is ~70px tall with 12px gap; connection from bottom-center to top-center
    const y1 = (i + 1) * 80 - 10;
    const y2 = (i + 1) * 80 + 2;
    connections.push({ x1: 50, y1, x2: 50, y2 });
  }

  return (
    <div
      ref={canvasRef}
      className="panel p-6 min-h-[500px] relative overflow-y-auto"
      style={{ maxHeight: "70vh" }}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={(e) => {
        if (e.target === canvasRef.current) onSelect(null);
      }}
    >
      {blocks.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-[400px] text-center">
          <div className="text-[var(--color-text-muted)] text-sm mb-2">
            Drag blocks here to build your strategy
          </div>
          <div className="text-[var(--color-text-muted)] text-[12px]">
            Start with an Entry block, then add Exit, Sizing, and Risk filters
          </div>
        </div>
      ) : (
        <div className="relative">
          {/* SVG connection lines */}
          <svg
            className="absolute left-0 top-0 pointer-events-none"
            style={{ width: "100%", height: `${blocks.length * 80}px` }}
          >
            {connections.map((conn, i) => (
              <line
                key={i}
                x1="50%"
                y1={conn.y1}
                x2="50%"
                y2={conn.y2}
                stroke="var(--color-primary)"
                strokeWidth="2"
                strokeDasharray="4 4"
                opacity="0.5"
              />
            ))}
          </svg>

          {/* Blocks in flow layout */}
          <div className="space-y-3 relative">
            {blocks.map((block, index) => {
              const def = getBlockDef(block.type);
              if (!def) return null;
              const Icon = def.icon;
              const color = CATEGORY_COLORS[block.category];
              const isSelected = selectedId === block.id;
              const isDragOver = dragOverIndex === index && dragIndex !== index;
              const isDragging = dragIndex === index;

              return (
                <div
                  key={block.id}
                  draggable
                  onDragStart={handleBlockDragStart(index)}
                  onDragOver={handleBlockDragOver(index)}
                  onDrop={handleBlockDrop(index)}
                  onDragEnd={() => { setDragIndex(null); setDragOverIndex(null); }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(block.id);
                  }}
                  className={`flex items-center gap-3 p-3.5 rounded-xl border-2 cursor-pointer transition-all ${
                    isSelected
                      ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                      : "border-[var(--color-border)] hover:border-[var(--color-primary)]/50"
                  } ${isDragging ? "opacity-50" : ""} ${isDragOver ? "border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/30" : ""}`}
                  style={{ borderLeftColor: color, borderLeftWidth: "4px" }}
                >
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0" style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` }}>
                    <Icon size={16} style={{ color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-bold text-[var(--color-text)]">{def.label}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold" style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`, color }}>
                        {def.category}
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                      {Object.entries(block.params).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join("  |  ")}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove(block.id);
                    }}
                    className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)] p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors flex-shrink-0"
                    title="Remove block"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
