const LOCALHOST_ORIGINS = new Set(["localhost", "127.0.0.1"])
const LOCAL_DEV_SUPABASE_URL = "https://vppmtcrfyrtitldmjymh.supabase.co"
const LOCAL_DEV_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_zEDpYANpC6rh3RZOqgaPaQ_BE0v5NTG"

function getPublicEnv(name: string): string | undefined {
  const value = process.env[name]
  if (!value) {
    return undefined
  }

  return value.trim()
}

function isLocalSiteUrl(siteUrl: string | undefined): boolean {
  if (!siteUrl) {
    return false
  }

  try {
    return LOCALHOST_ORIGINS.has(new URL(siteUrl).hostname)
  } catch {
    return false
  }
}

function requirePublicEnv(name: string, message: string): string {
  const value = getPublicEnv(name)
  if (!value) {
    throw new Error(message)
  }
  return value
}

function assertClientSafeSupabaseKey(key: string): string {
  if (key.startsWith("sb_secret_")) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY must use a publishable/anon key, not a secret key."
    )
  }

  return key
}

export function getSiteUrl(): string {
  const siteUrl = getPublicEnv("NEXT_PUBLIC_SITE_URL")
  if (siteUrl) {
    return siteUrl.replace(/\/$/, "")
  }

  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:3000"
  }

  throw new Error(
    "Missing NEXT_PUBLIC_SITE_URL. Set it explicitly for staging and production deployments."
  )
}

export function getApiUrl(): string {
  const apiUrl = getPublicEnv("NEXT_PUBLIC_API_URL")
  if (apiUrl) {
    return apiUrl.replace(/\/$/, "")
  }

  if (
    process.env.NODE_ENV !== "production" ||
    isLocalSiteUrl(getPublicEnv("NEXT_PUBLIC_SITE_URL"))
  ) {
    return "http://localhost:8000"
  }

  throw new Error(
    "Missing NEXT_PUBLIC_API_URL. Set it explicitly for non-local deployments."
  )
}

export function getPublicSupabaseUrl(): string {
  const url = getPublicEnv("NEXT_PUBLIC_SUPABASE_URL")
  if (url) {
    return url
  }

  if (process.env.NODE_ENV !== "production") {
    return LOCAL_DEV_SUPABASE_URL
  }

  return requirePublicEnv(
    "NEXT_PUBLIC_SUPABASE_URL",
    "Missing NEXT_PUBLIC_SUPABASE_URL. Please configure the frontend environment."
  )
}

export function getPublicSupabaseAnonKey(): string {
  const key = getPublicEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
  if (key) {
    return assertClientSafeSupabaseKey(key)
  }

  if (process.env.NODE_ENV !== "production") {
    return LOCAL_DEV_SUPABASE_PUBLISHABLE_KEY
  }

  return assertClientSafeSupabaseKey(
    requirePublicEnv(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY",
      "Missing NEXT_PUBLIC_SUPABASE_ANON_KEY. Please configure the frontend environment."
    )
  )
}
