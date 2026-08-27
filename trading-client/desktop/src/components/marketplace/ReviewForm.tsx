import { useState } from "react";
import { Star, X } from "lucide-react";
import { reviewStrategy } from "../../lib/marketplaceApi";
import { cn } from "../../lib/utils";

interface ReviewFormProps {
  listingId: number;
  onSubmitted?: () => void;
  onCancel?: () => void;
}

export function ReviewForm({ listingId, onSubmitted, onCancel }: ReviewFormProps) {
  const [rating, setRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    if (rating < 1 || rating > 5) {
      setError("Rating must be between 1 and 5");
      return;
    }
    setSubmitting(true);
    try {
      await reviewStrategy(listingId, rating, comment.trim());
      onSubmitted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  const displayRating = hoverRating || rating;

  return (
    <div className="rounded-[8px] border border-[var(--color-surface-2)] p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-[12px] font-bold text-[var(--color-text)]">Write a Review</h4>
        {onCancel && (
          <button
            onClick={onCancel}
            className="p-1 rounded-[4px] hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-[4px] bg-red-500/10 border border-red-500/30 p-2">
          <p className="text-[11px] text-red-400">{error}</p>
        </div>
      )}

      {/* Star rating */}
      <div>
        <label className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
          Rating
        </label>
        <div className="flex items-center gap-1">
          {Array.from({ length: 5 }).map((_, i) => {
            const value = i + 1;
            return (
              <button
                key={i}
                onClick={() => setRating(value)}
                onMouseEnter={() => setHoverRating(value)}
                onMouseLeave={() => setHoverRating(0)}
                className="p-0.5 transition-transform hover:scale-110"
              >
                <Star
                  size={20}
                  className={cn(
                    "transition-colors",
                    value <= displayRating
                      ? "text-amber-400 fill-amber-400"
                      : "text-[var(--color-text-muted)]"
                  )}
                />
              </button>
            );
          })}
          <span className="text-[12px] font-bold text-[var(--color-text)] ml-2">
            {displayRating}/5
          </span>
        </div>
      </div>

      {/* Comment */}
      <div>
        <label className="text-[10px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
          Comment (optional)
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder="Share your experience with this strategy..."
          className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] border border-transparent focus:border-[var(--color-primary)] outline-none resize-none"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-4 py-2 rounded-[6px] bg-[var(--color-primary)] text-white text-[12px] font-bold hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Submitting..." : "Submit Review"}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] font-bold hover:bg-[var(--color-surface-3)]"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
