/**
 * useSmoothPosition — interpolates a [lat, lng] target using rAF + cubic ease-out.
 * Duration is intentionally shorter than the GPS tick interval (~1400ms) so the
 * animation completes before the next tick arrives, keeping motion fluid.
 */
import { useState, useEffect, useRef } from 'react';

export default function useSmoothPosition(target, durationMs = 1000) {
  const [pos, setPos] = useState(target);
  const prevRef  = useRef(target);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!target) return;

    // Cancel any in-progress animation
    if (frameRef.current) cancelAnimationFrame(frameRef.current);

    const start     = prevRef.current || target;
    const startTime = performance.now();

    const animate = (now) => {
      const elapsed = now - startTime;
      const t       = Math.min(1, elapsed / durationMs);
      // Cubic ease-out: starts fast, decelerates smoothly
      const eased   = 1 - Math.pow(1 - t, 3);

      const lat = start[0] + (target[0] - start[0]) * eased;
      const lng = start[1] + (target[1] - start[1]) * eased;
      setPos([lat, lng]);

      if (t < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        prevRef.current  = target;
        frameRef.current = null;
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, durationMs]);

  return pos;
}
