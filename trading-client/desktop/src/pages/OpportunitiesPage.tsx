import { AISuggestionsPanel } from "../components/intelligence/AISuggestionsPanel";

export function OpportunitiesPage() {
  return (
    <div className="p-5 max-w-[900px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Oportunidades de Trading</h2>
      <AISuggestionsPanel />
    </div>
  );
}
