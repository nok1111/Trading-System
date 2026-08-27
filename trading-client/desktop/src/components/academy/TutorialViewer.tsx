import { useState } from "react";
import { ChevronLeft, ChevronRight, CheckCircle2, X, Code2 } from "lucide-react";
import type { Tutorial } from "../../data/tutorials";

interface TutorialViewerProps {
  tutorial: Tutorial;
  onClose: () => void;
  onComplete: (tutorialId: string) => void;
  initialStep?: number;
}

export function TutorialViewer({ tutorial, onClose, onComplete, initialStep = 0 }: TutorialViewerProps) {
  const [currentStep, setCurrentStep] = useState(initialStep);
  const [showCode, setShowCode] = useState(true);

  const step = tutorial.steps[currentStep];
  const isLastStep = currentStep === tutorial.steps.length - 1;
  const progress = ((currentStep + 1) / tutorial.steps.length) * 100;

  const handleNext = () => {
    if (isLastStep) {
      onComplete(tutorial.id);
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) setCurrentStep((prev) => prev - 1);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="panel w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
          <div className="min-w-0 flex-1">
            <h2 className="text-[16px] font-extrabold text-[var(--color-text)] truncate">{tutorial.title}</h2>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
              Step {currentStep + 1} of {tutorial.steps.length} - {tutorial.estimatedMinutes} min
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
            className="h-full bg-[var(--color-primary)] transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <h3 className="text-[18px] font-bold text-[var(--color-text)] mb-3">{step.title}</h3>
          <p className="text-[14px] text-[var(--color-text)] leading-relaxed mb-4">{step.content}</p>

          {step.codeExample && (
            <div className="mt-4">
              <button
                onClick={() => setShowCode(!showCode)}
                className="flex items-center gap-1.5 text-[12px] font-bold text-[var(--color-primary)] mb-2"
              >
                <Code2 size={14} />
                {showCode ? "Hide code example" : "Show code example"}
              </button>
              {showCode && (
                <pre className="bg-[var(--color-surface-2)] rounded-lg p-4 overflow-x-auto border border-[var(--color-border)]">
                  <code className="text-[12px] text-[var(--color-success)] font-mono whitespace-pre">
                    {step.codeExample}
                  </code>
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between p-4 border-t border-[var(--color-border)]">
          <button
            onClick={handlePrev}
            disabled={currentStep === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={16} />
            Previous
          </button>

          {/* Step dots */}
          <div className="flex items-center gap-1.5">
            {tutorial.steps.map((_, i) => (
              <div
                key={i}
                className={`h-2 rounded-full transition-all ${
                  i === currentStep
                    ? "w-6 bg-[var(--color-primary)]"
                    : i < currentStep
                    ? "w-2 bg-[var(--color-success)]"
                    : "w-2 bg-[var(--color-surface-2)]"
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-[13px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            {isLastStep ? (
              <>
                <CheckCircle2 size={16} />
                Complete
              </>
            ) : (
              <>
                Next
                <ChevronRight size={16} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
