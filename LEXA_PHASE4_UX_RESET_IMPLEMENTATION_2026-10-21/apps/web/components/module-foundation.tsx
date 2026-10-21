import Link from "next/link";
import { AppShell } from "./app-shell";

export function ModuleFoundation({ title, eyebrow, description, available, next }: { title: string; eyebrow: string; description: string; available: string[]; next: string[] }) {
  return <AppShell title={title} eyebrow={eyebrow}>
    <div className="foundation-hero"><div><p className="eyebrow">WORKSPACE FOUNDATION</p><h2>{description}</h2><p>This route is intentionally real and navigable while the deeper vertical workflow is completed. Nothing here pretends to have completed an operation that the backend does not yet expose.</p></div><Link className="button button-dark" href="/">Back to Command Centre</Link></div>
    <div className="foundation-grid">
      <section className="panel foundation-panel"><div className="panel-head"><div><p className="eyebrow">AVAILABLE NOW</p><h2>Connected capabilities</h2></div></div><div className="foundation-list">{available.map(item=><div className="foundation-row" key={item}><span className="status-dot"/><strong>{item}</strong></div>)}</div></section>
      <section className="panel foundation-panel"><div className="panel-head"><div><p className="eyebrow">NEXT VERTICAL</p><h2>Planned depth</h2></div></div><div className="foundation-list">{next.map(item=><div className="foundation-row" key={item}><span>→</span><strong>{item}</strong></div>)}</div></section>
    </div>
  </AppShell>;
}