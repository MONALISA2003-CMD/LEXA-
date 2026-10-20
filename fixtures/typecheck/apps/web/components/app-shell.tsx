import type { ReactNode } from "react";
export function AppShell(props: { children: ReactNode; title?: string; eyebrow?: string }) { return <section>{props.children}</section>; }
