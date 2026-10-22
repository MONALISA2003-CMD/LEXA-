"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "./ui";
import { getReadiness, getSetupProgress, logout, restoreSession, type AuthResponse, type ApiReadiness, type SetupProgress } from "../lib/api";

const primary = [
  ["/", "Home", "⌂"],
  ["/sales", "Sales", "▣"],
  ["/inventory", "Stock", "◈"],
  ["/products", "Products", "□"],
  ["/customers", "Customers", "◎"],
  ["/purchasing", "Purchases", "↗"],
  ["/accounting", "Finance", "¤"],
  ["/reports", "Reports", "▥"],
];
const quickNav = primary.slice(0, 4);
const moreWorkspaces = [
  ["/compliance", "Tax and receipts", "✓"],
  ["/administration", "Business details", "⚙"],
  ["/administration/members", "Team and access", "♙"],
  ["/workspace", "Switch business", "↔"],
  ["/onboarding", "Business setup", "✓"],
  ["/settings", "Settings", "◌"],
];

export function AppShell({ children, title, eyebrow }: { children: React.ReactNode; title?: string; eyebrow?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [authState, setAuthState] = useState<"checking" | "ready" | "signed_out" | "unavailable">("checking");
  const [authAttempt, setAuthAttempt] = useState(0);
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [serviceState, setServiceState] = useState<"checking" | "ready" | "degraded" | "unavailable">("checking");
  const [setupProgress, setSetupProgress] = useState<SetupProgress | null>(null);

  useEffect(() => {
    let active = true;
    setAuthState("checking");
    void restoreSession().then((value) => {
      if (!active) return;
      setSession(value);
      setAuthState(value ? "ready" : "signed_out");
      if (!value) router.replace("/login");
    }).catch(() => {
      if (active) setAuthState("unavailable");
    });
    return () => { active = false; };
  }, [router, authAttempt]);
  useEffect(() => {
    setOpen(false);
    if (moreWorkspaces.some(([href]) => href === pathname || pathname.startsWith(`${href}/`))) setMoreOpen(true);
  }, [pathname]);
  useEffect(() => {
    if (authState !== "ready") { setSetupProgress(null); return; }
    let active = true;
    void getSetupProgress().then((progress) => {
      if (active) setSetupProgress(progress);
    }).catch(() => {
      // Keep the shell usable if setup status cannot be checked; page-level
      // requests still explain any real data access problem.
      if (active) setSetupProgress(null);
    });
    return () => { active = false; };
  }, [authState, pathname]);

  useEffect(() => {
    let active = true;
    const checkReadiness = async () => {
      try {
        const readiness: ApiReadiness = await getReadiness();
        if (!active) return;
        setServiceState(String(readiness.status).toLowerCase() === "ready" ? "ready" : "degraded");
      } catch {
        if (active) setServiceState("unavailable");
      }
    };
    void checkReadiness();
    const timer = window.setInterval(() => void checkReadiness(), 60_000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === "Escape") setSearchOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function retrySession() {
    setAuthState("checking");
    setAuthAttempt((attempt) => attempt + 1);
  }

  async function signOut() {
    try {
      await logout();
    } catch {
      // Signing out locally must remain possible when the API is unreachable.
    } finally {
      setSession(null);
      setAuthState("signed_out");
      router.replace("/login");
    }
  }
  function submitSearch(event?: { preventDefault(): void }) {
    event?.preventDefault();
    const q = search.trim();
    if (!q) return;
    const lower = q.toLowerCase();
    const destination =
      /customer|client|debtor|receivable/.test(lower) ? `/customers?q=${encodeURIComponent(q)}` :
      /inventory|stock|warehouse|transfer|count|adjustment/.test(lower) ? `/inventory?q=${encodeURIComponent(q)}` :
      /product|product code|sku|barcode|catalog/.test(lower) ? `/products?q=${encodeURIComponent(q)}` :
      /sale|pos|invoice|payment|receipt/.test(lower) ? `/sales?q=${encodeURIComponent(q)}` :
      /purchase|supplier|receiving/.test(lower) ? `/purchasing?q=${encodeURIComponent(q)}` :
      /finance|journal|expense|accounting|money owed/.test(lower) ? `/accounting?q=${encodeURIComponent(q)}` :
      `/reports?q=${encodeURIComponent(q)}`;
    setSearchOpen(false);
    router.push(destination);
  }

  const nav = (items: string[][]) => items.map(([href, label, icon]) => {
    const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
    return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`app-nav-item ${active ? "active" : ""}`}><span aria-hidden="true">{icon}</span><b>{label}</b></Link>;
  });
  const moreActive = moreWorkspaces.some(([href]) => pathname === href || pathname.startsWith(`${href}/`));
  const serviceLabel = serviceState === "ready" ? "Connected" : serviceState === "checking" ? "Checking connection" : serviceState === "degraded" ? "Connection needs attention" : "Connection unavailable";

  return <div className="app-shell">
    <aside className={`app-sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
      <Link href="/" className="app-brand" aria-label="LEXA home"><img className="app-brand-logo" src="/lexa-mark.svg" alt=""/><div><strong>LEXA</strong><small>Your business, clearly.</small></div></Link>
      <Link className="workspace-switch" href="/workspace" aria-label="Switch business"><small>YOUR BUSINESS</small><strong>{session?.tenant_name || "Your business"}</strong><span aria-hidden="true">⌄</span></Link>
      <nav className="app-nav" aria-label="Main navigation">
        {nav(primary)}
        <div className="nav-divider" />
        <button type="button" className={`sidebar-more-toggle ${moreActive ? "active" : ""}`} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><span aria-hidden="true">⋯</span><b>Business settings</b><span className="sidebar-more-chevron" aria-hidden="true">{moreOpen ? "⌃" : "⌄"}</span></button>
        {moreOpen && <div className="sidebar-more-list">{nav(moreWorkspaces)}</div>}
      </nav>
      <div className="sidebar-foot">
        <span className={`status-dot ${authState === "ready" && serviceState === "ready" ? "" : "warning"}`} />
        <span className="sidebar-session-label">{authState === "ready" ? "Signed in" : authState === "checking" ? "Checking access" : authState === "signed_out" ? "Signed out" : "Connection issue"}</span>
        
        <button type="button" className="sidebar-signout" onClick={signOut}>Sign out</button>
      </div>
    </aside>
    {open && <button type="button" aria-label="Close navigation" className="app-scrim" onClick={() => setOpen(false)} />}
    <main className="app-main">
      <header className="app-topbar">
        <button type="button" className="mobile-menu" onClick={() => setOpen((value) => !value)} aria-label="Open navigation" aria-expanded={open}>☰</button>
        <form className="top-search" onSubmit={submitSearch} role="search"><button type="button" aria-label="Open business search" className="search-trigger" onClick={() => setSearchOpen(true)}>⌕</button><input aria-label="Search your business" value={search} onChange={e => setSearch(e.target.value)} onFocus={() => setSearchOpen(true)} placeholder="Search your business…" /><kbd>Ctrl K</kbd></form>
        <div className="top-actions"><button type="button" className="ask-lexa" onClick={() => router.push("/reports")}><span aria-hidden="true">▥</span> Business reports</button><span className="avatar" aria-hidden="true">{session?.tenant_name?.slice(0,1).toUpperCase() || "U"}</span><button type="button" className="account-menu" onClick={signOut}>Sign out</button></div>
      </header>
      {searchOpen && <div className="command-overlay" role="dialog" aria-modal="true" aria-label="Business search">
        <button type="button" className="command-backdrop" aria-label="Close search" onClick={() => setSearchOpen(false)} />
        <div className="command-panel-float">
          <div className="command-search-head"><span aria-hidden="true">⌕</span><input autoFocus aria-label="Search business areas" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submitSearch(e); }} placeholder="Search products, stock, sales or purchases…" /><button type="button" onClick={() => setSearchOpen(false)}>Esc</button></div>
          <div className="command-suggestions">
            {[
              ["Inventory low stock", "/inventory"], ["Products and codes", "/products"], ["Today's sales", "/sales"], ["Customers and balances", "/customers"], ["Purchase orders", "/purchasing"], ["Money and expenses", "/accounting"], ["Business reports", "/reports"], ["Settings and team", "/settings"],
            ].map(([item, href]) => <button key={item} type="button" onClick={() => { setSearchOpen(false); setSearch(""); router.push(href); }}>{item}<span aria-hidden="true">→</span></button>)}
          </div>
          <p className="command-hint">Search takes you to the right part of your business using your saved records.</p>
        </div>
      </div>}
      <section className="app-content">
        {authState !== "ready" ? (
          <div className="workspace-section" role={authState === "unavailable" ? "alert" : "status"} aria-live="polite">
            {authState === "checking" && <><span className="section-label">WELCOME BACK</span><h2>Opening your business…</h2><p>We’re checking your access before showing your saved records.</p></>}
            {authState === "signed_out" && <><span className="section-label">SIGN IN REQUIRED</span><h2>Your session has ended</h2><p>Returning you to sign in. You can also open the sign-in page directly.</p><Link className="text-link" href="/login">Go to sign in</Link></>}
            {authState === "unavailable" && <><span className="section-label">CONNECTION ISSUE</span><h2>We couldn’t open your business</h2><p>Your saved records have not been reported as changed. Check your connection and try again.</p><div className="header-actions"><button type="button" className="button button-soft" onClick={retrySession}>Try again</button><Link className="button button-soft" href="/login">Sign in again</Link></div></>}
          </div>
        ) : (
          <>
            {title && <PageHeader eyebrow={eyebrow} title={title} context={<div className={`standard-page-context page-context-${serviceState}`} aria-live="polite"><span className={`status-dot ${serviceState === "ready" ? "" : "warning"}`} />{serviceLabel}</div>} />}
            {setupProgress && !setupProgress.complete && pathname !== "/onboarding" && <section className="business-setup-alert" role="status" aria-live="polite"><div className="business-setup-icon" aria-hidden="true">✓</div><div className="business-setup-copy"><strong>Your business needs a few setup details</strong><p>Add a main branch, stock room and stock location so sales, stock and reports can work together.</p></div><Link href="/onboarding" className="button button-dark button-small">Finish setup</Link></section>}
            {children}
          </>
        )}
      </section>
    </main>
    <nav className="mobile-nav" aria-label="Quick navigation">
      {quickNav.map(([href, label, icon]) => <Link key={href} href={href} aria-current={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "page" : undefined} className={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "active" : ""}><span aria-hidden="true">{icon}</span><small>{label}</small></Link>)}
      <button type="button" className={open || moreActive ? "active" : ""} onClick={() => setOpen((value) => !value)} aria-label={open ? "Close business settings" : "Open business settings"} aria-expanded={open}><span aria-hidden="true">⋯</span><small>More</small></button>
    </nav>
  </div>;
}
