import { createBrowserClient } from '@supabase/ssr'
import { getPublicSupabaseAnonKey, getPublicSupabaseUrl } from '@/lib/public-env'

export function createClient() {
  const supabaseUrl = getPublicSupabaseUrl()
  const supabaseAnonKey = getPublicSupabaseAnonKey()

  return createBrowserClient(supabaseUrl, supabaseAnonKey)
}
