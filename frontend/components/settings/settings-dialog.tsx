"use client"

import { useState, useEffect } from "react"
import { Loader2, Settings2, Link2, Moon, Sun, Monitor, X, CheckCircle2, LogOut } from "lucide-react"
import { toast } from "sonner"
import * as DialogPrimitive from "@radix-ui/react-dialog"

import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogPortal,
  DialogOverlay,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { createClient } from "@/lib/supabase/client"
import { useSettings } from "./settings-context"

interface UserPreferences {
  id?: string
  user_id: string
  learning_style: "linear" | "iterative"
  agent_persona: "strict" | "humorous" | "buddy"
  default_deduplicate_flashcards?: boolean
  theme_preference?: "light" | "dark" | "system"
  ankiweb_username?: string | null
  auto_explain_on_page_change?: boolean
}

export function SettingsDialog() {
  const { isOpen, closeSettings } = useSettings()
  const supabase = createClient()

  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [userId, setUserId] = useState<string | null>(null)

  // Settings state
  const [deduplicateDefault, setDeduplicateDefault] = useState(false)
  const [learningStyle, setLearningStyle] = useState<"linear" | "iterative">("linear")
  const [agentPersona, setAgentPersona] = useState<"strict" | "humorous" | "buddy">("buddy")
  const [themePreference, setThemePreference] = useState<"light" | "dark" | "system">("system")
  const [ankiWebUsername, setAnkiWebUsername] = useState<string>("")
  const [autoExplainOnPageChange, setAutoExplainOnPageChange] = useState(true)

  // AnkiWeb login state - start with not_logged_in to avoid loading spinner
  const [ankiWebStatus, setAnkiWebStatus] = useState<"loading" | "logged_in" | "not_logged_in" | "not_connected" | "error">("not_logged_in")
  const [ankiWebEmail, setAnkiWebEmail] = useState("")
  const [ankiWebPassword, setAnkiWebPassword] = useState("")
  const [isAnkiWebLoggingIn, setIsAnkiWebLoggingIn] = useState(false)
  const [ankiWebError, setAnkiWebError] = useState<string | null>(null)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  // Load user preferences when dialog opens
  useEffect(() => {
    if (isOpen) {
      loadPreferences()
      loadAnkiWebStatus()
    }
  }, [isOpen])

  const loadAnkiWebStatus = async () => {
    // Background verification - don't show loading spinner
    // UI already shows cached state from preferences
    try {
      const response = await fetch(`${API_URL}/api/anki/login-status`)
      if (response.ok) {
        const data = await response.json()
        // Only update if status actually changed
        setAnkiWebStatus(data.status)
        if (data.username) {
          setAnkiWebUsername(data.username)
        } else if (data.status === "not_logged_in") {
          setAnkiWebUsername("")
        }
      }
      // Don't update UI on error - keep showing cached state
    } catch {
      // Silently fail - keep showing cached state
      // User will see error when they try to interact
    }
  }

  const handleAnkiWebLogin = async () => {
    if (!ankiWebEmail || !ankiWebPassword) {
      setAnkiWebError("Bitte E-Mail und Passwort eingeben")
      return
    }

    setIsAnkiWebLoggingIn(true)
    setAnkiWebError(null)

    try {
      const response = await fetch(`${API_URL}/api/anki/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: ankiWebEmail,
          password: ankiWebPassword
        })
      })

      const data = await response.json()

      if (response.ok) {
        setAnkiWebStatus("logged_in")
        setAnkiWebUsername(data.username || ankiWebEmail)
        setAnkiWebEmail("")
        setAnkiWebPassword("")
        toast.success("Erfolgreich mit AnkiWeb verbunden")
        // Save username to user preferences
        await savePreference("ankiweb_username", data.username || ankiWebEmail)
      } else if (response.status === 429) {
        // Rate limited
        setAnkiWebError("Zu viele Anmeldeversuche. Bitte versuchen Sie es in 15 Minuten erneut.")
      } else if (response.status === 501) {
        // Addon not loaded - need to restart container
        setAnkiWebError("Bitte starten Sie den Anki Docker-Container neu, um die Login-Funktion zu aktivieren.")
      } else if (response.status === 401) {
        setAnkiWebError("Ungültige E-Mail oder Passwort")
      } else {
        setAnkiWebError(data.detail || "Anmeldung fehlgeschlagen")
      }
    } catch (err) {
      setAnkiWebError("Verbindung zum Server fehlgeschlagen")
    } finally {
      setIsAnkiWebLoggingIn(false)
    }
  }

  const handleAnkiWebLogout = async () => {
    try {
      const response = await fetch(`${API_URL}/api/anki/logout`, {
        method: "POST"
      })

      if (response.ok) {
        setAnkiWebStatus("not_logged_in")
        setAnkiWebUsername("")
        toast.success("Von AnkiWeb abgemeldet")
        await savePreference("ankiweb_username", null)
      } else {
        const data = await response.json()
        toast.error(data.detail || "Abmeldung fehlgeschlagen")
      }
    } catch {
      toast.error("Verbindung zum Server fehlgeschlagen")
    }
  }

  const loadPreferences = async () => {
    setIsLoading(true)
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        toast.error("Nicht angemeldet")
        closeSettings()
        return
      }

      setUserId(user.id)

      // Fetch user preferences
      const { data: prefs, error } = await supabase
        .from("user_preferences")
        .select("*")
        .eq("user_id", user.id)
        .single()

      if (error && error.code !== "PGRST116") {
        // PGRST116 = no rows returned
        throw error
      }

      if (prefs) {
        setLearningStyle(prefs.learning_style || "linear")
        setAgentPersona(prefs.agent_persona || "buddy")
        setDeduplicateDefault(prefs.default_deduplicate_flashcards ?? false)
        setThemePreference(prefs.theme_preference || "system")
        setAnkiWebUsername(prefs.ankiweb_username || "")
        setAutoExplainOnPageChange(prefs.auto_explain_on_page_change ?? true)
        
        // Use cached username to show instant UI (no loading spinner)
        if (prefs.ankiweb_username) {
          setAnkiWebStatus("logged_in")
        } else {
          setAnkiWebStatus("not_logged_in")
        }
      }

      // Load theme from localStorage as fallback
      const savedTheme = localStorage.getItem("theme") as "light" | "dark" | "system" | null
      if (savedTheme && !prefs?.theme_preference) {
        setThemePreference(savedTheme)
      }
    } catch (err) {
      console.error("Error loading preferences:", err)
      toast.error("Fehler beim Laden der Einstellungen")
    } finally {
      setIsLoading(false)
    }
  }

  const savePreference = async (key: string, value: unknown) => {
    if (!userId) return

    setIsSaving(true)
    try {
      // Check if preferences exist
      const { data: existing } = await supabase
        .from("user_preferences")
        .select("id")
        .eq("user_id", userId)
        .single()

      if (existing) {
        // Update existing
        const { error } = await supabase
          .from("user_preferences")
          .update({ [key]: value })
          .eq("user_id", userId)

        if (error) throw error
      } else {
        // Create new preferences
        const { error } = await supabase
          .from("user_preferences")
          .insert({
            user_id: userId,
            [key]: value,
          })

        if (error) throw error
      }

      toast.success("Einstellung gespeichert")
    } catch (err) {
      console.error("Error saving preference:", err)
      toast.error("Fehler beim Speichern")
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeduplicateChange = async (checked: boolean) => {
    setDeduplicateDefault(checked)
    await savePreference("default_deduplicate_flashcards", checked)
  }

  const handleAutoExplainChange = async (checked: boolean) => {
    setAutoExplainOnPageChange(checked)
    // Also update localStorage so active study sessions can react to the change
    localStorage.setItem("auto_explain_on_page_change", String(checked))
    // Dispatch custom event for same-tab listeners (storage event only fires cross-tab)
    window.dispatchEvent(new CustomEvent('autoExplainSettingChanged', { detail: checked }))
    await savePreference("auto_explain_on_page_change", checked)
  }

  const handleLearningStyleChange = async (value: "linear" | "iterative") => {
    setLearningStyle(value)
    await savePreference("learning_style", value)
  }

  const handleAgentPersonaChange = async (value: "strict" | "humorous" | "buddy") => {
    setAgentPersona(value)
    await savePreference("agent_persona", value)
  }

  const handleThemeChange = async (value: "light" | "dark" | "system") => {
    setThemePreference(value)
    localStorage.setItem("theme", value)
    
    // Apply theme immediately
    const root = document.documentElement
    if (value === "dark") {
      root.classList.add("dark")
    } else if (value === "light") {
      root.classList.remove("dark")
    } else {
      // System preference
      if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        root.classList.add("dark")
      } else {
        root.classList.remove("dark")
      }
    }

    await savePreference("theme_preference", value)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeSettings()}>
      <DialogPortal>
        <DialogOverlay className="z-[60]" />
        <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-[60] grid w-full max-w-[550px] translate-x-[-50%] translate-y-[-50%] gap-4 border bg-white p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg max-h-[85vh] overflow-y-auto">
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground cursor-pointer">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              Allgemeine Einstellungen
            </DialogTitle>
            <DialogDescription>
              Passen Sie Ihre Lerneinstellungen und Präferenzen an.
            </DialogDescription>
          </DialogHeader>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-6 py-4">
            {/* Auto-explain on page change */}
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-0.5">
                <Label
                  htmlFor="auto-explain"
                  className="text-sm font-medium cursor-pointer"
                >
                  Automatische Erklärung beim Seitenwechsel
                </Label>
                <p className="text-xs text-muted-foreground">
                  KI-Tutor erklärt automatisch den Inhalt jeder neuen Seite
                </p>
              </div>
              <Switch
                id="auto-explain"
                checked={autoExplainOnPageChange}
                onCheckedChange={handleAutoExplainChange}
                disabled={isSaving}
              />
            </div>

            <Separator />

            {/* Deduplication Default */}
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-0.5">
                <Label
                  htmlFor="deduplicate-default"
                  className="text-sm font-medium cursor-pointer"
                >
                  Karteikarten-Deduplizierung
                </Label>
                <p className="text-xs text-muted-foreground">
                  Bei neuen Kursen automatisch Duplikate entfernen
                </p>
              </div>
              <Switch
                id="deduplicate-default"
                checked={deduplicateDefault}
                onCheckedChange={handleDeduplicateChange}
                disabled={isSaving}
              />
            </div>

            <Separator />

            {/* Learning Style */}
            <div className="space-y-2">
              <Label htmlFor="learning-style" className="text-sm font-medium">
                Lernstil
              </Label>
              <p className="text-xs text-muted-foreground mb-2">
                Wie möchten Sie Lerninhalte präsentiert bekommen?
              </p>
              <Select
                value={learningStyle}
                onValueChange={(value) => handleLearningStyleChange(value as "linear" | "iterative")}
                disabled={isSaving}
              >
                <SelectTrigger id="learning-style">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="z-[70] bg-white">
                  <SelectItem value="linear">
                    <div className="flex flex-col">
                      <span>Linear</span>
                      <span className="text-xs text-muted-foreground">
                        Schritt für Schritt durch das Material
                      </span>
                    </div>
                  </SelectItem>
                  <SelectItem value="iterative">
                    <div className="flex flex-col">
                      <span>Iterativ</span>
                      <span className="text-xs text-muted-foreground">
                        Wiederholende Vertiefung der Themen
                      </span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Agent Persona */}
            <div className="space-y-2">
              <Label htmlFor="agent-persona" className="text-sm font-medium">
                Tutor-Persönlichkeit
              </Label>
              <p className="text-xs text-muted-foreground mb-2">
                Wie soll Ihr KI-Tutor mit Ihnen kommunizieren?
              </p>
              <Select
                value={agentPersona}
                onValueChange={(value) => handleAgentPersonaChange(value as "strict" | "humorous" | "buddy")}
                disabled={isSaving}
              >
                <SelectTrigger id="agent-persona">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="z-[70] bg-white">
                  <SelectItem value="strict">
                    <div className="flex flex-col">
                      <span>Streng</span>
                      <span className="text-xs text-muted-foreground">
                        Fokussiert und direkt
                      </span>
                    </div>
                  </SelectItem>
                  <SelectItem value="humorous">
                    <div className="flex flex-col">
                      <span>Humorvoll</span>
                      <span className="text-xs text-muted-foreground">
                        Mit Witz und Charme
                      </span>
                    </div>
                  </SelectItem>
                  <SelectItem value="buddy">
                    <div className="flex flex-col">
                      <span>Freundlich</span>
                      <span className="text-xs text-muted-foreground">
                        Wie ein guter Freund
                      </span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* Theme */}
            <div className="space-y-2">
              <Label htmlFor="theme" className="text-sm font-medium">
                Erscheinungsbild
              </Label>
              <p className="text-xs text-muted-foreground mb-2">
                Wählen Sie Ihr bevorzugtes Farbschema
              </p>
              <Select
                value={themePreference}
                onValueChange={(value) => handleThemeChange(value as "light" | "dark" | "system")}
                disabled={isSaving}
              >
                <SelectTrigger id="theme">
                  <SelectValue />
                </SelectTrigger>
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
            </div>

            <Separator />

            {/* AnkiWeb Connection */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Link2 className="h-4 w-4 text-muted-foreground" />
                <Label className="text-sm font-medium">AnkiWeb Verbindung</Label>
              </div>
              <p className="text-xs text-muted-foreground">
                Verbinden Sie Ihr AnkiWeb-Konto, um Karteikarten automatisch zu synchronisieren.
              </p>
              
              {ankiWebStatus === "loading" ? (
                <div className="rounded-lg border p-4 flex items-center justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : ankiWebStatus === "logged_in" ? (
                <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                      <div>
                        <p className="text-sm font-medium text-green-800">Verbunden</p>
                        <p className="text-xs text-green-600">{ankiWebUsername}</p>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={handleAnkiWebLogout}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <LogOut className="h-4 w-4 mr-1" />
                      Abmelden
                    </Button>
                  </div>
                </div>
              ) : ankiWebStatus === "not_connected" ? (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
                  <p className="text-sm text-yellow-800">
                    Anki-Service ist nicht erreichbar. Bitte starten Sie den Docker-Container.
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="ankiweb-email" className="text-xs">
                      AnkiWeb E-Mail
                    </Label>
                    <Input
                      id="ankiweb-email"
                      type="email"
                      placeholder="ihre@email.com"
                      value={ankiWebEmail}
                      onChange={(e) => setAnkiWebEmail(e.target.value)}
                      disabled={isAnkiWebLoggingIn}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="ankiweb-password" className="text-xs">
                      Passwort
                    </Label>
                    <Input
                      id="ankiweb-password"
                      type="password"
                      placeholder="••••••••"
                      value={ankiWebPassword}
                      onChange={(e) => setAnkiWebPassword(e.target.value)}
                      disabled={isAnkiWebLoggingIn}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleAnkiWebLogin()
                        }
                      }}
                    />
                  </div>
                  {ankiWebError && (
                    <p className="text-xs text-destructive">{ankiWebError}</p>
                  )}
                  <Button 
                    onClick={handleAnkiWebLogin}
                    disabled={isAnkiWebLoggingIn}
                    className="w-full"
                    size="sm"
                  >
                    {isAnkiWebLoggingIn ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Verbinden...
                      </>
                    ) : (
                      <>
                        <Link2 className="h-4 w-4 mr-2" />
                        Mit AnkiWeb verbinden
                      </>
                    )}
                  </Button>
                  <p className="text-xs text-muted-foreground text-center">
                    Noch kein Konto?{" "}
                    <a 
                      href="https://ankiweb.net/account/signup" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Jetzt registrieren
                    </a>
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}
