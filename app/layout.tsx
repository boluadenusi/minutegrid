import type { Metadata } from "next";
import { fontVariables } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"
  ),
  title: "Minute Grid",
  description: "See which minutes a footballer has scored in.",
  openGraph: {
    title: "Minute Grid",
    description: "See which minutes a footballer has scored in.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={fontVariables}>
      <body
        className="antialiased bg-tone-950 text-tone-100 min-h-screen"
      >
        {children}
        <footer className="site-footer">
          <a href="https://buymeamalt.com/@boluadenusi" target="_blank" rel="noopener noreferrer">Buy me a malt</a>
          <span aria-hidden>·</span>
          <a href="https://x.com/@boluadenusi" target="_blank" rel="noopener noreferrer">Boluwatife on X</a>
        </footer>
      </body>
    </html>
  );
}
