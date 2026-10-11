import { createClient } from '@supabase/supabase-js';

export const SUPABASE_URL = 'https://eziigoiirqdsgimfkquv.supabase.co';
export const SUPABASE_ANON_KEY = 'sb_publishable_fDc46mh4MukSCabbBpeVMA_KqtWdOee';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
