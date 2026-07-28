import { AISuggestionsPanel } from "../components/intelligence/AISuggestionsPanel";

export function OpportunitiesPage() {
  return (
    <div className="p-5 max-w-[900px] mx-auto space-y-4">
      <div>
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Oportunidades de Trading</h2>
        <p className="text-[12px] text-[var(--color-text-muted)] mt-1">
          Señales activas rankeadas por confianza, alineadas con tu perfil de riesgo y horizonte temporal.
        </p>
      </div>
      <AISuggestionsPanel />
    </div>
  );
}
