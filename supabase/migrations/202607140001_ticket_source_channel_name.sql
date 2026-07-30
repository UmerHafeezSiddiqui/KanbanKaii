alter table public.tickets
add column if not exists source_channel_name text
check (
    source_channel_name is null
    or char_length(btrim(source_channel_name)) between 1 and 255
);
