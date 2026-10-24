"use client";

import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import styles from "./page.module.css";

const businessTools = [
  {
    href: "/sales",
    title: "Review sales",
    description: "Check recent sales and see how your business is performing.",
    action: "View sales",
  },
  {
    href: "/inventory",
    title: "Check stock",
    description: "See what is available and which products may need attention.",
    action: "View stock",
  },
  {
    href: "/reports",
    title: "Explore reports",
    description: "Review business totals and compare activity over time.",
    action: "Open reports",
  },
  {
    href: "/purchasing",
    title: "Plan purchases",
    description: "Review suppliers, orders and deliveries before making a decision.",
    action: "View purchases",
  },
  {
    href: "/customers",
    title: "Follow up with customers",
    description: "Review customer records, payments and amounts still due.",
    action: "View customers",
  },
  {
    href: "/documents",
    title: "Check business documents",
    description: "Review invoices, receipts and other documents before using their details.",
    action: "View documents",
  },
];

export default function AiAssistantPage() {
  return <AppShell title="Business assistant" eyebrow="BUSINESS SUPPORT">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1160 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · BUSINESS SUPPORT</span>
          <h1>Guidance for your business.</h1>
          <p>Use LEXA’s business tools to check your records, understand recent activity and decide what to do next.</p>
        </div>
      </div>

      <section className={`workspace-section ${styles.section}`} aria-labelledby="assistant-status-title">
        <div className={styles.statusIcon} aria-hidden="true">✦</div>
        <div className={styles.statusCopy}>
          <span className="section-label">BUSINESS GUIDANCE</span>
          <h2 id="assistant-status-title">The assistant isn’t available right now.</h2>
          <p>You can still use the tools below to review your business information. This page will not generate or pretend to generate an answer while the assistant is unavailable.</p>
        </div>
      </section>

      <section className={styles.toolsSection} aria-labelledby="available-tools-title">
        <div className="section-head">
          <div>
            <span className="section-label">TOOLS YOU CAN USE NOW</span>
            <h2 id="available-tools-title">Where would you like to start?</h2>
            <p>Choose a working LEXA tool to view your saved business information.</p>
          </div>
        </div>
        <div className={styles.toolGrid}>
          {businessTools.map((tool) => <article className={styles.toolCard} key={tool.href}>
            <div>
              <h3>{tool.title}</h3>
              <p>{tool.description}</p>
            </div>
            <Link href={tool.href} className={styles.toolLink}>{tool.action}<span aria-hidden="true">→</span></Link>
          </article>)}
        </div>
      </section>

      <p className={styles.footerNote}>Keep passwords, payment credentials and private customer details out of messages or notes. Check important figures against the original business records before acting.</p>
    </main>
  </AppShell>;
}
