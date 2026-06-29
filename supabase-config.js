/* ============================================================
   Supabase configuration for the Coach Directory
   ------------------------------------------------------------
   1. Create a free project at https://supabase.com
   2. In the dashboard go to: Project Settings → API
   3. Copy the "Project URL" and the "anon / public" API key
      into the values below.
   4. Run the SQL in  supabase/schema.sql  using the
      Supabase SQL Editor to create the `coaches` table.

   The anon key is SAFE to expose in client-side code — access is
   protected by the Row Level Security policies in schema.sql.

   Until these values are filled in, the Coach Directory runs in
   "Demo mode" and stores signups only in this browser (localStorage).
   ============================================================ */
window.SUPABASE_CONFIG = {
  url: '',      // e.g. 'https://abcdefgh.supabase.co'
  anonKey: ''   // e.g. 'eyJhbGciOi...'
};
