import {
  TrendingUp,
  Grid3x3,
  Square,
  Type,
  Eraser,
  Trash2,
  MousePointer2,
  Minus,
  ArrowUpRight,
  Spline,
  Pen,
} from "lucide-react";
import { useState } from "react";

export type DrawingTool = "none" | "trendline" | "fibonacci" | "rectangle" | "text" | "eraser" | "horizontal" | "ray" | "extended" | "brush";

interface DrawingToolbarProps {
  activeTool: DrawingTool;
  onToolChange: (tool: DrawingTool) => void;
  color: string;
  onColorChange: (color: string) => void;
  onClearAll: () => void;
}

const TOOLS: { tool: DrawingTool; label: string; icon: typeof TrendingUp }[] = [
  { tool: "none", label: "Cursor", icon: MousePointer2 },
  { tool: "trendline", label: "Trend Line", icon: TrendingUp },
  { tool: "horizontal", label: "H-Line", icon: Minus },
  { tool: "ray", label: "Ray", icon: ArrowUpRight },
  { tool: "extended", label: "Extended", icon: Spline },
  { tool: "fibonacci", label: "Fibonacci", icon: Grid3x3 },
  { tool: "rectangle", label: "Rectangle", icon: Square },
  { tool: "brush", label: "Brush", icon: Pen },
  { tool: "text", label: "Text", icon: Type },
  { tool: "eraser", label: "Eraser", icon: Eraser },
];

const COLORS = [
  "#7c3aed", // primary (purple)
  "#22d39a", // success (green)
  "#ff5f6d", // danger (red)
  "#f59e0b", // warning (amber)
  "#3b82f6", // blue
  "#ffffff", // white
  "#a855f7", // purple light
  "#ec4899", // pink
];

export function DrawingToolbar({
  activeTool,
  onToolChange,
  color,
  onColorChange,
  onClearAll,
}: DrawingToolbarProps) {
  const [showColorPicker, setShowColorPicker] = useState(false);

  return (
    <div className="panel p-2 flex items-center gap-1.5 flex-wrap">
      {/* Drawing tools */}
      {TOOLS.map((tool) => {
        const Icon = tool.icon;
        const isActive = activeTool === tool.tool;
        return (
          <button
            key={tool.tool}
            onClick={() => onToolChange(tool.tool)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${
              isActive
                ? "bg-[var(--color-primary)] text-white"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
            }`}
            title={tool.label}
          >
            <Icon size={14} />
            <span className="hidden sm:inline">{tool.label}</span>
            {isActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            )}
          </button>
        );
      })}

      {/* Divider */}
      <div className="w-px h-6 bg-[var(--color-border)] mx-1" />

      {/* Color picker */}
      <div className="relative">
        <button
          onClick={() => setShowColorPicker(!showColorPicker)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)] transition-colors"
          title="Color"
        >
          <span
            className="w-4 h-4 rounded border border-[var(--color-border)]"
            style={{ backgroundColor: color }}
          />
          <span className="hidden sm:inline">Color</span>
        </button>
        {showColorPicker && (
          <div className="absolute top-full left-0 mt-1 z-50 panel p-2 shadow-lg">
            <div className="grid grid-cols-4 gap-1.5">
              {COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    onColorChange(c);
                    setShowColorPicker(false);
                  }}
                  className={`w-6 h-6 rounded border-2 transition-transform hover:scale-110 ${
                    color === c ? "border-white" : "border-transparent"
                  }`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-6 bg-[var(--color-border)] mx-1" />

      {/* Clear all */}
      <button
        onClick={onClearAll}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-bold text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 transition-colors"
        title="Clear all drawings"
      >
        <Trash2 size={14} />
        <span className="hidden sm:inline">Clear All</span>
      </button>
    </div>
  );
}
