import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LEXA | Your business, clearly.",
  description: "Sales, stock, customers and finance in one clear business workspace.",
  icons: {
    icon: [
      { url: "/lexa-mark.svg", type: "image/svg+xml" },
      { url: "/lexa-icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/lexa-icon.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/lexa-icon-180.png",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
