import { useState, useEffect, useCallback } from "react";
import {
  BookOpen,
  CheckCircle2,
  Award,
  Clock,
  ChevronRight,
  GraduationCap,
  Lock,
  Route,
  BookA,
  Trophy,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  TUTORIALS,
  TUTORIAL_CATEGORIES,
  LEARNING_PATHS,
  BADGES,
  DIFFICULTY_LABELS,
  DIFFICULTY_COLORS,
  getTutorialsByCategory,
  arePrerequisitesMet,
  getLevelForXp,
  getXpForTutorial,
  type Tutorial,
  type TutorialCategory,
} from "../data/tutorials";
import { TutorialViewer } from "../components/academy/TutorialViewer";
import { AITutor } from "../components/academy/AITutor";
import { XPBar } from "../components/academy/XPBar";
import { StreakCounter } from "../components/academy/StreakCounter";
import { BadgeDisplay } from "../components/academy/BadgeDisplay";
import { LevelUpModal } from "../components/academy/LevelUpModal";
import { BadgeEarnedModal } from "../components/academy/BadgeEarnedModal";
import { LearningPathCard } from "../components/academy/LearningPathCard";
import { GlossaryPanel } from "../components/academy/GlossaryPanel";
import { Confetti } from "../components/academy/Confetti";
import { useGamification } from "../hooks/useGamification";
import { api } from "../lib/api";

type Tab = "paths" | "tutorials" | "glossary" | "badges";

// ─── Progress tracking (separate from gamification for step resume) ──────────

const PROGRESS_KEY = "academy_step_progress";

interface StepProgress {
  [tutorialId: string]: number; // step index
}

function loadStepProgress(): StepProgress {
  try {
    const saved = localStorage.getItem(PROGRESS_KEY);
    if (saved) return JSON.parse(saved);
  } catch {
    // ignore
  }
  return {};
}

function saveStepProgress(progress: StepProgress) {
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress));
  } catch {
    // ignore
  }
}

// ─── Page component ───────────────────────────────────────────────────────────

