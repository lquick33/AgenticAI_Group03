import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "katex/dist/katex.min.css";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Lernkompanien - Adaptive Learning Assistant",
  description: "AI-powered learning ecosystem that helps students with planning, tutoring, and motivation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased selection:bg-zinc-200 dark:selection:bg-zinc-800`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
