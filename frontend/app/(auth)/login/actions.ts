'use server'

import { createClient } from '@/lib/supabase/server'
import { getSiteUrl } from '@/lib/public-env'
import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

export async function signInWithEmailPassword(formData: FormData) {
  const supabase = await createClient()

  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) {
    return {
      error: 'Email and password are required',
    }
  }

  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    return {
      error: error.message,
    }
  }

  revalidatePath('/', 'layout')
  redirect('/dashboard')
}

export async function signInWithGoogle() {
  const supabase = await createClient()

  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${getSiteUrl()}/auth/callback`,
    },
  })

  if (error) {
    return {
      error: error.message,
    }
  }

  if (data.url) {
    redirect(data.url)
  }

  return {
    error: 'Failed to initiate Google OAuth',
  }
}

export async function signOut() {
  const supabase = await createClient()
  
  const { error } = await supabase.auth.signOut()
  
  if (error) {
    return {
      error: error.message,
    }
  }
  
  revalidatePath('/', 'layout')
  redirect('/login')
}
