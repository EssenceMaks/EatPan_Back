from __future__ import annotations

from django.conf import settings
from django.db import transaction

from .models import SyncOutbox


def outbox_enqueue(*, entity_type: str, entity_uuid, op: str, payload: dict | None = None) -> None:
    node_id = getattr(settings, 'NODE_ID', 'local_a')
    payload = payload or {}

    def _create() -> None:
        SyncOutbox.objects.create(
            entity_type=entity_type,
            entity_uuid=entity_uuid,
            op=op,
            payload=payload,
            node_id=node_id,
        )

    transaction.on_commit(_create)
