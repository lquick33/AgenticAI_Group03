import { TargetIcon, ZapIcon, CheckCircle2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function SectionCards() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 px-4 lg:px-8 mb-8 mt-4">
      {/* Primary Hero Metric */}
      <Card className="md:col-span-2 lg:col-span-2 bg-zinc-950 border-zinc-800 text-zinc-50 shadow-md relative overflow-hidden transition-all duration-300 hover:-translate-y-1">
        <CardHeader className="relative z-10">
          <CardDescription className="text-zinc-400 text-xs font-semibold tracking-wider uppercase mb-1">
            Dein aktuelles Lernziel
          </CardDescription>
          <CardTitle className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
            Meilenstein 1: Grundlagen
          </CardTitle>
          <div>
            <Badge variant="secondary" className="bg-zinc-800/80 text-zinc-100 hover:bg-zinc-800 px-3 py-1 rounded-md text-xs border border-zinc-700/50">
              <TargetIcon className="size-3.5 mr-1.5" />
              65% Abgeschlossen
            </Badge>
          </div>
        </CardHeader>
        <CardFooter className="relative z-10 flex-col items-start gap-2 pt-8">
          <div className="flex gap-2 font-medium text-sm text-zinc-300">
            Du bist auf einem sehr guten Weg für diese Woche.
          </div>
          <div className="w-full bg-zinc-800/80 rounded-full h-1.5 mt-2 overflow-hidden">
            <div className="bg-zinc-100 h-1.5 rounded-full" style={{ width: "65%" }}></div>
          </div>
        </CardFooter>
        <div className="absolute right-0 bottom-0 opacity-[0.03] pointer-events-none translate-x-1/4 translate-y-1/4 text-white">
          <TargetIcon className="w-72 h-72" />
        </div>
      </Card>

      {/* Secondary Metrics */}
      <Card className="border-zinc-200 dark:border-zinc-800 shadow-sm bg-white dark:bg-zinc-950 transition-all duration-300 hover:-translate-y-1 flex flex-col justify-between">
        <CardHeader className="pb-2">
          <div className="flex justify-between items-start">
            <CardDescription className="font-semibold text-zinc-500 dark:text-zinc-400 text-xs tracking-wider uppercase">Streak</CardDescription>
            <ZapIcon className="size-4 text-amber-500" />
          </div>
          <CardTitle className="text-3xl font-bold tracking-tight mt-2">
            12 Tage
          </CardTitle>
        </CardHeader>
        <CardFooter className="pt-0 text-sm text-zinc-500 dark:text-zinc-400 font-medium pb-5">
          Dein Bestwert: 14 Tage
        </CardFooter>
      </Card>

      <Card className="border-zinc-200 dark:border-zinc-800 shadow-sm bg-white dark:bg-zinc-950 transition-all duration-300 hover:-translate-y-1 flex flex-col justify-between">
        <CardHeader className="pb-2">
          <div className="flex justify-between items-start">
            <CardDescription className="font-semibold text-zinc-500 dark:text-zinc-400 text-xs tracking-wider uppercase">Geprüftes Wissen</CardDescription>
            <CheckCircle2Icon className="size-4 text-emerald-500" />
          </div>
          <CardTitle className="text-3xl font-bold tracking-tight mt-2">
            345
          </CardTitle>
        </CardHeader>
        <CardFooter className="pt-0 text-sm text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1 pb-5">
          <span className="text-emerald-600 dark:text-emerald-500">+24</span> diese Woche
        </CardFooter>
      </Card>
      
    </div>
  )
}
