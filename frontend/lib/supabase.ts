import { createClient } from '@supabase/supabase-js'
import { getPublicSupabaseAnonKey, getPublicSupabaseUrl } from './public-env'

const supabaseUrl = getPublicSupabaseUrl()
const supabaseAnonKey = getPublicSupabaseAnonKey()

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
