import { X, GripVertical } from "lucide-react";
import type { ReactNode } from "react";

interface WidgetWrapperProps {
  title: string;
  icon?: ReactNode;
  onRemove: () => void;
  onDragStart: (e: React.DragEvent) => void;
  onDragEnd: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  isDragging?: boolean;
  isDragOver?: boolean;
  editMode: boolean;
  children: ReactNode;
}

export function WidgetWrapper({
  title,
  icon,
  onRemove,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  isDragging,
  isDragOver,
  editMode,
  children,
}: WidgetWrapperProps) {
  return (
    <div
      className={`panel card-hover transition-all ${
        isDragging ? "opacity-50 ring-2 ring-[var(--color-primary)]" : ""
      } ${isDragOver ? "ring-2 ring-[var(--color-primary)] ring-offset-2" : ""}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {/* Drag handle / header bar */}
      <div
        draggable={editMode}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        className={`flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-border)] ${
          editMode ? "cursor-grab active:cursor-grabbing" : "cursor-default"
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          {editMode && <GripVertical size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />}
          {icon && <span className="flex-shrink-0 text-[var(--color-primary)]">{icon}</span>}
          <h3 className="text-[13px] font-bold text-[var(--color-text)] truncate">{title}</h3>
        </div>
        {editMode && (
          <button
            onClick={onRemove}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)] p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors flex-shrink-0"
            title="Remove widget"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {/* Widget content */}
      <div className="p-4">{children}</div>
    </div>
  );
}
