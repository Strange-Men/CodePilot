import type { Metadata } from "next";
import "highlight.js/styles/github.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodePilot Review Workspace",
  description: "Evidence-grounded AI code review workspace"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const saved = localStorage.getItem("codepilot-theme");
                const dark = saved === "dark" || (!saved && matchMedia("(prefers-color-scheme: dark)").matches);
                document.documentElement.classList.toggle("dark", dark);
              } catch {}
            `
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
