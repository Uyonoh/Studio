"use client";

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) =>
      element.getAttribute("aria-hidden") !== "true" &&
      // offsetParent is null for display:none elements; fixed-position elements
      // can also report null, so also accept elements with a size.
      (element.offsetParent !== null || element.getClientRects().length > 0)
  );
}

interface UseFocusTrapOptions {
  /** Element that receives focus when the trap activates, if nothing inside is focused. */
  initialFocusRef?: RefObject<HTMLElement>;
  /** Called when Escape is pressed while the trap is active. */
  onEscape?: () => void;
}

/**
 * Keep keyboard focus inside a dialog/drawer while it is open.
 *
 * - Focuses `initialFocusRef` (or the first focusable element) on activation.
 * - Wraps Tab / Shift+Tab at the first and last focusable elements.
 * - Closes on Escape through `onEscape`.
 * - Restores focus to the element that opened the dialog on deactivation.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement>,
  active: boolean,
  { initialFocusRef, onEscape }: UseFocusTrapOptions = {}
) {
  const onEscapeRef = useRef(onEscape);
  const initialFocusRefRef = useRef(initialFocusRef);
  const wasActiveRef = useRef(false);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    onEscapeRef.current = onEscape;
    initialFocusRefRef.current = initialFocusRef;
  }, [onEscape, initialFocusRef]);

  // Capture the trigger during render, before child effects move focus into
  // the dialog, so focus can be restored to it when the dialog closes.
  if (active && !wasActiveRef.current) {
    previouslyFocusedRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  wasActiveRef.current = active;

  useEffect(() => {
    if (!active) return;

    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = previouslyFocusedRef.current;

    const focusInitial = () => {
      const target =
        initialFocusRefRef.current?.current ?? focusableElements(container)[0] ?? container;
      target.focus();
    };

    // Do not steal focus from an element the dialog already focused itself.
    if (!container.contains(document.activeElement)) {
      focusInitial();
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onEscapeRef.current?.();
        return;
      }

      if (event.key !== "Tab") return;

      const focusable = focusableElements(container);
      if (focusable.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;

      if (event.shiftKey) {
        if (current === first || !container.contains(current)) {
          event.preventDefault();
          last.focus();
        }
      } else if (current === last || !container.contains(current)) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [active, containerRef]);
}
