-- Nur für lokale Tests: Ersatz für die Admin-Tabelle (die echte kommt aus 20261027000000_jopml_admin_publish.sql und braucht Supabase Storage).
create table public.jopml_admins (user_id uuid primary key references auth.users (id) on delete cascade, note text, created_at timestamptz not null default now());
alter table public.jopml_admins enable row level security;
create function public.jopml_is_admin() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.jopml_admins where user_id = auth.uid()) $$;
grant execute on function public.jopml_is_admin() to authenticated;
