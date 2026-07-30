begin;

create or replace function public.list_my_organization_invitations()
returns table (
    id uuid,
    organization_id uuid,
    organization_name text,
    organization_slug text,
    default_role text,
    created_by uuid,
    created_at timestamptz,
    expires_at timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_email text;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select lower(account.email) into v_email
    from auth.users account
    where account.id = v_user_id
      and account.email_confirmed_at is not null;

    if v_email is null then
        raise exception 'A verified email address is required' using errcode = '42501';
    end if;

    return query
    select
        invite.id,
        invite.organization_id,
        organization.name,
        organization.slug,
        invite.default_role,
        invite.created_by,
        invite.created_at,
        invite.expires_at
    from public.organization_invites invite
    join public.organizations organization
      on organization.id = invite.organization_id
    where invite.intended_email = v_email
      and invite.accepted_at is null
      and invite.declined_at is null
      and invite.revoked_at is null
      and invite.expires_at > now()
      and not exists (
          select 1
          from public.organization_members member
          where member.organization_id = invite.organization_id
            and member.user_id = v_user_id
      )
    order by invite.created_at desc;
end;
$$;

revoke all on function public.list_my_organization_invitations() from public, anon;
grant execute on function public.list_my_organization_invitations() to authenticated;

notify pgrst, 'reload schema';

commit;
