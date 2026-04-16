import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white dark:bg-zinc-950 font-sans selection:bg-zinc-200 dark:selection:bg-zinc-800">
      <main className="flex w-full max-w-4xl flex-col items-center justify-center p-8 text-center sm:p-16">
        <div className="mb-8 inline-flex items-center rounded-full border border-zinc-200 bg-zinc-50 px-4 py-1.5 text-sm tracking-wide text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
          <span className="mr-2 flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Learning Assistant Online
        </div>
        
        <h1 className="max-w-3xl text-5xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-6xl lg:text-7xl mb-6">
          Willkommen bei <br className="hidden sm:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-zinc-900 to-zinc-500 dark:from-zinc-100 dark:to-zinc-600">Lernkompanien</span>
        </h1>
        
        <p className="max-w-2xl text-lg leading-relaxed text-zinc-600 dark:text-zinc-400 mb-10">
          Dein intelligenter Begleiter für strukturiertes Lernen, persönliche Weiterentwicklung und messbare Erfolge.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto">
          <Link
            href="/dashboard"
            className="group relative flex h-14 w-full sm:w-auto items-center justify-center gap-2 overflow-hidden rounded-full bg-zinc-900 px-8 font-medium text-white transition-all hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            <span>Zum Dashboard</span>
            <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-1" />
          </Link>
          <Link
            href="/kurse"
            className="flex h-14 w-full sm:w-auto items-center justify-center rounded-full border border-zinc-200 bg-white px-8 font-medium text-zinc-900 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:bg-zinc-900"
          >
            Kurskatalog
          </Link>
        </div>
      </main>
    </div>
  );
}
