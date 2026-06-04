import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodePilot",
  description: "AI code review agent for new graduate AI engineering portfolios"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

