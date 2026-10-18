from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase
from uuid import uuid4

from app.organizations.invite_store import OrganizationInviteStore, RedisInviteDraft


class MemoryRedis:
    """Redis subset with a controllable clock for invitation expiry tests."""
    def __init__(self):
        self.now = 0
        self.values = {}
        self.expirations = {}

    def _value(self, key):
        if self.expirations.get(key, float('inf')) <= self.now:
            self.values.pop(key, None)
            self.expirations.pop(key, None)
        return self.values.get(key)

    async def get(self, key):
        return self._value(key)

    async def smembers(self, key):
        return self._value(key) or set()

    def pipeline(self, transaction=True):
        return MemoryPipeline(self)


class MemoryPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __getattr__(self, name):
        def enqueue(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return enqueue

    async def execute(self):
        results = []
        for name, args, options in self.commands:
            key, value = args
            current = self.redis._value(key)
            if name == 'set':
                allowed = not options.get('nx') or current is None
                if allowed:
                    self.redis.values[key] = value
                    self.redis.expirations[key] = self.redis.now + options['ex']
                results.append(True if allowed else None)
            elif name == 'sadd':
                self.redis.values.setdefault(key, set()).add(value)
                results.append(1)
            elif name == 'expire':
                deadline = self.redis.now + value
                previous = self.redis.expirations.get(key)
                allowed = current is not None
                if options.get('nx'):
                    allowed = allowed and previous is None
                if options.get('gt'):
                    allowed = allowed and previous is not None and deadline > previous
                if allowed:
                    self.redis.expirations[key] = deadline
                results.append(allowed)
            else:
                raise AssertionError(f'Unexpected Redis command: {name}')
        self.commands.clear()
        return results


class InviteIndexExpiryTests(IsolatedAsyncioTestCase):
    async def test_short_invitation_does_not_hide_long_email_invitation(self):
        redis = MemoryRedis()
        store = OrganizationInviteStore(redis)
        async def create(hours, email, org):
            return await store.create(RedisInviteDraft(
                organization_id=org, organization_name='Team', organization_slug='team',
                intended_email=email, default_role='MEMBER', created_by=uuid4(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
                token_hash=str(uuid4()),
            ))
        long_org = uuid4()
        long = await create(168, 'member@example.com', long_org)
        await create(1, 'member@example.com', uuid4())
        await create(1, 'other@example.com', long_org)
        redis.now += 3601
        self.assertEqual([x.id for x in await store.list_for_email('member@example.com')], [long.id])
        self.assertEqual([x.id for x in await store.list_for_organization(long_org)], [long.id])

    async def test_long_invitation_extends_existing_email_and_organization_indexes(self):
        redis = MemoryRedis()
        store = OrganizationInviteStore(redis)
        org = uuid4()
        for hours, email, organization in [(1, 'member@example.com', org), (168, 'member@example.com', uuid4()), (168, 'other@example.com', org)]:
            await store.create(RedisInviteDraft(
                organization_id=organization, organization_name='Team', organization_slug='team',
                intended_email=email, default_role='MEMBER', created_by=uuid4(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=hours), token_hash=str(uuid4()),
            ))
        redis.now += 3601
        self.assertEqual(len(await store.list_for_email('member@example.com')), 1)
        self.assertEqual(len(await store.list_for_organization(org)), 1)
