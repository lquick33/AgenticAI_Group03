import { createServerClient } from '@supabase/ssr'
import { getPublicSupabaseAnonKey, getPublicSupabaseUrl } from '@/lib/public-env'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  const supabaseUrl = getPublicSupabaseUrl()
  const supabaseAnonKey = getPublicSupabaseAnonKey()

  return createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing
            // user sessions.
          }
        },
      },
    }
  )
}
