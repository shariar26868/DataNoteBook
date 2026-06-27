"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import toast, { type Toast } from "react-hot-toast";

export type ToastType =
  | "success"
  | "error"
  | "warning"
  | "info"
  | "loading";

export interface GSAPToastProps {
  t: Toast;
  title: string;
  message: string;
  type: ToastType;
}

const styles: Record<ToastType, string> = {
  success: "border-green-500/40",
  error: "border-red-500/40",
  warning: "border-yellow-500/40",
  info: "border-blue-500/40",
  loading: "border-purple-500/40",
};

const icons: Record<ToastType, string> = {
  success: "✅",
  error: "❌",
  warning: "⚠️",
  info: "ℹ️",
  loading: "⏳",
};

export default function GSAPToast({
  t,
  title,
  message,
  type,
}: GSAPToastProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Enter animation
    if (t.visible) {
      gsap.fromTo(
        el,
        { y: -30, opacity: 0, scale: 0.95 },
        {
          y: 0,
          opacity: 1,
          scale: 1,
          duration: 0.35,
          ease: "power3.out",
        }
      );
    } else {
      // Exit animation
      gsap.to(el, {
        y: -20,
        opacity: 0,
        scale: 0.95,
        duration: 0.25,
        ease: "power3.in",
      });
    }
  }, [t.visible]);

  return (
    <div
      ref={ref}
      role="alert"
      aria-live={type === "error" ? "assertive" : "polite"}
      className={`pointer-events-auto flex w-full max-w-sm gap-3 rounded-lg border bg-[#1f2128]
      px-4 py-3 text-white shadow-lg ${styles[type]}`}
    >
      {/* Icon */}
      <span className="shrink-0 text-lg">{icons[type]}</span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold truncate">{title}</p>
        <p className="mt-0.5 text-xs opacity-90 line-clamp-2">
          {message}
        </p>
      </div>

      {/* Close button (not for loading) */}
      {type !== "loading" && (
        <button
          type="button"
          onClick={() => toast.dismiss(t.id)}
          className="ml-2 shrink-0 text-xs opacity-60 hover:opacity-100"
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      )}
    </div>
  );
}
