begin;

create or replace function public.create_organization_board(
    p_organization_id uuid,
    p_name text,
    p_slug text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_role text;
    v_board_id uuid;
    v_name text := btrim(p_name);
    v_slug text := lower(btrim(p_slug));
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    v_role := public.current_organization_role(p_organization_id);
    if coalesce(v_role, '') <> 'OWNER' then
        raise exception 'Only an organization manager can create boards'
            using errcode = '42501';
    end if;

    if char_length(v_name) not between 2 and 100
       or char_length(v_slug) not between 2 and 63
       or v_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' then
        raise exception 'Board name or slug is invalid' using errcode = '22023';
    end if;

    insert into public.organization_boards(
        organization_id,
        name,
        slug,
        created_by
    ) values (
        p_organization_id,
        v_name,
        v_slug,
        v_user_id
    )
    returning id into v_board_id;

    insert into public.organization_board_members(
        board_id,
        organization_id,
        user_id,
        role,
        added_by
    ) values (
        v_board_id,
        p_organization_id,
        v_user_id,
        'MANAGER',
        v_user_id
    );

    return v_board_id;
end;
$$;

revoke all on function public.create_organization_board(uuid, text, text)
from public, anon;
grant execute on function public.create_organization_board(uuid, text, text)
to authenticated;

commit;
