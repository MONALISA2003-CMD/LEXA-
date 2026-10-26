import type { Metadata } from "next";
import "./globals.css";
import "./lexa-brand-authority.css";

export const metadata: Metadata = {
  title: "LEXA | Sales · Inventory · Business Management",
  description: "LEXA brings sales, inventory and business management together in one clear workspace.",
  applicationName: "LEXA",
  keywords: ["LEXA", "sales", "inventory", "business management", "business intelligence"],
  icons: {
    icon: [
      { url: "/lexa-mark.svg", type: "image/svg+xml" },
      { url: "/lexa-app-mark.png", sizes: "512x512", type: "image/png" },
      { url: "/lexa-app-mark.png", sizes: "192x192", type: "image/png" },
    ],
    shortcut: "/lexa-mark.svg",
    apple: "/lexa-app-mark.png",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
