import { useState } from "react";
import { CheckCircle2, XCircle, ChevronRight, Award } from "lucide-react";
import type { QuizQuestion } from "../../data/tutorials";

interface QuizProps {
  questions: QuizQuestion[];
  onAllAnswered: (correctCount: number, total: number) => void;
  onContinue: () => void;
}

export function Quiz({ questions, onAllAnswered, onContinue }: QuizProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [answered, setAnswered] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [finished, setFinished] = useState(false);

  const question = questions[currentIndex];
  const isCorrect = answered && selectedIndex === question.correctIndex;
  const isLastQuestion = currentIndex === questions.length - 1;

  const handleSelect = (index: number) => {
    if (answered) return;
    setSelectedIndex(index);
    setAnswered(true);
    const correct = index === question.correctIndex;
    if (correct) setCorrectCount((prev) => prev + 1);

    // If last question, notify after answering
    if (isLastQuestion) {
      const total = correct ? correctCount + 1 : correctCount;
      onAllAnswered(total, questions.length);
      setFinished(true);
    }
  };

  const handleNext = () => {
    if (isLastQuestion) return;
    setCurrentIndex((prev) => prev + 1);
    setSelectedIndex(null);
    setAnswered(false);
  };

  // ─── Results screen ──────────────────────────────────────────────────────────
  if (finished) {
    const pct = Math.round((correctCount / questions.length) * 100);
    const perfect = correctCount === questions.length;

    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center animate-fade-in-up">
        <div
          className="flex items-center justify-center w-20 h-20 rounded-full mb-4"
          style={{
            background: perfect
              ? "color-mix(in srgb, var(--color-success) 15%, transparent)"
              : pct >= 60
              ? "color-mix(in srgb, var(--color-primary) 15%, transparent)"
              : "color-mix(in srgb, var(--color-warning) 15%, transparent)",
          }}
        >
          <Award
            size={36}
            className={
              perfect
                ? "text-[var(--color-success)]"
                : pct >= 60
                ? "text-[var(--color-primary)]"
                : "text-[var(--color-warning)]"
            }
          />
        </div>

        <div className="text-[28px] font-extrabold text-[var(--color-text)]">
          {correctCount} / {questions.length}
        </div>
        <div className="text-[13px] text-[var(--color-text-muted)] mt-1">
          {perfect
            ? "¡Perfecto! Todas las respuestas correctas 🎉"
            : pct >= 60
            ? "¡Buen trabajo! Sigue practicando"
            : "Repasa el tutorial e inténtalo de nuevo"}
        </div>

        {/* Score bar */}
        <div className="w-full max-w-xs mt-4">
          <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${pct}%`,
                background: perfect
                  ? "var(--color-success)"
                  : pct >= 60
                  ? "var(--color-primary)"
                  : "var(--color-warning)",
              }}
            />
          </div>
        </div>

        <button
          onClick={onContinue}
          className="mt-6 flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[var(--color-primary)] text-white text-[14px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
        >
          Continuar
          <ChevronRight size={18} />
        </button>
      </div>
    );
  }

  // ─── Question screen ─────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Progress indicator */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">
          Pregunta {currentIndex + 1} de {questions.length}
        </span>
        <div className="flex items-center gap-1">
          {questions.map((_, i) => (
            <div
              key={i}
              className="h-1.5 rounded-full transition-all"
              style={{
                width: i === currentIndex ? "20px" : "8px",
                background:
                  i < currentIndex
                    ? "var(--color-success)"
                    : i === currentIndex
                    ? "var(--color-primary)"
                    : "var(--color-surface-2)",
              }}
            />
          ))}
        </div>
      </div>

      {/* Question */}
      <h4 className="text-[15px] font-bold text-[var(--color-text)] leading-relaxed">
        {question.question}
      </h4>

      {/* Options */}
      <div className="space-y-2">
        {question.options.map((option, i) => {
          const isSelected = selectedIndex === i;
          const isCorrectOption = i === question.correctIndex;

          let bg = "var(--color-surface-2)";
          let border = "1px solid var(--color-border)";
          let textColor = "var(--color-text)";

          if (answered) {
            if (isCorrectOption) {
              bg = "color-mix(in srgb, var(--color-success) 12%, transparent)";
              border = "1px solid var(--color-success)";
              textColor = "var(--color-success)";
            } else if (isSelected && !isCorrectOption) {
              bg = "color-mix(in srgb, var(--color-danger) 12%, transparent)";
              border = "1px solid var(--color-danger)";
              textColor = "var(--color-danger)";
            }
          }

          return (
            <button
              key={i}
              onClick={() => handleSelect(i)}
              disabled={answered}
              className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all"
              style={{
                background: bg,
                border,
                cursor: answered ? "default" : "pointer",
                opacity: answered && !isSelected && !isCorrectOption ? 0.5 : 1,
              }}
            >
              <div
                className="flex items-center justify-center w-6 h-6 rounded-full flex-shrink-0 text-[11px] font-bold"
                style={{
                  background: answered && isCorrectOption
                    ? "var(--color-success)"
                    : answered && isSelected && !isCorrectOption
                    ? "var(--color-danger)"
                    : "var(--color-surface)",
                  color: answered && (isCorrectOption || (isSelected && !isCorrectOption))
                    ? "white"
                    : "var(--color-text-muted)",
                  border: "1px solid var(--color-border)",
                }}
              >
                {answered && isCorrectOption ? (
                  <CheckCircle2 size={14} />
                ) : answered && isSelected && !isCorrectOption ? (
                  <XCircle size={14} />
                ) : (
                  String.fromCharCode(65 + i)
                )}
              </div>
              <span
                className="text-[13px] font-medium flex-1"
                style={{ color: textColor }}
              >
                {option}
              </span>
            </button>
          );
        })}
      </div>

      {/* Explanation */}
      {answered && (
        <div
          className="p-3 rounded-xl text-[12px] leading-relaxed animate-fade-in-up"
          style={{
            background: isCorrect
              ? "color-mix(in srgb, var(--color-success) 8%, transparent)"
              : "color-mix(in srgb, var(--color-danger) 8%, transparent)",
            border: `1px solid ${
              isCorrect ? "var(--color-success)" : "var(--color-danger)"
            }`,
          }}
        >
          <div className="flex items-center gap-2 mb-1">
            {isCorrect ? (
              <CheckCircle2 size={14} className="text-[var(--color-success)]" />
            ) : (
              <XCircle size={14} className="text-[var(--color-danger)]" />
            )}
            <span
              className="font-bold text-[11px] uppercase"
              style={{
                color: isCorrect
                  ? "var(--color-success)"
                  : "var(--color-danger)",
              }}
            >
              {isCorrect ? "¡Correcto!" : "Incorrecto"}
            </span>
          </div>
          <p className="text-[var(--color-text)]">{question.explanation}</p>
        </div>
      )}

      {/* Next button */}
      {answered && !isLastQuestion && (
        <div className="flex justify-end">
          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white text-[13px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            Siguiente Pregunta
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
