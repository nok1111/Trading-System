import { useEffect, useMemo } from "react";

interface ConfettiProps {
  show: boolean;
  onComplete?: () => void;
}

const CONFETTI_COLORS = [
  "var(--color-primary)",
  "var(--color-success)",
  "var(--color-warning)",
  "var(--color-danger)",
];

const PIECE_COUNT = 50;

interface ConfettiPiece {
  left: number;
  delay: number;
  duration: number;
  rotation: number;
  color: string;
  size: number;
  drift: number;
}

export function Confetti({ show, onComplete }: ConfettiProps) {
  // Generate random pieces once per show
  const pieces = useMemo<ConfettiPiece[]>(() => {
    return Array.from({ length: PIECE_COUNT }, () => ({
      left: Math.random() * 100,
      delay: Math.random() * 0.5,
      duration: 2 + Math.random() * 1.5,
      rotation: Math.random() * 360,
      color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
      size: 6 + Math.random() * 8,
      drift: (Math.random() - 0.5) * 200,
    }));
  }, [show]);

  useEffect(() => {
    if (!show) return;
    const timer = setTimeout(() => {
      onComplete?.();
    }, 3000);
    return () => clearTimeout(timer);
  }, [show, onComplete]);

  if (!show) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 9999,
        overflow: "hidden",
      }}
    >
      <style>{`
        @keyframes confetti-fall {
          0% {
            transform: translateY(-10vh) translateX(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(110vh) translateX(var(--drift)) rotate(720deg);
            opacity: 0;
          }
        }
      `}</style>
      {pieces.map((piece, i) => (
        <div
          key={`${show}-${i}`}
          style={{
            position: "absolute",
            left: `${piece.left}%`,
            top: "-10vh",
            width: `${piece.size}px`,
            height: `${piece.size}px`,
            backgroundColor: piece.color,
            borderRadius: "2px",
            transform: `rotate(${piece.rotation}deg)`,
            animation: `confetti-fall ${piece.duration}s linear ${piece.delay}s forwards`,
            ["--drift" as string]: `${piece.drift}px`,
          }}
        />
      ))}
    </div>
  );
}
