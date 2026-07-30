begin;

create table public.user_profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    display_name text not null check (char_length(btrim(display_name)) between 1 and 100),
    job_title text check (job_title is null or char_length(btrim(job_title)) between 1 and 100),
    avatar_url text check (avatar_url is null or char_length(avatar_url) <= 2048),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.sync_user_profile_from_auth()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_display_name text;
    v_job_title text;
    v_avatar_url text;
begin
    v_display_name := coalesce(
        nullif(btrim(new.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(new.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(new.raw_user_meta_data ->> 'name'), ''),
        split_part(coalesce(new.email, 'Member'), '@', 1),
        'Member'
    );
    v_job_title := nullif(btrim(new.raw_user_meta_data ->> 'job_title'), '');
    v_avatar_url := coalesce(
        nullif(btrim(new.raw_user_meta_data ->> 'avatar_url'), ''),
        nullif(btrim(new.raw_user_meta_data ->> 'picture'), '')
    );

    insert into public.user_profiles(user_id, display_name, job_title, avatar_url)
    values (new.id, left(v_display_name, 100), left(v_job_title, 100), left(v_avatar_url, 2048))
    on conflict (user_id) do update set
        display_name = excluded.display_name,
        job_title = excluded.job_title,
        avatar_url = excluded.avatar_url,
        updated_at = now();

    return new;
end;
$$;

create trigger auth_users_sync_public_profile
after insert or update of raw_user_meta_data on auth.users
for each row execute function public.sync_user_profile_from_auth();

insert into public.user_profiles(user_id, display_name, job_title, avatar_url)
select
    account.id,
    left(coalesce(
        nullif(btrim(account.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(account.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(account.raw_user_meta_data ->> 'name'), ''),
        split_part(coalesce(account.email, 'Member'), '@', 1),
        'Member'
    ), 100),
    left(nullif(btrim(account.raw_user_meta_data ->> 'job_title'), ''), 100),
    left(coalesce(
        nullif(btrim(account.raw_user_meta_data ->> 'avatar_url'), ''),
        nullif(btrim(account.raw_user_meta_data ->> 'picture'), '')
    ), 2048)
from auth.users account
on conflict (user_id) do nothing;

create or replace function public.can_view_user_profile(p_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select p_user_id = (select auth.uid()) or exists (
        select 1
        from public.organization_members viewer
        join public.organization_members target
          on target.organization_id = viewer.organization_id
        where viewer.user_id = (select auth.uid())
          and target.user_id = p_user_id
    );
$$;

create or replace function public.list_organization_members_with_profiles(
    p_organization_id uuid
)
returns table (
    organization_id uuid,
    user_id uuid,
    role text,
    invited_by uuid,
    joined_at timestamptz,
    display_name text,
    job_title text,
    avatar_url text
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;
    if not public.is_organization_member(p_organization_id) then
        raise exception 'Organization membership is required' using errcode = '42501';
    end if;

    return query
    select
        member.organization_id,
        member.user_id,
        member.role,
        member.invited_by,
        member.joined_at,
        profile.display_name,
        profile.job_title,
        profile.avatar_url
    from public.organization_members member
    join public.user_profiles profile on profile.user_id = member.user_id
    where member.organization_id = p_organization_id
    order by member.joined_at;
end;
$$;

alter table public.user_profiles enable row level security;

create policy "Users can view profiles in shared organizations"
on public.user_profiles for select
to authenticated
using (public.can_view_user_profile(user_id));

revoke all on public.user_profiles from anon, authenticated;
grant select on public.user_profiles to authenticated;

revoke all on function public.sync_user_profile_from_auth() from public, anon, authenticated;
revoke all on function public.can_view_user_profile(uuid) from public, anon;
revoke all on function public.list_organization_members_with_profiles(uuid) from public, anon;

grant execute on function public.can_view_user_profile(uuid) to authenticated, service_role;
grant execute on function public.list_organization_members_with_profiles(uuid) to authenticated;

commit;
