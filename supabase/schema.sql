-- ============================================================
--  GTA PickleCourts — Coach Directory schema
--  Run this in the Supabase SQL Editor (one time).
-- ============================================================

create table if not exists public.coaches (
  id                 uuid primary key default gen_random_uuid(),
  created_at         timestamptz not null default now(),
  name               text not null,
  email              text not null,
  phone              text,
  city               text not null,          -- home-base city
  lat                double precision not null,
  lng                double precision not null,
  travel_distance_km integer not null default 10,  -- how far they'll travel to teach
  skill_levels       text[]  not null default '{}', -- e.g. {Beginner,Intermediate,Advanced,Junior}
  years_experience   integer,
  hourly_rate        numeric,                 -- CAD / hour
  certifications     text,                    -- e.g. 'PPR, IPTPA'
  bio                text
);

-- Fast filtering / sorting
create index if not exists coaches_created_at_idx on public.coaches (created_at desc);
create index if not exists coaches_city_idx        on public.coaches (city);

-- ------------------------------------------------------------
--  Row Level Security
--  Public directory: anyone may read, anyone may sign up.
--  (Updates / deletes are NOT granted to anonymous users.)
-- ------------------------------------------------------------
alter table public.coaches enable row level security;

drop policy if exists "Public can read coaches" on public.coaches;
create policy "Public can read coaches"
  on public.coaches
  for select
  using (true);

drop policy if exists "Anyone can sign up as a coach" on public.coaches;
create policy "Anyone can sign up as a coach"
  on public.coaches
  for insert
  with check (true);

-- NOTE: Because signup is open to the public, consider adding
-- moderation (an `approved` boolean defaulting to false, plus a
-- policy `using (approved)` on select) and/or a CAPTCHA before
-- promoting this to production to prevent spam entries.
