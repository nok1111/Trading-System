import { useState, useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  X,
  Sparkles,
  ExternalLink,
  Play,
} from "lucide-react";
import type { Tutorial } from "../../data/tutorials";
import { getQuizForTutorial } from "../../data/tutorials";
import { Quiz } from "./Quiz";
import { Confetti } from "./Confetti";
import { AcademyWidget } from "./AcademyWidget";

interface TutorialViewerProps {
  tutorial: Tutorial;
  onClose: () => void;
  onComplete: (tutorialId: string, allCorrect: boolean) => void;
  onAction?: (target: string) => void;
  initialStep?: number;
}

export function TutorialViewer({
  tutorial,
  onClose,
  onComplete,
  onAction,
  initialStep = 0,
}: TutorialViewerProps) {
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [showQuiz, setShowQuiz] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const [quizResults, setQuizResults] = useState<{
    correct: number;
    total: number;
  } | null>(null);

  const step = tutorial.steps[currentStep];
  const isLastStep = currentStep === tutorial.steps.length - 1;
  const quizQuestions = getQuizForTutorial(tutorial.id);

  const handleNext = useCallback(() => {
    if (isLastStep) {
      // If there's a quiz, show it. Otherwise complete immediately.
      if (quizQuestions && quizQuestions.length > 0 && !showQuiz) {
        setShowQuiz(true);
        return;
      }
      // Complete the tutorial
      const allCorrect =
        quizResults != null && quizResults.correct === quizResults.total;
      onComplete(tutorial.id, allCorrect);
      setShowConfetti(true);
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  }, [
    isLastStep,
    quizQuestions,
    showQuiz,
    quizResults,
    onComplete,
    tutorial.id,
  ]);

  const handlePrev = () => {
    if (showQuiz) {
      setShowQuiz(false);
      return;
    }
    if (currentStep > 0) setCurrentStep((prev) => prev - 1);
  };

  const handleQuizAllAnswered = (correct: number, total: number) => {
    setQuizResults({ correct, total });
  };

  const handleQuizContinue = () => {
    const allCorrect =
      quizResults != null && quizResults.correct === quizResults.total;
    onComplete(tutorial.id, allCorrect);
    setShowConfetti(true);
  };

  return (
    <>
      <Confetti show={showConfetti} onComplete={() => setShowConfetti(false)} />
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in-up">
        <div className="panel w-full max-w-4xl max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
            <div className="min-w-0 flex-1">
              <h2 className="text-[16px] font-extrabold text-[var(--color-text)] truncate">
                {tutorial.title}
              </h2>
              <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                {showQuiz
                  ? "Quiz Final"
                  : `Step ${currentStep + 1} de ${tutorial.steps.length} · ${tutorial.estimatedMinutes} min · +${tutorial.xpReward} XP`}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-2 rounded hover:bg-[var(--color-surface-2)] transition-colors flex-shrink-0"
            >
              <X size={18} />
            </button>
          </div>

          {/* Progress bar */}
          <div className="h-1 bg-[var(--color-surface-2)] flex-shrink-0">
            <div
              className="h-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-accent)] transition-all duration-300"
              style={{
                width: showQuiz
                  ? "100%"
                  : `${((currentStep + 1) / tutorial.steps.length) * 100}%`,
              }}
            />
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-y-auto p-6">
            {showQuiz && quizQuestions ? (
              <div className="max-w-xl mx-auto">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles
                    size={18}
                    className="text-[var(--color-primary)]"
                  />
                  <h3 className="text-[16px] font-bold text-[var(--color-text)]">
                    ¡Demuestra lo que aprendiste!
                  </h3>
                </div>
                <Quiz
                  questions={quizQuestions}
                  onAllAnswered={handleQuizAllAnswered}
                  onContinue={handleQuizContinue}
                />
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
                {/* Step content */}
                <div className="min-w-0">
                  <h3 className="text-[18px] font-bold text-[var(--color-text)] mb-3">
                    {step.title}
                  </h3>
                  <p className="text-[14px] text-[var(--color-text)] leading-relaxed mb-4">
                    {step.content}
                  </p>

                  {/* Interactive widget — simulates real Alvora UI */}
                  {step.widget && (
                    <div className="mt-4">
                      <div className="flex items-center gap-1.5 text-[11px] font-bold text-[var(--color-primary)] mb-2">
                        <Play size={12} />
                        PRUÉBALO — Simulación interactiva
                      </div>
                      <AcademyWidget type={step.widget} />
                    </div>
                  )}

                  {/* Action button */}
                  {step.actionLabel && step.actionTarget && onAction && (
                    <button
                      onClick={() => onAction(step.actionTarget!)}
                      className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-[13px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
                    >
                      {step.actionLabel}
                      <ExternalLink size={14} />
                    </button>
                  )}
                </div>

                {/* XP reward sidebar */}
                <div className="lg:w-48 flex-shrink-0">
                  <div
                    className="p-4 rounded-xl text-center sticky top-0"
                    style={{
                      background:
                        "color-mix(in srgb, var(--color-primary) 8%, var(--color-surface))",
                      border:
                        "1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)",
                    }}
                  >
                    <div className="text-[24px] mb-1">🎯</div>
                    <div className="text-[20px] font-extrabold text-[var(--color-primary)]">
                      +{tutorial.xpReward}
                    </div>
                    <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">
                      XP al completar
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Navigation */}
          {!showQuiz && (
            <div className="flex items-center justify-between p-4 border-t border-[var(--color-border)]">
              <button
                onClick={handlePrev}
                disabled={currentStep === 0 && !showQuiz}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={16} />
                Anterior
              </button>

              {/* Step dots */}
              <div className="flex items-center gap-1.5">
                {tutorial.steps.map((_, i) => (
                  <div
                    key={i}
                    className="h-2 rounded-full transition-all"
                    style={{
                      width: i === currentStep ? "24px" : "8px",
                      background:
                        i < currentStep
                          ? "var(--color-success)"
                          : i === currentStep
                          ? "var(--color-primary)"
                          : "var(--color-surface-2)",
                    }}
                  />
                ))}
                {quizQuestions && (
                  <div
                    className="h-2 w-2 rounded-full transition-all"
                    style={{
                      background: showQuiz
                        ? "var(--color-primary)"
                        : "var(--color-surface-2)",
                    }}
                    title="Quiz"
                  />
                )}
              </div>

              <button
                onClick={handleNext}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-[13px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
              >
                {isLastStep && quizQuestions
                  ? "Empezar Quiz"
                  : isLastStep
                  ? "Completar"
                  : "Siguiente"}
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
