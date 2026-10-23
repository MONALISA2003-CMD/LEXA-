"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "./ui";
import { ApiError, getCachedSession, getCachedSetupProgress, getReadiness, getSetupProgress, logout, restoreSession, type AuthResponse, type ApiReadiness, type SetupProgress } from "../lib/api";

const primary = [
  ["/", "Home", "home"],
  ["/sales", "Sales", "cart"],
  ["/inventory", "Stock", "boxes"],
  ["/products", "Products", "package"],
  ["/customers", "Customers", "users"],
  ["/purchasing", "Purchases", "truck"],
  ["/accounting", "Finance", "wallet"],
  ["/reports", "Reports", "chart"],
  ["/team-chat", "Team chat", "chat"],
];
const quickNav = primary.slice(0, 4);
const moreWorkspaces = [
  ["/compliance", "Tax and receipts", "receipt"],
  ["/administration", "Business details", "building"],
  ["/administration/members", "Team and access", "users"],
  ["/workspace", "Switch business", "switch"],
  ["/onboarding", "Business setup", "check"],
  ["/settings", "Settings", "settings"],
];

function NavGlyph({ name }: { name: string }) {
  const props = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const shapes: Record<string, React.ReactNode> = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5.5 9v11h13V9M9 20v-6h4v6"/></>,
    cart: <><path d="M3 4h2l2.2 10.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 1.9-1.4L21 8H6"/><circle cx="10" cy="19" r="1.3"/><circle cx="17" cy="19" r="1.3"/></>,
    boxes: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4.4 7.7 7.6 4.4 7.6-4.4M12 12.1V21"/></>,
    package: <><path d="m12 3 8 4.2v9.6L12 21l-8-4.2V7.2L12 3Z"/><path d="M4.5 7.5 12 12l7.5-4.5M12 12v9M8.2 5l7.6 4.4"/></>,
    users: <><circle cx="9" cy="8" r="3.1"/><path d="M3.5 19v-1.2a5.5 5.5 0 0 1 11 0V19H3.5Z"/><path d="M16 5.2a3.1 3.1 0 0 1 0 5.7M17 14.2a4.1 4.1 0 0 1 3.5 4.1v.7h-4"/></>,
    truck: <><path d="M3 6h11v11H3zM14 10h4l3 3v4h-7z"/><circle cx="7" cy="19" r="1.7"/><circle cx="18" cy="19" r="1.7"/></>,
    wallet: <><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 8h15a2 2 0 0 1 2 2v2h-5a2 2 0 0 0 0 4h5"/><path d="M16 14h.01"/></>,
    chart: <><path d="M4 20V4M4 20h17"/><path d="m7 15 4-4 3 2 5-6"/><circle cx="19" cy="7" r="1"/></>,
    chat: <><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.7 8.7 0 0 1-3.7-.8L4 20l1.3-3.6A7.2 7.2 0 0 1 4 12c0-4.1 3.6-7.5 8-7.5s8 3.1 8 7Z"/><path d="M8 11h8M8 14h5"/></>,
    receipt: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h6M9 16h3"/></>,
    building: <><path d="M4 21V5l8-2 8 2v16M2 21h20"/><path d="M8 8h1M15 8h1M8 12h1M15 12h1M10 21v-4h4v4"/></>,
    switch: <><path d="M4 7h15l-3-3M20 17H5l3 3"/><path d="M16 4 19 7l-3 3M8 14l-3 3 3 3"/></>,
    check: <><circle cx="12" cy="12" r="9"/><path d="m7.5 12.5 3 3 6-7"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.1 1.8-1.8 3.1-2.1-.5a7.6 7.6 0 0 1-1.7 1l-.7 2h-3.6l-.7-2a7.6 7.6 0 0 1-1.7-1l-2.1.5-1.8-3.1 1.1-1.8a8.1 8.1 0 0 1 0-2l-1.1-1.8 1.8-3.1 2.1.5a7.6 7.6 0 0 1 1.7-1l.7-2h3.6l.7 2a7.6 7.6 0 0 1 1.7 1l2.1-.5 1.8 3.1-1.1 1.8a8.1 8.1 0 0 1 0 2Z" transform="translate(0 -1) scale(.9) translate(1.3 1.4)"/></>,
    more: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" {...props}>{shapes[name] || shapes.more}</svg>;
}

