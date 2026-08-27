import { getBlockDef } from "./BlockPalette";
import type { StrategyBlock } from "./BlockCanvas";

interface BlockConfigProps {
  block: StrategyBlock | null;
  onUpdate: (id: string, params: Record<string, number | string | boolean>) => void;
}

export function BlockConfig({ block, onUpdate }: BlockConfigProps) {
  if (!block) {
    return (
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-2">Configuration</h3>
        <div className="text-center py-8 text-[var(--color-text-muted)] text-[12px]">
          Select a block to edit its parameters
        </div>
      </div>
    );
  }

  const def = getBlockDef(block.type);
  if (!def) {
    return (
      <div className="panel p-4">
        <div className="text-[var(--color-danger)] text-[12px]">Unknown block type: {block.type}</div>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1">{def.label}</h3>
      <p className="text-[11px] text-[var(--color-text-muted)] mb-4">{def.description}</p>

      <div className="space-y-3">
        {def.paramDefs.map((param) => {
          const value = block.params[param.key] ?? param.default;

          if (param.type === "select") {
            return (
              <div key={param.key}>
                <label className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide block mb-1">
                  {param.label}
                </label>
                <select
                  value={String(value)}
                  onChange={(e) => onUpdate(block.id, { ...block.params, [param.key]: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  {param.options?.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          if (param.type === "boolean") {
            return (
              <div key={param.key} className="flex items-center justify-between">
                <label className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">
                  {param.label}
                </label>
                <button
                  onClick={() => onUpdate(block.id, { ...block.params, [param.key]: !value })}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    value ? "bg-[var(--color-primary)]" : "bg-[var(--color-surface-2)]"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                      value ? "translate-x-5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            );
          }

          // Number input
          return (
            <div key={param.key}>
              <label className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide block mb-1">
                {param.label}
                {param.unit && <span className="ml-1 text-[var(--color-text-muted)]">({param.unit})</span>}
              </label>
              <input
                type="number"
                value={Number(value)}
                min={param.min}
                max={param.max}
                step={param.step}
                onChange={(e) => onUpdate(block.id, { ...block.params, [param.key]: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
