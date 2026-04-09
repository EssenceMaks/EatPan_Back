import pytest
from django.urls import reverse
from rest_framework.test import APIRequestFactory
from eatpan_core.health import health

@pytest.fixture
def factory():
    return APIRequestFactory()

def test_health_check_ok(factory, mocker):
    url = reverse("health")
    
    # Mocking database connection to succeed
    mocker.patch("eatpan_core.health.connections")
    
    request = factory.get(url)
    response = health(request)
    import json
    data = json.loads(response.content)
    
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert "node" in data
    assert "latency_ms" in data

def test_health_check_degraded(factory, mocker):
    url = reverse("health")
    
    # Mocking database connection to fail
    mocker.patch("eatpan_core.health.connections.__getitem__", side_effect=Exception("DB Error"))
    
    request = factory.get(url)
    response = health(request)
    import json
    data = json.loads(response.content)
    
    assert response.status_code == 503
    assert data["status"] == "degraded"
    assert data["db"] == "error"

