// ─── Gamification state management with localStorage persistence ──────────────
// Tracks: XP, level, streak, badges earned, tutorials completed, quiz scores

import { useState, useCallback, useEffect, useRef } from "react";
import {
  BADGES,
  TUTORIALS,
  getLevelForXp,
  getNextLevel,
  getXpForTutorial,
  type Badge,
} from "../data/tutorials";

const STORAGE_KEY = "academy_gamification";

export interface GamificationState {
  xp: number;
  streak: number;
  lastStudyDate: string; // ISO date (YYYY-MM-DD)
  completedTutorials: string[];
  perfectQuizzes: string[]; // tutorial IDs where all answers were correct
  earnedBadges: string[];
  quizScores: Record<string, number[]>; // tutorialId -> array of correct(1)/incorrect(0) per step
}

export interface LevelInfo {
  level: number;
  title: string;
  icon: string;
  xpToNext: number;
  progressPct: number;
}

export interface GamificationActions {
  addXp: (amount: number) => void;
  recordQuizAnswer: (tutorialId: string, stepIndex: number, correct: boolean) => void;
  completeTutorial: (tutorialId: string, allCorrect: boolean) => void;
  checkStreak: () => void;
  getLevel: () => LevelInfo;
  getEarnedBadges: () => Badge[];
  reset: () => void;
}

const DEFAULT_STATE: GamificationState = {
  xp: 0,
  streak: 0,
  lastStudyDate: "",
  completedTutorials: [],
  perfectQuizzes: [],
  earnedBadges: [],
  quizScores: {},
};

// ─── Date helpers ─────────────────────────────────────────────────────────────

function todayISO(): string {
  return new Date().toISOString().split("T")[0];
}

function yesterdayISO(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().split("T")[0];
}

function daysBetween(dateStr1: string, dateStr2: string): number {
  const d1 = new Date(dateStr1 + "T00:00:00Z");
  const d2 = new Date(dateStr2 + "T00:00:00Z");
  return Math.round((d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24));
}

// ─── Load / save ──────────────────────────────────────────────────────────────

function loadState(): GamificationState {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return { ...DEFAULT_STATE, ...parsed };
    }
  } catch {
    // ignore
  }
  return { ...DEFAULT_STATE };
}

