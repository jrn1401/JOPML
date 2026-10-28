-- Veröffentlichen aus dem Launcher: Nur Konten in jopml_admins dürfen im Bucket "releases" schreiben.
-- Lesen bleibt öffentlich (Bucket public). Die Admin-Liste ist für Clients unsichtbar (RLS, keine Policies).
-- Admin eintragen (einmalig, als Projektbetreiber im SQL-Editor):
--   insert into public.jopml_admins (user_id, note) select id, 'owner' from auth.users where email = '<google-mail>';
create table if not exists public.jopml_admins (
  user_id uuid primary key references auth.users (id) on delete cascade,
  note text,
  created_at timestamptz not null default now()
);
alter table public.jopml_admins enable row level security;
revoke all on public.jopml_admins from anon, authenticated, public;

create or replace function public.jopml_is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.jopml_admins where user_id = auth.uid())
$$;
revoke all on function public.jopml_is_admin() from public, anon;
grant execute on function public.jopml_is_admin() to authenticated;

drop policy if exists "jopml admin select releases" on storage.objects;
drop policy if exists "jopml admin insert releases" on storage.objects;
drop policy if exists "jopml admin update releases" on storage.objects;
drop policy if exists "jopml admin delete releases" on storage.objects;
create policy "jopml admin select releases" on storage.objects for select to authenticated
  using (bucket_id = 'releases' and public.jopml_is_admin());
create policy "jopml admin insert releases" on storage.objects for insert to authenticated
  with check (bucket_id = 'releases' and public.jopml_is_admin());
create policy "jopml admin update releases" on storage.objects for update to authenticated
  using (bucket_id = 'releases' and public.jopml_is_admin()) with check (bucket_id = 'releases' and public.jopml_is_admin());
create policy "jopml admin delete releases" on storage.objects for delete to authenticated
  using (bucket_id = 'releases' and public.jopml_is_admin());