export function AcademyPage() {
  const { state, actions, leveledUp, newBadgeId, currentLevel } =
    useGamification();

  const [stepProgress, setStepProgress] = useState<StepProgress>({});
  const [selectedTutorial, setSelectedTutorial] = useState<Tutorial | null>(
    null,
  );
  const [activeCategory, setActiveCategory] = useState<
    TutorialCategory | "All"
  >("All");
  const [activeTab, setActiveTab] = useState<Tab>("paths");
  const [showAITutor, setShowAITutor] = useState(false);
  const [showLevelUp, setShowLevelUp] = useState(false);
  const [showBadgeModal, setShowBadgeModal] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);

  // Load step progress
  useEffect(() => {
    setStepProgress(loadStepProgress());
  }, []);

  // Detect level up
  useEffect(() => {
    if (leveledUp) {
      setShowLevelUp(true);
    }
  }, [leveledUp]);

  // Detect new badge
  useEffect(() => {
    if (newBadgeId) {
      setShowBadgeModal(true);
    }
  }, [newBadgeId]);

  // Sync with backend
  useEffect(() => {
    api("/api/academy/progress")
      .then((data: any) => {
        if (data && data.progress) {
          // Backend sync can update step progress if needed
        }
      })
      .catch(() => {
        // Backend not available
      });
  }, []);

  const handleComplete = useCallback(
    (tutorialId: string, allCorrect: boolean) => {
      actions.completeTutorial(tutorialId, allCorrect);

      // Clear step progress for this tutorial
      setStepProgress((prev) => {
        const next = { ...prev };
        delete next[tutorialId];
        saveStepProgress(next);
        return next;
      });

      // Sync with backend
      api(`/api/academy/progress/${tutorialId}`, {
        method: "POST",
        body: JSON.stringify({
          progress_percent: 100,
          completed: true,
          xp_earned: getXpForTutorial(
            TUTORIALS.find((t) => t.id === tutorialId)!,
          ),
          perfect_quiz: allCorrect,
        }),
      }).catch(() => {});

      setShowConfetti(true);
      setSelectedTutorial(null);
    },
    [actions],
  );

  const handleAction = useCallback((_target: string) => {
    // Navigate to the target page — this would use the app's navigation
    // For now, just close the viewer
    setSelectedTutorial(null);
  }, []);

  const handlePathClick = (pathId: string) => {
    const path = LEARNING_PATHS.find((p) => p.id === pathId);
    if (!path) return;
    // Find first incomplete tutorial in the path
    const nextTutorial = path.tutorialIds
      .map((id) => TUTORIALS.find((t) => t.id === id))
      .filter(Boolean)
      .find((t) => !state.completedTutorials.includes(t!.id));
    if (nextTutorial) {
      setSelectedTutorial(nextTutorial);
    } else {
      // All completed, open the first one for review
      const first = TUTORIALS.find((t) => t.id === path.tutorialIds[0]);
      if (first) setSelectedTutorial(first);
    }
  };

  // ─── Stats ──────────────────────────────────────────────────────────────────
  const completedCount = state.completedTutorials.length;
  const totalCount = TUTORIALS.length;
  const overallPercent = Math.round((completedCount / totalCount) * 100);
  const allCompleted = completedCount === totalCount;
  const earnedBadges = actions.getEarnedBadges();
  const newBadge = newBadgeId
    ? BADGES.find((b) => b.id === newBadgeId) || null
    : null;

  // ─── Filter tutorials ───────────────────────────────────────────────────────
  const filteredTutorials =
    activeCategory === "All"
      ? TUTORIALS
      : getTutorialsByCategory(activeCategory as TutorialCategory);

  const tabConfig: { id: Tab; label: string; icon: typeof Route }[] = [
    { id: "paths", label: "Learning Paths", icon: Route },
    { id: "tutorials", label: "Tutoriales", icon: BookOpen },
    { id: "glossary", label: "Glosario", icon: BookA },
    { id: "badges", label: "Badges", icon: Trophy },
  ];

  return (
    <div className="p-5 max-w-[1400px] mx-auto">
      <Confetti
        show={showConfetti}
        onComplete={() => setShowConfetti(false)}
      />
      <LevelUpModal
        level={getLevelForXp(state.xp)}
        show={showLevelUp}
        onClose={() => setShowLevelUp(false)}
      />
      <BadgeEarnedModal
        badge={newBadge}
        show={showBadgeModal}
        onClose={() => setShowBadgeModal(false)}
      />

      {/* Header */}
      <div className="panel p-6 mb-4 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-surface-2)]">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-[var(--color-primary)]/15">
              <GraduationCap
                size={24}
                className="text-[var(--color-primary)]"
              />
            </div>
            <div>
              <h1 className="text-[20px] font-extrabold text-[var(--color-text)]">
                Alvora Academy
              </h1>
              <p className="text-[13px] text-[var(--color-text-muted)]">
                Aprende trading desde lo básico hasta estrategias avanzadas
              </p>
            </div>
          </div>

          {/* Overall progress */}
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-[24px] font-extrabold text-[var(--color-text)]">
                {completedCount}/{totalCount}
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] uppercase font-bold">
                Tutoriales
              </div>
            </div>
            <div className="w-32">
              <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-accent)] transition-all"
                  style={{ width: `${overallPercent}%` }}
                />
              </div>
              <div className="text-[11px] text-center mt-1 text-[var(--color-text-muted)]">
                {overallPercent}%
              </div>
            </div>
          </div>
        </div>

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

      {/* Main 2-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* ─── Main content ─── */}
        <div className="space-y-4 min-w-0">
          {/* Tabs */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-[var(--color-surface-2)]">
            {tabConfig.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-all flex-1 justify-center"
                  style={{
                    background: isActive
                      ? "var(--color-surface)"
                      : "transparent",
                    color: isActive
                      ? "var(--color-primary)"
                      : "var(--color-text-muted)",
                    boxShadow: isActive
                      ? "0 1px 3px rgba(0,0,0,0.1)"
                      : "none",
                  }}
                >
                  <Icon size={14} />
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* ─── Learning Paths tab ─── */}
          {activeTab === "paths" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {LEARNING_PATHS.map((path) => (
                <LearningPathCard
                  key={path.id}
                  path={path}
                  completedTutorials={state.completedTutorials}
                  onClick={() => handlePathClick(path.id)}
                />
              ))}
            </div>
          )}

          {/* ─── Tutorials tab ─── */}
          {activeTab === "tutorials" && (
            <>
              {/* Category filter */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => setActiveCategory("All")}
                  className="px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors"
                  style={{
                    background:
                      activeCategory === "All"
                        ? "var(--color-primary)"
                        : "var(--color-surface)",
                    color:
                      activeCategory === "All"
                        ? "white"
                        : "var(--color-text-muted)",
                    border:
                      activeCategory === "All"
                        ? "1px solid var(--color-primary)"
                        : "1px solid var(--color-border)",
                  }}
                >
                  Todos ({TUTORIALS.length})
                </button>
                {TUTORIAL_CATEGORIES.map((cat) => {
                  const count = getTutorialsByCategory(cat).length;
                  const completedInCat = getTutorialsByCategory(cat).filter(
                    (t) => state.completedTutorials.includes(t.id),
                  ).length;
                  const isActive = activeCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setActiveCategory(cat)}
                      className="px-3 py-1.5 rounded-lg text-[12px] font-bold transition-colors"
                      style={{
                        background: isActive
                          ? "var(--color-primary)"
                          : "var(--color-surface)",
                        color: isActive
                          ? "white"
                          : "var(--color-text-muted)",
                        border: isActive
                          ? "1px solid var(--color-primary)"
                          : "1px solid var(--color-border)",
                      }}
                    >
                      {cat} ({completedInCat}/{count})
                    </button>
                  );
                })}
              </div>

              {/* Tutorial cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredTutorials.map((tutorial) => {
                  const isCompleted = state.completedTutorials.includes(
                    tutorial.id,
                  );
                  const stepIdx = stepProgress[tutorial.id] || 0;
                  const percent =
                    isCompleted
                      ? 100
                      : Math.round((stepIdx / tutorial.steps.length) * 100);
                  const diffColor = DIFFICULTY_COLORS[tutorial.difficulty];
                  const prereqsMet = arePrerequisitesMet(
                    tutorial.id,
                    state.completedTutorials,
                  );
                  const isLocked = !prereqsMet && !isCompleted;

                  return (
                    <button
                      key={tutorial.id}
                      onClick={() =>
                        !isLocked && setSelectedTutorial(tutorial)
                      }
                      disabled={isLocked}
                      className="panel p-4 text-left card-hover group relative overflow-hidden transition-all"
                      style={{
                        opacity: isLocked ? 0.6 : 1,
                        cursor: isLocked ? "not-allowed" : "pointer",
                      }}
                    >
                      {/* Completion / Lock badge */}
                      <div className="absolute top-3 right-3">
                        {isCompleted ? (
                          <CheckCircle2
                            size={18}
                            className="text-[var(--color-success)]"
                          />
                        ) : isLocked ? (
                          <Lock
                            size={16}
                            className="text-[var(--color-text-muted)]"
                          />
                        ) : null}
                      </div>

                      {/* Category + difficulty + XP */}
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
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
                        <span className="flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full font-bold text-[var(--color-primary)] bg-[var(--color-primary)]/10">
                          <Zap size={9} />
                          {tutorial.xpReward} XP
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

                      {/* Lock reason */}
                      {isLocked && (
                        <div className="text-[10px] text-[var(--color-warning)] mb-2 flex items-center gap-1">
                          <Lock size={10} />
                          Completa los prerrequisitos para desbloquear
                        </div>
                      )}

                      {/* Meta */}
                      <div className="flex items-center gap-3 text-[11px] text-[var(--color-text-muted)]">
                        <span className="flex items-center gap-1">
                          <BookOpen size={11} />
                          {tutorial.steps.length} pasos
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
                          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                            {percent}% completado
                          </div>
                        </div>
                      )}

                      {/* Start/Continue button */}
                      {!isLocked && (
                        <div className="mt-3 flex items-center gap-1 text-[12px] font-bold text-[var(--color-primary)] group-hover:gap-2 transition-all">
                          {isCompleted
                            ? "Repasar"
                            : percent > 0
                            ? "Continuar"
                            : "Empezar"}
                          <ChevronRight size={14} />
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {/* ─── Glossary tab ─── */}
          {activeTab === "glossary" && (
            <div className="panel p-4">
              <GlossaryPanel />
            </div>
          )}

          {/* ─── Badges tab ─── */}
          {activeTab === "badges" && (
            <div className="panel p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[14px] font-bold text-[var(--color-text)]">
                  Insignias ({earnedBadges.length}/{BADGES.length})
                </h3>
                <span className="text-[12px] text-[var(--color-text-muted)]">
                  {Math.round((earnedBadges.length / BADGES.length) * 100)}%
                  desbloqueado
                </span>
              </div>
              <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden mb-4">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-accent)] transition-all"
                  style={{
                    width: `${(earnedBadges.length / BADGES.length) * 100}%`,
                  }}
                />
              </div>
              <BadgeDisplay
                badges={BADGES}
                earnedBadgeIds={state.earnedBadges}
                newlyEarned={newBadgeId}
              />
            </div>
          )}
        </div>

        {/* ─── Right sidebar ─── */}
        <div className="space-y-3">
          {/* XP Bar */}
          <div className="panel p-4">
            <XPBar xp={state.xp} />
          </div>

          {/* Streak Counter */}
          <div className="panel p-4">
            <StreakCounter streak={state.streak} />
          </div>

          {/* Quick stats */}
          <div className="panel p-4 space-y-2">
            <h3 className="text-[12px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide mb-2">
              Estadísticas
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 rounded-lg bg-[var(--color-surface-2)] text-center">
                <div className="text-[18px] font-extrabold text-[var(--color-text)]">
                  {completedCount}
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)] uppercase font-bold">
                  Completados
                </div>
              </div>
              <div className="p-2 rounded-lg bg-[var(--color-surface-2)] text-center">
                <div className="text-[18px] font-extrabold text-[var(--color-text)]">
                  {state.perfectQuizzes.length}
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)] uppercase font-bold">
                  Quizzes Perfectos
                </div>
              </div>
              <div className="p-2 rounded-lg bg-[var(--color-surface-2)] text-center">
                <div className="text-[18px] font-extrabold text-[var(--color-text)]">
                  {earnedBadges.length}
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)] uppercase font-bold">
                  Badges
                </div>
              </div>
              <div className="p-2 rounded-lg bg-[var(--color-surface-2)] text-center">
                <div className="text-[18px] font-extrabold text-[var(--color-text)]">
                  {currentLevel}
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)] uppercase font-bold">
                  Nivel
                </div>
              </div>
            </div>
          </div>

          {/* AI Tutor */}
          <div className="panel p-3">
            <button
              onClick={() => setShowAITutor(!showAITutor)}
              className="w-full flex items-center justify-between p-1 rounded-lg hover:bg-[var(--color-surface-2)] transition-colors"
            >
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-[var(--color-primary)]" />
                <span className="text-[13px] font-bold text-[var(--color-text)]">
                  AI Tutor
                </span>
              </div>
              <ChevronRight
                size={16}
                className={`text-[var(--color-text-muted)] transition-transform ${
                  showAITutor ? "rotate-90" : ""
                }`}
              />
            </button>
            {showAITutor && (
              <div className="mt-3">
                <AITutor tutorialContext={selectedTutorial?.title} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tutorial viewer modal */}
      {selectedTutorial && (
        <TutorialViewer
          tutorial={selectedTutorial}
          onClose={() => setSelectedTutorial(null)}
          onComplete={handleComplete}
          onAction={handleAction}
          initialStep={stepProgress[selectedTutorial.id] || 0}
        />
      )}
    </div>
  );
}
