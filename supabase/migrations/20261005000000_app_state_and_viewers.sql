-- Indy's Year: cloud backup + sync. One JSON state blob per user, plus a share list.

create table public.app_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  state jsonb not null,
  updated_at timestamptz not null default now()
);

create table public.viewers (
  owner_id uuid references auth.users(id) on delete cascade,
  viewer_email text not null,
  primary key (owner_id, viewer_email)
);

alter table public.app_state enable row level security;
alter table public.viewers enable row level security;

-- app_state: the owner has full access to their own row
create policy "owner select" on public.app_state for select to authenticated
  using (user_id = (select auth.uid()));
create policy "owner insert" on public.app_state for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy "owner update" on public.app_state for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "owner delete" on public.app_state for delete to authenticated
  using (user_id = (select auth.uid()));

-- app_state: people the owner added as viewers can read (never write)
create policy "viewer select" on public.app_state for select to authenticated
  using (exists (
    select 1 from public.viewers v
    where v.owner_id = app_state.user_id
      and v.viewer_email = (select auth.jwt()->>'email')
  ));

-- viewers: the owner manages their own share list
create policy "owner all" on public.viewers for all to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));

-- viewers: a viewer may see the rows that name them. Without this the "viewer select"
-- policy above cannot see the viewers table (RLS applies inside the subquery) and sharing would never work.
create policy "viewer sees own invite" on public.viewers for select to authenticated
  using (viewer_email = (select auth.jwt()->>'email'));
