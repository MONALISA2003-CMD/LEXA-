"use client";

import { useEffect, useState } from "react";

const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

type Health = { status: string; service?: string; environment?: string };

export default function HomePage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiUrl) {
      setError("NEXT_PUBLIC_API_URL is not configured.");
      return;
    }
    fetch(`${apiUrl}/health`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`API returned HTTP ${response.status}`);
        return response.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "API health check failed."));
  }, []);

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">LEXA</p>
        <h1>Business operating system</h1>
        <p className="muted">Frontend deployment is connected to the LEXA API.</p>
        <div className="status">
          <span className={health ? "dot online" : "dot"} />
          {health ? `API online — ${health.environment ?? "environment unknown"}` : error ?? "Checking API…"}
        </div>
      </section>
    </main>
  );
}
