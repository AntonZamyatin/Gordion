import { useEffect } from "react";
import { useSigma } from "@react-sigma/core";

export function SigmaAutoResize() {
  const sigma = useSigma();

  useEffect(() => {
    const el = sigma.getContainer();

    let raf = 0;
    const ro = new ResizeObserver(() => {
      // Coalesce multiple resize notifications into one per frame:
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        // Resize renderer if exposed, then refresh:
        const renderer = (sigma as any).getRenderer?.() ?? (sigma as any).renderer;
        renderer?.resize?.();
        sigma.refresh();
      });
    });

    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [sigma]);

  return null;
}
