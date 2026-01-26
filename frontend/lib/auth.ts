import { createClient } from './supabase/server'
import { redirect } from 'next/navigation'

/**
 * Get the current session (server-side)
 * @returns Session object or null if not authenticated
 */
export async function getSession() {
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session
}

/**
 * Require authentication - redirects to login if not authenticated
 * @returns Session object if authenticated
 */
export async function requireAuth() {
  const session = await getSession()
  if (!session) {
    redirect('/login')
  }
  return session
}

/**
 * Get the current user (server-side)
 * @returns User object or null if not authenticated
 */
export async function getUser() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  return user
}
