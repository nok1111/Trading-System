import { ChevronDown, Plus, RotateCcw, Pencil, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export type PresetName = "Day Trader" | "HODLer" | "Bot Operator" | "Analyst" | "Custom";

export const PRESET_NAMES: PresetName[] = ["Day Trader", "HODLer", "Bot Operator", "Analyst", "Custom"];

interface DashboardToolbarProps {
  activePreset: PresetName;
  onPresetChange: (preset: PresetName) => void;
  onAddWidget: () => void;
  onReset: () => void;
  editMode: boolean;
  onToggleEdit: () => void;
}

export function DashboardToolbar({
  activePreset,
  onPresetChange,
  onAddWidget,
  onReset,
  editMode,
  onToggleEdit,
}: DashboardToolbarProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-3">
        {/* Preset selector dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)] hover:bg-[var(--color-surface-2)] transition-colors"
          >
            <span className="text-[var(--color-text-muted)]">Layout:</span>
            <span>{activePreset}</span>
            <ChevronDown size={14} className="text-[var(--color-text-muted)]" />
          </button>
          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-1 z-50 panel p-1 min-w-[160px] shadow-lg">
              {PRESET_NAMES.map((name) => (
                <button
                  key={name}
                  onClick={() => {
                    onPresetChange(name);
                    setDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 rounded text-[12px] font-medium transition-colors ${
                    activePreset === name
                      ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
                      : "text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Add widget button */}
        <button
          onClick={onAddWidget}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--color-primary)]/15 text-[var(--color-primary)] text-[12px] font-bold hover:bg-[var(--color-primary)]/25 transition-colors"
        >
          <Plus size={14} />
          Add Widget
        </button>

        {/* Reset layout button */}
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)] transition-colors"
          title="Reset to default layout"
        >
          <RotateCcw size={14} />
          Reset
        </button>
      </div>

      {/* Edit mode toggle */}
      <button
        onClick={onToggleEdit}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-colors ${
          editMode
            ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
            : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        }`}
      >
        {editMode ? <Check size={14} /> : <Pencil size={14} />}
        {editMode ? "Done Editing" : "Edit Layout"}
      </button>
    </div>
  );
}
