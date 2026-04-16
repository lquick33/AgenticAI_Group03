"use client"

import { useEffect, useMemo } from "react"
import { useForm } from "react-hook-form"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, Monitor, Moon, Settings2, Sun } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { createClient } from "@/lib/supabase/client"
import { useSettings } from "./settings-context"

interface UserPreferences {
  id?: string
  user_id: string
  learning_style: "linear" | "iterative"
  agent_persona: "strict" | "humorous" | "buddy"
  default_deduplicate_flashcards?: boolean
  theme_preference?: "light" | "dark" | "system"
  auto_explain_on_page_change?: boolean
}

interface SettingsFormValues {
  autoExplainOnPageChange: boolean
  deduplicateDefault: boolean
  learningStyle: "linear" | "iterative"
  agentPersona: "strict" | "humorous" | "buddy"
  themePreference: "light" | "dark" | "system"
}

const defaultValues: SettingsFormValues = {
  autoExplainOnPageChange: true,
  deduplicateDefault: false,
  learningStyle: "linear",
  agentPersona: "buddy",
  themePreference: "system",
}

export function SettingsDialog() {
  const { isOpen, closeSettings } = useSettings()
  const supabase = useMemo(() => createClient(), [])
  const queryClient = useQueryClient()
  
  const form = useForm<SettingsFormValues>({
    defaultValues,
  })

  const { data: userData, isLoading: isUserLoading } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        toast.error("Nicht angemeldet")
        closeSettings()
        return null
      }
      return user
    },
    enabled: isOpen
  })

  const { data: prefs, isLoading: isPrefsLoading } = useQuery({
    queryKey: ['user_preferences', userData?.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("user_preferences")
        .select("*")
        .eq("user_id", userData!.id)
        .single()
      
      if (error && error.code !== "PGRST116") throw error
      return data || null
    },
    enabled: isOpen && !!userData?.id
  })

  useEffect(() => {
    if (prefs !== undefined) {
      const savedTheme = typeof window !== "undefined"
          ? (localStorage.getItem("theme") as SettingsFormValues["themePreference"] | null)
          : null
      form.reset({
        autoExplainOnPageChange: prefs?.auto_explain_on_page_change ?? true,
        deduplicateDefault: prefs?.default_deduplicate_flashcards ?? false,
        learningStyle: prefs?.learning_style || "linear",
        agentPersona: prefs?.agent_persona || "buddy",
        themePreference: prefs?.theme_preference || savedTheme || "system",
      })
    }
  }, [prefs, form])

  const { mutate: savePrefMutation, isPending: isSaving } = useMutation({
    mutationFn: async ({ key, value }: { key: keyof UserPreferences, value: unknown }) => {
      if (!userData?.id) throw new Error("Not logged in")
      const userId = userData.id
      
      const { data: existing } = await supabase
        .from("user_preferences")
        .select("id")
        .eq("user_id", userId)
        .single()

      if (existing) {
        const { error } = await supabase
          .from("user_preferences")
          .update({ [key]: value })
          .eq("user_id", userId)
        if (error) throw error
      } else {
        const { error } = await supabase
          .from("user_preferences")
          .insert({
            user_id: userId,
            [key]: value,
          })
        if (error) throw error
      }
      return { key, value }
    },
    onSuccess: () => {
      toast.success("Einstellung gespeichert")
      queryClient.invalidateQueries({ queryKey: ['user_preferences', userData?.id] })
    },
    onError: (err) => {
      console.error("Error saving preference:", err)
      toast.error("Fehler beim Speichern")
    }
  })

  const savePreference = async (key: keyof UserPreferences, value: unknown) => {
    savePrefMutation({ key, value })
  }

  const isLoading = isUserLoading || isPrefsLoading

  const syncAutoExplainPreference = async (checked: boolean) => {
    localStorage.setItem("auto_explain_on_page_change", String(checked))
    window.dispatchEvent(
      new CustomEvent("autoExplainSettingChanged", { detail: checked })
    )
    await savePreference("auto_explain_on_page_change", checked)
  }

  const syncThemePreference = async (value: SettingsFormValues["themePreference"]) => {
    localStorage.setItem("theme", value)

    const root = document.documentElement
    if (value === "dark") {
      root.classList.add("dark")
    } else if (value === "light") {
      root.classList.remove("dark")
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      root.classList.add("dark")
    } else {
      root.classList.remove("dark")
    }

    await savePreference("theme_preference", value)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeSettings()}>
      <DialogContent className="z-[60] max-h-[85vh] overflow-y-auto bg-white sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            Allgemeine Einstellungen
          </DialogTitle>
          <DialogDescription>
            Passen Sie Ihre Lerneinstellungen und Praeferenzen an.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <Form {...form}>
            <form className="space-y-6 py-4">
              <FormField
                control={form.control}
                name="autoExplainOnPageChange"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between gap-4 rounded-lg border p-4">
                    <div className="space-y-1">
                      <FormLabel className="cursor-pointer">Automatische Erklaerung beim Seitenwechsel</FormLabel>
                      <FormDescription>
                        Der KI-Tutor erklaert automatisch den Inhalt jeder neuen Seite.
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        id="auto-explain"
                        checked={field.value}
                        onCheckedChange={(checked) => {
                          field.onChange(checked)
                          void syncAutoExplainPreference(checked)
                        }}
                        disabled={isSaving}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Separator />

              <FormField
                control={form.control}
                name="deduplicateDefault"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between gap-4 rounded-lg border p-4">
                    <div className="space-y-1">
                      <FormLabel className="cursor-pointer">Karteikarten-Deduplizierung</FormLabel>
                      <FormDescription>
                        Bei neuen Kursen werden Duplikate standardmaessig entfernt.
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        id="deduplicate-default"
                        checked={field.value}
                        onCheckedChange={(checked) => {
                          field.onChange(checked)
                          void savePreference("default_deduplicate_flashcards", checked)
                        }}
                        disabled={isSaving}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Separator />

              <FormField
                control={form.control}
                name="learningStyle"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lernstil</FormLabel>
                    <FormDescription>
                      Wie moechten Sie Lerninhalte praesentiert bekommen?
                    </FormDescription>
                    <Select
                      value={field.value}
                      onValueChange={(value: SettingsFormValues["learningStyle"]) => {
                        field.onChange(value)
                        void savePreference("learning_style", value)
                      }}
                      disabled={isSaving}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="z-[70] bg-white">
                        <SelectItem value="linear">Linear</SelectItem>
                        <SelectItem value="iterative">Iterativ</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Separator />

              <FormField
                control={form.control}
                name="agentPersona"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tutor-Persoenlichkeit</FormLabel>
                    <FormDescription>
                      Wie soll Ihr KI-Tutor mit Ihnen kommunizieren?
                    </FormDescription>
                    <Select
                      value={field.value}
                      onValueChange={(value: SettingsFormValues["agentPersona"]) => {
                        field.onChange(value)
                        void savePreference("agent_persona", value)
                      }}
                      disabled={isSaving}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="z-[70] bg-white">
                        <SelectItem value="strict">Streng</SelectItem>
                        <SelectItem value="humorous">Humorvoll</SelectItem>
                        <SelectItem value="buddy">Freundlich</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Separator />

              <FormField
                control={form.control}
                name="themePreference"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Erscheinungsbild</FormLabel>
                    <FormDescription>
                      Waehlen Sie Ihr bevorzugtes Farbschema.
                    </FormDescription>
                    <Select
                      value={field.value}
                      onValueChange={(value: SettingsFormValues["themePreference"]) => {
                        field.onChange(value)
                        void syncThemePreference(value)
                      }}
                      disabled={isSaving}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="z-[70] bg-white">
                        <SelectItem value="light">
                          <div className="flex items-center gap-2">
                            <Sun className="h-4 w-4" />
                            <span>Hell</span>
                          </div>
                        </SelectItem>
                        <SelectItem value="dark">
                          <div className="flex items-center gap-2">
                            <Moon className="h-4 w-4" />
                            <span>Dunkel</span>
                          </div>
                        </SelectItem>
                        <SelectItem value="system">
                          <div className="flex items-center gap-2">
                            <Monitor className="h-4 w-4" />
                            <span>System</span>
                          </div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="flex justify-end">
                <Button type="button" variant="outline" onClick={closeSettings} disabled={isSaving}>
                  Schliessen
                </Button>
              </div>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  )
}
