import { useState, useEffect, useCallback } from "react";
import {
  BookOpen,
  CheckCircle2,
  Award,
  Clock,
  ChevronRight,
  GraduationCap,
} from "lucide-react";
import {
  TUTORIALS,
  TUTORIAL_CATEGORIES,
  DIFFICULTY_LABELS,
  DIFFICULTY_COLORS,
  getTutorialsByCategory,
  type Tutorial,
  type TutorialCategory,
} from "../data/tutorials";
import { TutorialViewer } from "../components/academy/TutorialViewer";
import { AITutor } from "../components/academy/AITutor";
import { api } from "../lib/api";

// ─── Progress tracking ────────────────────────────────────────────────────────

const PROGRESS_KEY = "academy_progress";

interface ProgressMap {
  [tutorialId: string]: { completed: boolean; percent: number };
}

function loadProgress(): ProgressMap {
  try {
    const saved = localStorage.getItem(PROGRESS_KEY);
    if (saved) return JSON.parse(saved);
  } catch {
    // ignore
  }
  return {};
}

function saveProgress(progress: ProgressMap) {
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress));
  } catch {
    // ignore
  }
}

// ─── Page component ───────────────────────────────────────────────────────────

export function AcademyPage() {
  const [progress, setProgress] = useState<ProgressMap>({});
  const [selectedTutorial, setSelectedTutorial] = useState<Tutorial | null>(null);
  const [activeCategory, setActiveCategory] = useState<TutorialCategory | "All">("All");
  const [showAITutor, setShowAITutor] = useState(false);

  // Load progress from localStorage and sync with backend
  useEffect(() => {
    const localProgress = loadProgress();
    setProgress(localProgress);

    // Try to sync with backend
    api("/api/academy/progress")
      .then((data: any) => {
        if (data && data.progress) {
          const backendProgress: ProgressMap = {};
          for (const item of data.progress) {
            backendProgress[item.tutorial_id] = {
              completed: item.completed,
              percent: item.progress_percent,
            };
          }
          // Merge: backend takes priority
          const merged = { ...localProgress, ...backendProgress };
          setProgress(merged);
          saveProgress(merged);
        }
      })
      .catch(() => {
        // Backend not available, use local progress only
      });
  }, []);

  const updateProgress = useCallback(
    (tutorialId: string, percent: number, completed: boolean) => {
      setProgress((prev) => {
        const next = { ...prev, [tutorialId]: { completed, percent } };
        saveProgress(next);
        return next;
      });

      // Sync with backend
      api(`/api/academy/progress/${tutorialId}`, {
        method: "POST",
        body: JSON.stringify({ progress_percent: percent, completed }),
      }).catch(() => {
        // Backend not available, progress saved locally only
      });
    },
    [],
  );

  const handleComplete = (tutorialId: string) => {
    updateProgress(tutorialId, 100, true);
    setSelectedTutorial(null);
  };

  // ─── Stats ──────────────────────────────────────────────────────────────────
  const completedCount = Object.values(progress).filter((p) => p.completed).length;
  const totalCount = TUTORIALS.length;
  const overallPercent = Math.round((completedCount / totalCount) * 100);
  const allCompleted = completedCount === totalCount;

  // ─── Filter tutorials ───────────────────────────────────────────────────────
  const filteredTutorials =
    activeCategory === "All"
      ? TUTORIALS
      : getTutorialsByCategory(activeCategory as TutorialCategory);

  return (
    <div className="p-5 space-y-4 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="panel p-6 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-surface-2)]">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-[var(--color-primary)]/15">
              <GraduationCap size={24} className="text-[var(--color-primary)]" />
            </div>
            <div>
              <h1 className="text-[20px] font-extrabold text-[var(--color-text)]">Alvora Academy</h1>
              <p className="text-[13px] text-[var(--color-text-muted)]">
                Aprende trading desde lo básico hasta estrategias avanzadas con AI
              </p>
            </div>
          </div>

          {/* Overall progress */}
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-[24px] font-extrabold text-[var(--color-text)]">
                {completedCount}/{totalCount}
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] uppercase font-bold">Tutorials</div>
            </div>
            <div className="w-32">
              <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-[var(--color-primary)] transition-all"
                  style={{ width: `${overallPercent}%` }}
                />
              </div>
              <div className="text-[11px] text-center mt-1 text-[var(--color-text-muted)]">{overallPercent}%</div>
            </div>
          </div>
        </div>

        {/* Certified badge */}
        {allCompleted && (
          <div className="mt-4 flex items-center gap-3 p-3 rounded-xl bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
            <Award size={24} className="text-[var(--color-warning)]" />
            <div>
              <div className="text-[14px] font-bold text-[var(--color-warning)]">
                Alvora Certified Trader
              </div>
              <div className="text-[12px] text-[var(--color-text-muted)]">
                Has completado todos los tutoriales. ¡Felicidades!
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Category filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setActiveCategory("All")}
          className={`px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${
            activeCategory === "All"
              ? "bg-[var(--color-primary)] text-white"
              : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          All
        </button>
        {TUTORIAL_CATEGORIES.map((cat) => {
          const count = getTutorialsByCategory(cat).length;
          const completedInCat = getTutorialsByCategory(cat).filter(
            (t) => progress[t.id]?.completed,
          ).length;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${
                activeCategory === cat
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              {cat} ({completedInCat}/{count})
            </button>
          );
        })}
      </div>

      {/* Main layout: tutorials grid + AI tutor */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        {/* Tutorial cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredTutorials.map((tutorial) => {
            const prog = progress[tutorial.id];
            const isCompleted = prog?.completed;
            const percent = prog?.percent || 0;
            const diffColor = DIFFICULTY_COLORS[tutorial.difficulty];

            return (
              <button
                key={tutorial.id}
                onClick={() => setSelectedTutorial(tutorial)}
                className="panel p-4 text-left card-hover group relative overflow-hidden"
              >
                {/* Completion badge */}
                {isCompleted && (
                  <div className="absolute top-3 right-3">
                    <CheckCircle2 size={18} className="text-[var(--color-success)]" />
                  </div>
                )}

                {/* Category + difficulty */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-semibold">
                    {tutorial.category}
                  </span>
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                    style={{
                      backgroundColor: `color-mix(in srgb, ${diffColor} 15%, transparent)`,
                      color: diffColor,
                    }}
                  >
                    {DIFFICULTY_LABELS[tutorial.difficulty]}
                  </span>
                </div>

                {/* Title */}
                <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-1 pr-6 group-hover:text-[var(--color-primary)] transition-colors">
                  {tutorial.title}
                </h3>

                {/* Description */}
                <p className="text-[12px] text-[var(--color-text-muted)] leading-relaxed mb-3 line-clamp-2">
                  {tutorial.description}
                </p>

                {/* Meta */}
                <div className="flex items-center gap-3 text-[11px] text-[var(--color-text-muted)]">
                  <span className="flex items-center gap-1">
                    <BookOpen size={11} />
                    {tutorial.steps.length} steps
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={11} />
                    {tutorial.estimatedMinutes} min
                  </span>
                </div>

                {/* Progress bar */}
                {percent > 0 && !isCompleted && (
                  <div className="mt-2">
                    <div className="h-1 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--color-primary)]"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-1">{percent}% complete</div>
                  </div>
                )}

                {/* Start/Continue button */}
                <div className="mt-3 flex items-center gap-1 text-[12px] font-bold text-[var(--color-primary)] group-hover:gap-2 transition-all">
                  {isCompleted ? "Review" : percent > 0 ? "Continue" : "Start"}
                  <ChevronRight size={14} />
                </div>
              </button>
            );
          })}
        </div>

        {/* AI Tutor sidebar */}
        <div className="space-y-3">
          <button
            onClick={() => setShowAITutor(!showAITutor)}
            className="w-full flex items-center justify-between p-3 panel hover:bg-[var(--color-surface-2)] transition-colors"
          >
            <div className="flex items-center gap-2">
              <GraduationCap size={16} className="text-[var(--color-primary)]" />
              <span className="text-[13px] font-bold text-[var(--color-text)]">AI Tutor</span>
            </div>
            <ChevronRight
              size={16}
              className={`text-[var(--color-text-muted)] transition-transform ${showAITutor ? "rotate-90" : ""}`}
            />
          </button>
          {showAITutor && (
            <AITutor
              tutorialContext={selectedTutorial?.title}
            />
          )}

          {/* Overall progress card */}
          <div className="panel p-4">
            <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Your Progress</h3>
            <div className="space-y-2">
              {TUTORIAL_CATEGORIES.map((cat) => {
                const catTutorials = getTutorialsByCategory(cat);
                const completed = catTutorials.filter((t) => progress[t.id]?.completed).length;
                const total = catTutorials.length;
                const pct = total > 0 ? (completed / total) * 100 : 0;
                return (
                  <div key={cat}>
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="text-[var(--color-text-muted)] font-medium">{cat}</span>
                      <span className="text-[var(--color-text)] font-bold">{completed}/{total}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--color-primary)] transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Tutorial viewer modal */}
      {selectedTutorial && (
        <TutorialViewer
          tutorial={selectedTutorial}
          onClose={() => setSelectedTutorial(null)}
          onComplete={handleComplete}
          initialStep={
            progress[selectedTutorial.id]?.percent
              ? Math.floor((progress[selectedTutorial.id].percent / 100) * selectedTutorial.steps.length)
              : 0
          }
        />
      )}
    </div>
  );
}