export function AppShell({ children, title, eyebrow }: { children: React.ReactNode; title?: string; eyebrow?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<AuthResponse | null>(() => getCachedSession());
  const [authState, setAuthState] = useState<"checking" | "ready" | "signed_out" | "unavailable">(() => getCachedSession() ? "ready" : "checking");
  const [authAttempt, setAuthAttempt] = useState(0);
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [serviceState, setServiceState] = useState<"checking" | "ready" | "degraded" | "unavailable">("checking");
  const [setupProgress, setSetupProgress] = useState<SetupProgress | null>(() => {
    const cached = getCachedSession();
    return cached ? getCachedSetupProgress(cached.tenant_id) : null;
  });
  const [setupProgressChecked, setSetupProgressChecked] = useState(() => {
    const cached = getCachedSession();
    return Boolean(cached && getCachedSetupProgress(cached.tenant_id));
  });

  useEffect(() => {
    let active = true;
    const cached = getCachedSession();
    if (cached) {
      setSession(cached);
      setAuthState("ready");
      return () => { active = false; };
    }
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
    if (authState !== "ready") { setSetupProgress(null); setSetupProgressChecked(false); return; }
    let active = true;
    const cached = session?.tenant_id ? getCachedSetupProgress(session.tenant_id) : null;
    // Keep the last verified snapshot visible during route changes. It is
    // refreshed below, but shouldn't hide a page while the request is pending.
    if (cached) { setSetupProgress(cached); setSetupProgressChecked(true); }
    else setSetupProgressChecked(false);
    void getSetupProgress().then((progress) => {
      if (active) { setSetupProgress(progress); setSetupProgressChecked(true); }
    }).catch(() => {
      // A prior verified snapshot is still useful when a background refresh
      // fails; without one, render the page and let its own loader explain data state.
      if (active) {
        if (!cached) setSetupProgress(null);
        setSetupProgressChecked(true);
      }
    });
    return () => { active = false; };
  }, [authState, pathname, session?.tenant_id]);

  useEffect(() => {
    let active = true;
    const checkReadiness = async () => {
      try {
        const readiness: ApiReadiness = await getReadiness();
        if (!active) return;
        setServiceState(String(readiness.status).toLowerCase() === "ready" ? "ready" : "degraded");
      } catch (error) {
        if (active) setServiceState(error instanceof ApiError && error.status === 503 ? "degraded" : "unavailable");
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
      /chat|message|handover|team discussion/.test(lower) ? "/team-chat" :
      `/reports?q=${encodeURIComponent(q)}`;
    setSearchOpen(false);
    router.push(destination);
  }

  const nav = (items: string[][]) => items.map(([href, label, icon]) => {
    const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
    return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`app-nav-item ${active ? "active" : ""}`}><span className="app-nav-icon"><NavGlyph name={icon}/></span><b>{label}</b></Link>;
  });
  const moreActive = moreWorkspaces.some(([href]) => pathname === href || pathname.startsWith(`${href}/`)) || !quickNav.some(([href]) => href === "/" ? pathname === "/" : pathname.startsWith(href));
  const serviceLabel = serviceState === "ready" ? "Your business is ready" : serviceState === "checking" ? "Checking that everything is ready" : serviceState === "degraded" ? "A few things need attention" : "Could not check business status";

  return <div className="app-shell">
    <aside className={`app-sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
      <Link href="/" className="app-brand" aria-label="LEXA home"><img className="app-brand-logo" src="/lexa-mark.svg" alt=""/><div><strong>LEXA</strong><small>Your business, clearly.</small></div></Link>
      <Link className="workspace-switch" href="/workspace" aria-label="Switch business"><small>YOUR BUSINESS</small><strong>{session?.tenant_name || "Your business"}</strong><span aria-hidden="true">⌄</span></Link>
      <nav className="app-nav" aria-label="Main navigation">
        {nav(primary)}
        <div className="nav-divider" />
        <button type="button" className={`sidebar-more-toggle ${moreActive ? "active" : ""}`} aria-expanded={moreOpen} onClick={() => setMoreOpen((value) => !value)}><span className="app-nav-icon"><NavGlyph name="more"/></span><b>Business settings</b><span className="sidebar-more-chevron" aria-hidden="true">{moreOpen ? "⌃" : "⌄"}</span></button>
        {moreOpen && <div className="sidebar-more-list">{nav(moreWorkspaces)}</div>}
      </nav>
      <div className="sidebar-foot">
        <span className={`status-dot ${authState === "ready" && serviceState === "ready" ? "" : "warning"}`} />
        <span className="sidebar-session-label">{authState === "ready" ? "Signed in" : authState === "checking" ? "Checking sign-in" : authState === "signed_out" ? "Signed out" : "Could not open your business"}</span>
        
        <button type="button" className="sidebar-signout" onClick={signOut}>Sign out</button>
      </div>
    </aside>
    {open && <button type="button" aria-label="Close navigation" className="app-scrim" onClick={() => setOpen(false)} />}
    <main className="app-main">
      <header className="app-topbar">
        <button type="button" className="mobile-menu" onClick={() => setOpen((value) => !value)} aria-label="Open navigation" aria-expanded={open}><NavGlyph name="menu"/></button>
        <form className="top-search" onSubmit={submitSearch} role="search"><button type="button" aria-label="Open business search" className="search-trigger" onClick={() => setSearchOpen(true)}><NavGlyph name="search"/></button><input aria-label="Search your business" value={search} onChange={e => setSearch(e.target.value)} onFocus={() => setSearchOpen(true)} placeholder="Search your business…" /><kbd>Ctrl K</kbd></form>
        <div className="top-actions"><button type="button" className="ask-lexa" onClick={() => router.push("/reports")}><span className="top-action-icon"><NavGlyph name="chart"/></span> Business reports</button><span className="avatar" aria-hidden="true">{session?.tenant_name?.slice(0,1).toUpperCase() || "U"}</span><button type="button" className="account-menu" onClick={signOut}>Sign out</button></div>
      </header>
      {searchOpen && <div className="command-overlay" role="dialog" aria-modal="true" aria-label="Business search">
        <button type="button" className="command-backdrop" aria-label="Close search" onClick={() => setSearchOpen(false)} />
        <div className="command-panel-float">
          <div className="command-search-head"><span aria-hidden="true">⌕</span><input autoFocus aria-label="Search business areas" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submitSearch(e); }} placeholder="Search products, stock, sales or purchases…" /><button type="button" onClick={() => setSearchOpen(false)}>Esc</button></div>
          <div className="command-suggestions">
            {[
              ["Inventory low stock", "/inventory"], ["Products and codes", "/products"], ["Today's sales", "/sales"], ["Customers and balances", "/customers"], ["Purchase orders", "/purchasing"], ["Money and expenses", "/accounting"], ["Business reports", "/reports"], ["Team messages", "/team-chat"], ["Settings and team", "/settings"],
            ].map(([item, href]) => <button key={item} type="button" onClick={() => { setSearchOpen(false); setSearch(""); router.push(href); }}>{item}<span aria-hidden="true">→</span></button>)}
          </div>
          <p className="command-hint">Search takes you to the right part of your business using your saved records.</p>
        </div>
      </div>}
      <section className="app-content">
        {authState !== "ready" ? (
          <div className="workspace-section" role={authState === "unavailable" ? "alert" : "status"} aria-live="polite">
            {authState === "checking" && <><span className="section-label">WELCOME BACK</span><h2>Opening your business…</h2><p>We’re checking your access before showing your saved records.</p></>}
            {authState === "signed_out" && <><span className="section-label">SIGN IN REQUIRED</span><h2>You’ve been signed out</h2><p>Returning you to sign in. You can also open the sign-in page directly.</p><Link className="text-link" href="/login">Go to sign in</Link></>}
            {authState === "unavailable" && <><span className="section-label">CONNECTION ISSUE</span><h2>We couldn’t open your business</h2><p>Your saved records have not been reported as changed. Check your connection and try again.</p><div className="header-actions"><button type="button" className="button button-soft" onClick={retrySession}>Try again</button><Link className="button button-soft" href="/login">Sign in again</Link></div></>}
          </div>
        ) : !setupProgressChecked ? (
          <div className="workspace-opening" role="status" aria-live="polite"><span className="workspace-opening-mark"><NavGlyph name="check"/></span><div><strong>Getting your business ready</strong><p>Checking the saved business details before showing your figures.</p></div></div>
        ) : (
          <>
            {title && <PageHeader eyebrow={eyebrow} title={title} context={<div className={`standard-page-context page-context-${serviceState}`} aria-live="polite"><span className={`status-dot ${serviceState === "ready" ? "" : "warning"}`} />{serviceLabel}</div>} />}
            {setupProgress && !setupProgress.complete && !["/onboarding", "/administration", "/settings", "/workspace", "/administration/members", "/accounting", "/commerce"].some(route => pathname === route || pathname.startsWith(`${route}/`)) ? (
              <section className="setup-welcome-card" role="status" aria-live="polite">
                <div className="setup-welcome-art"><span className="setup-welcome-orb orb-one"/><span className="setup-welcome-orb orb-two"/><span className="setup-welcome-mark"><NavGlyph name="check"/></span></div>
                <div className="setup-welcome-copy"><span className="section-label">ONE QUICK STEP</span><h2>Let's get your business ready</h2><p>Before we show sales, stock and money figures, let's verify your business details and currency, main branch and stock room, a payment method in that currency, and basic money-tracking accounts. This keeps all your business records connected.</p>
                  <div className="setup-step-pills">{setupProgress.steps.filter(step => step.required).map(step => <span key={step.key} className={step.complete ? "done" : "todo"}><i aria-hidden="true">{step.complete ? "✓" : "○"}</i>{step.label}</span>)}</div>
                  <div className="header-actions"><Link href="/onboarding" className="button button-dark">Finish business setup</Link><Link href="/administration" className="button button-soft">Review business details</Link></div>
                </div>
              </section>
            ) : (
              <>
                {setupProgress && !setupProgress.complete && pathname !== "/onboarding" && <section className="business-setup-alert" role="status" aria-live="polite"><div className="business-setup-icon" aria-hidden="true"><NavGlyph name="check"/></div><div className="business-setup-copy"><strong>A few business details still need attention</strong><p>Finish the business details that still need attention so sales, stock and money records stay connected.</p></div><Link href="/onboarding" className="button button-dark button-small">Finish setup</Link></section>}
                {children}
              </>
            )}
          </>
        )}
      </section>
    </main>
    <nav className="mobile-nav" aria-label="Quick navigation">
      {quickNav.map(([href, label, icon]) => <Link key={href} href={href} aria-current={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "page" : undefined} className={(href === "/" ? pathname === "/" : pathname.startsWith(href)) ? "active" : ""}><span className="mobile-nav-icon"><NavGlyph name={icon}/></span><small>{label}</small></Link>)}
      <button type="button" className={open || moreActive ? "active" : ""} onClick={() => setOpen((value) => !value)} aria-label={open ? "Close business settings" : "Open business settings"} aria-expanded={open}><span className="mobile-nav-icon"><NavGlyph name="more"/></span><small>More</small></button>
    </nav>
  </div>;
}
