"use client";

import { useEffect, useState } from "react";
import { getHealth, type ApiHealth } from "../lib/api";

export default function HomePage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((result) => {
        setHealth(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setHealth(null);
        setError(err instanceof Error ? err.message : "LEXA API health check failed.");
      });

    return () => controller.abort();
  }, []);

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">LEXA</p>
        <h1>Business operating system</h1>
        <p className="muted">
          Vercel is serving the Next.js frontend and Render is serving the LEXA API.
        </p>
        <div className="status" role="status" aria-live="polite">
          <span className={health ? "dot online" : "dot"} />
          {health
            ? `API online — ${health.environment ?? "environment unknown"}`
            : error ?? "Checking LEXA API…"}
        </div>
      </section>
    </main>
  );
}
