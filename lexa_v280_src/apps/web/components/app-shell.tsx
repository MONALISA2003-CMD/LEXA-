"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { logout, restoreSession, type AuthResponse } from "../lib/api";

const primary = [
  ["/", "Home", "⌂"],
  ["/sales", "Sales", "▣"],
  ["/inventory", "Inventory", "◈"],
  ["/purchasing", "Purchasing", "↗"],
  ["/customers", "Customers", "◎"],
  ["/products", "Products", "□"],
  ["/accounting", "Finance", "¤"],
  ["/reports", "Reports", "▥"],
  ["/compliance", "Compliance", "✓"],
];
const secondary = [
  ["/intelligence", "AI Intelligence", "✦"],
  ["/administration", "Administration", "⚙"],
  ["/settings", "Settings", "◌"],
];

export function AppShell({ children, title, eyebrow }: { children: React.ReactNode; title?: string; eyebrow?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [authState, setAuthState] = useState<"checking" | "ready" | "signed_out" | "unavailable">("checking");
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    let active = true;
    void restoreSession().then((value) => {
      if (!active) return;
      setSession(value);
      setAuthState(value ? "ready" : "signed_out");
      if (!value) router.replace("/login");
    }).catch(() => {
      if (active) setAuthState("unavailable");
    });
    return () => { active = false; };
  }, [router]);
  useEffect(() => { setOpen(false); }, [pathname]);
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

  async function signOut() { await logout(); router.replace("/login"); }
  function submitSearch(event?: { preventDefault(): void }) {
    event?.preventDefault();
    const q = search.trim();
    if (!q) return;
    const lower = q.toLowerCase();
    const destination =
      /inventory|stock|warehouse|transfer|count|adjustment/.test(lower) ? `/inventory?q=${encodeURIComponent(q)}` :
      /product|sku|barcode|catalog/.test(lower) ? `/products?q=${encodeURIComponent(q)}` :
      /sale|pos|invoice|customer|payment|receipt/.test(lower) ? `/sales?q=${encodeURIComponent(q)}` :
      /purchase|supplier|receiving/.test(lower) ? `/purchasing?q=${encodeURIComponent(q)}` :
      /finance|journal|expense|accounting/.test(lower) ? `/accounting?q=${encodeURIComponent(q)}` :
      `/reports?q=${encodeURIComponent(q)}`;
    setSearchOpen(false);
    router.push(destination);
  }

  const nav = (items: string[][]) => items.map(([href, label, icon]) => {
    const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
    return <Link key={href} href={href} className={`app-nav-item ${active ? "active" : ""}`}><span>{icon}</span><b>{label}</b></Link>;
  });

  return <div className="app-shell">
    <aside className={`app-sidebar ${open ? "open" : ""}`}>
      <div className="app-brand"><span className="app-brand-mark">L</span><div><strong>LEXA</strong><small>Business workspace</small></div></div>
      <div className="workspace-switch"><small>WORKSPACE</small><strong>{session?.tenant_name || "Your business"}</strong><span>⌄</span></div>
      <nav className="app-nav">{nav(primary)}<div className="nav-divider" />{nav(secondary)}</nav>
      <div className="sidebar-foot"><span className="status-dot" /> Online<span className="sidebar-version">v2.8</span></div>
    </aside>
    {open && <button aria-label="Close navigation" className="app-scrim" onClick={() => setOpen(false)} />}
    <main className="app-main">
      <header className="app-topbar">
        <button className="mobile-menu" onClick={() => setOpen(v => !v)} aria-label="Open navigation">☰</button>
        <form className="top-search" onSubmit={submitSearch}><button type="button" aria-label="Open search" className="search-trigger" onClick={() => setSearchOpen(true)}>⌕</button><input value={search} onChange={e => setSearch(e.target.value)} onFocus={() => setSearchOpen(true)} placeholder="Search your business…" /><kbd>⌘ K</kbd></form>
        <div className="top-actions"><button className="ask-lexa" onClick={() => router.push("/intelligence")}><span>✦</span> Ask LEXA</button><button className="icon-button" aria-label="Notifications">♢</button><button className="avatar" aria-label="Account menu">{session?.tenant_name?.slice(0,1).toUpperCase() || "U"}</button><button className="account-menu" onClick={signOut}>Sign out</button></div>
      </header>
      {searchOpen && <div className="command-overlay" role="dialog" aria-modal="true" aria-label="Business search">
        <button className="command-backdrop" aria-label="Close search" onClick={() => setSearchOpen(false)} />
        <div className="command-panel-float">
          <div className="command-search-head"><span>⌕</span><input autoFocus value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submitSearch(e); }} placeholder="Search products, stock, sales, purchases…" /><button type="button" onClick={() => setSearchOpen(false)}>Esc</button></div>
          <div className="command-suggestions">
            {["Inventory low stock", "Products and SKUs", "Today's sales", "Purchase orders", "Finance and journals", "Business reports"].map(item => <button key={item} type="button" onClick={() => { setSearch(item); setSearchOpen(false); setTimeout(() => submitSearch(), 0); }}>{item}<span>→</span></button>)}
          </div>
          <p className="command-hint">LEXA search routes you to the appropriate authoritative workspace. It does not replace transaction validation.</p>
        </div>
      </div>}
      <section className="app-content">
        {authState === "unavailable" && <div className="workspace-banner attention"><span className="banner-icon">!</span><div><strong>LEXA is temporarily unavailable</strong><p>Your session could not be checked because the application service is unavailable. No transaction has been reported as complete.</p></div></div>}
        {(title || eyebrow) && <div className="page-heading"><div>{eyebrow && <div className="page-eyebrow">{eyebrow}</div>}<h1>{title}</h1></div><div className="page-context"><span className="status-dot" /> Live workspace</div></div>}
        {children}
      </section>
    </main>
    <nav className="mobile-nav">{primary.slice(0,5).map(([href,label,icon]) => <Link key={href} href={href} className={pathname === href ? "active" : ""}><span>{icon}</span><small>{label}</small></Link>)}</nav>
  </div>;
}
