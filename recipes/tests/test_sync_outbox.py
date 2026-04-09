import pytest
import uuid
from django.db import transaction
from recipes.sync_outbox import outbox_enqueue
from recipes.models import SyncOutbox

@pytest.mark.django_db(transaction=True)
def test_outbox_enqueue():
    test_uuid = uuid.uuid4()
    
    assert SyncOutbox.objects.count() == 0
    
    # outbox_enqueue uses transaction.on_commit
    with transaction.atomic():
        outbox_enqueue(
            entity_type='recipe',
            entity_uuid=test_uuid,
            op='upsert',
            payload={'test': 'data'}
        )
    
    assert SyncOutbox.objects.count() == 1
    outbox = SyncOutbox.objects.first()
    assert outbox.entity_type == 'recipe'
    assert outbox.entity_uuid == test_uuid
    assert outbox.op == 'upsert'
    assert outbox.payload == {'test': 'data'}
    assert outbox.node_id == 'local_a'
