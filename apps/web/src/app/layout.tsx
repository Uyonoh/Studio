import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { ErrorBoundary } from "@/components/error-boundary";

export const metadata: Metadata = {
  title: "Studio — AI Content Creation Platform",
  description: "Generate images and videos with state-of-the-art AI models.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0B0C10] text-[#E8EAF0] antialiased selection:bg-[#7C5CFF]/30">
        <ErrorBoundary>
          <QueryProvider>{children}</QueryProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