function saveState(state: GamificationState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

// ─── Badge checking ───────────────────────────────────────────────────────────

function checkBadges(state: GamificationState): string[] {
  const earned = new Set(state.earnedBadges);
  for (const badge of BADGES) {
    if (!earned.has(badge.id) && badge.condition(state)) {
      earned.add(badge.id);
    }
  }
  return Array.from(earned);
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useGamification() {
  const [state, setState] = useState<GamificationState>(loadState);
  const prevLevelRef = useRef<number>(getLevelForXp(state.xp).level);

  // Persist to localStorage whenever state changes
  useEffect(() => {
    saveState(state);
  }, [state]);

  // Check streak on mount
  useEffect(() => {
    checkStreak();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addXp = useCallback((amount: number) => {
    setState((prev) => {
      const newXp = prev.xp + amount;
      const newState = { ...prev, xp: newXp };
      // Check badges after XP change
      newState.earnedBadges = checkBadges(newState);
      return newState;
    });
  }, []);

  const recordQuizAnswer = useCallback(
    (tutorialId: string, stepIndex: number, correct: boolean) => {
      setState((prev) => {
        const existing = prev.quizScores[tutorialId] || [];
        const updated = [...existing];
        // Ensure array is long enough
        while (updated.length <= stepIndex) updated.push(0);
        updated[stepIndex] = correct ? 1 : 0;

        const newState = {
          ...prev,
          quizScores: { ...prev.quizScores, [tutorialId]: updated },
        };
        newState.earnedBadges = checkBadges(newState);
        return newState;
      });
    },
    [],
  );

  const completeTutorial = useCallback(
    (tutorialId: string, allCorrect: boolean) => {
      setState((prev) => {
        const today = todayISO();
        const wasAlreadyCompleted = prev.completedTutorials.includes(tutorialId);

        // Update streak
        let newStreak = prev.streak;
        let newLastStudyDate = prev.lastStudyDate;

        if (prev.lastStudyDate === today) {
          // Already studied today, streak unchanged
        } else if (prev.lastStudyDate === yesterdayISO()) {
          newStreak = prev.streak + 1;
          newLastStudyDate = today;
        } else {
          // Streak was broken or first time
          newStreak = 1;
          newLastStudyDate = today;
        }

        // Add XP only if not already completed
        const newXp = wasAlreadyCompleted ? prev.xp : prev.xp + getTutorialXp(tutorialId);

        const newCompleted = wasAlreadyCompleted
          ? prev.completedTutorials
          : [...prev.completedTutorials, tutorialId];

        const newPerfectQuizzes = allCorrect && !prev.perfectQuizzes.includes(tutorialId)
          ? [...prev.perfectQuizzes, tutorialId]
          : prev.perfectQuizzes;

        const newState: GamificationState = {
          ...prev,
          xp: newXp,
          streak: newStreak,
          lastStudyDate: newLastStudyDate,
          completedTutorials: newCompleted,
          perfectQuizzes: newPerfectQuizzes,
        };

        // Check badges
        newState.earnedBadges = checkBadges(newState);

        return newState;
      });
    },
    [],
  );

  const checkStreak = useCallback(() => {
    setState((prev) => {
      const today = todayISO();
      if (!prev.lastStudyDate) return prev; // Never studied, no streak to check

      if (prev.lastStudyDate === today) {
        // Studied today, streak is current
        return prev;
      }

      const gap = daysBetween(prev.lastStudyDate, today);
      if (gap > 1) {
        // Streak broken — more than 1 day since last study
        return { ...prev, streak: 0 };
      }

      // gap === 1 means yesterday — streak continues but hasn't been incremented yet today
      // Don't increment here; that happens when completing a tutorial
      return prev;
    });
  }, []);

  const getLevel = useCallback((): LevelInfo => {
    const current = getLevelForXp(state.xp);
    const next = getNextLevel(current.level);
    if (!next) {
      return {
        level: current.level,
        title: current.title,
        icon: current.icon,
        xpToNext: 0,
        progressPct: 100,
      };
    }
    const xpInLevel = state.xp - current.minXp;
    const xpForLevel = next.minXp - current.minXp;
    const xpToNext = next.minXp - state.xp;
    const progressPct = Math.min(100, Math.round((xpInLevel / xpForLevel) * 100));
    return {
      level: current.level,
      title: current.title,
      icon: current.icon,
      xpToNext,
      progressPct,
    };
  }, [state.xp]);

  const getEarnedBadges = useCallback((): Badge[] => {
    return BADGES.filter((b) => state.earnedBadges.includes(b.id));
  }, [state.earnedBadges]);

  const reset = useCallback(() => {
    setState({ ...DEFAULT_STATE });
    prevLevelRef.current = 1;
  }, []);

  // Detect level up
  const currentLevel = getLevelForXp(state.xp).level;
  const leveledUp = currentLevel > prevLevelRef.current;
  useEffect(() => {
    if (leveledUp) {
      prevLevelRef.current = currentLevel;
    }
  }, [leveledUp, currentLevel]);

  // Detect newly earned badges (last badge in earnedBadges that wasn't there before)
  const newBadgeRef = useRef<string | null>(null);
  const prevBadgeCountRef = useRef(state.earnedBadges.length);
  const newBadgeId =
    state.earnedBadges.length > prevBadgeCountRef.current
      ? state.earnedBadges[state.earnedBadges.length - 1]
      : null;

  useEffect(() => {
    prevBadgeCountRef.current = state.earnedBadges.length;
    if (newBadgeId) {
      newBadgeRef.current = newBadgeId;
    }
  }, [state.earnedBadges.length, newBadgeId]);

  const actions: GamificationActions = {
    addXp,
    recordQuizAnswer,
    completeTutorial,
    checkStreak,
    getLevel,
    getEarnedBadges,
    reset,
  };

  return {
    state,
    actions,
    leveledUp,
    newBadgeId,
    currentLevel,
  };
}

// ─── Helper: get XP for a tutorial ────────────────────────────────────────────

function getTutorialXp(tutorialId: string): number {
  const tutorial = TUTORIALS.find((t) => t.id === tutorialId);
  if (!tutorial) return 25;
  return getXpForTutorial(tutorial);
}
