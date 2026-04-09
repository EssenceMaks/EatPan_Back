import pytest
import jwt
from django.test import RequestFactory
from rest_framework import exceptions
from eatpan_core.authentication import SupabaseJWTAuthentication
from django.contrib.auth.models import User
from django.conf import settings

@pytest.fixture
def auth():
    return SupabaseJWTAuthentication()

@pytest.fixture
def factory():
    return RequestFactory()

def test_no_auth_header(auth, factory):
    request = factory.get('/')
    assert auth.authenticate(request) is None

def test_invalid_auth_header_format(auth, factory):
    request = factory.get('/', HTTP_AUTHORIZATION='Token something')
    assert auth.authenticate(request) is None

def test_expired_token(auth, factory, mocker):
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'HS256'})
    mocker.patch('jwt.decode', side_effect=jwt.ExpiredSignatureError("Expired"))
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    with pytest.raises(exceptions.AuthenticationFailed) as exc:
        auth.authenticate(request)
    assert 'Token Expired' in str(exc.value)

def test_invalid_token(auth, factory, mocker):
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'HS256'})
    mocker.patch('jwt.decode', side_effect=jwt.InvalidTokenError("Invalid"))
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    with pytest.raises(exceptions.AuthenticationFailed) as exc:
        auth.authenticate(request)
    assert 'Invalid Token' in str(exc.value)

def test_unsupported_alg(auth, factory, mocker):
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'RS256'})
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    with pytest.raises(exceptions.AuthenticationFailed) as exc:
        auth.authenticate(request)
    assert 'Unsupported JWT algorithm: RS256' in str(exc.value)

@pytest.mark.django_db
def test_valid_hs256_token(auth, factory, mocker):
    # Mocking decode
    payload = {
        'sub': '123e4567-e89b-12d3-a456-426614174000',
        'email': 'test@test.com',
        'role': 'authenticated'
    }
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'HS256'})
    mocker.patch('jwt.decode', return_value=payload)
    
    # Needs settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    user, token = auth.authenticate(request)
    
    assert user.username == '123e4567-e89b-12d3-a456-426614174000'
    assert user.email == 'test@test.com'
    assert token == 'token'

@pytest.mark.django_db
def test_valid_es256_token(auth, factory, mocker):
    payload = {
        'sub': '123e4567-e89b-12d3-a456-426614174001',
        'email': 'es256@test.com',
        'aud': 'authenticated'
    }
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'ES256'})
    mocker.patch('jwt.decode', return_value=payload)
    
    mock_jwks = mocker.Mock()
    mock_signing_key = mocker.Mock()
    mock_signing_key.key = "public_key"
    mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key
    mocker.patch('eatpan_core.authentication.get_jwks_client', return_value=mock_jwks)
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    user, token = auth.authenticate(request)
    
    assert user.username == '123e4567-e89b-12d3-a456-426614174001'
    assert user.email == 'es256@test.com'
    assert token == 'token'

def test_unauthenticated_role(auth, factory, mocker):
    payload = {
        'sub': '123e4567-e89b-12d3-a456-426614174000',
        'role': 'anon'
    }
    mocker.patch('jwt.get_unverified_header', return_value={'alg': 'HS256'})
    mocker.patch('jwt.decode', return_value=payload)
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    
    settings.SUPABASE_JWT_SECRET = "dummy_secret"
    mocker.patch('django.conf.settings.SUPABASE_JWT_SECRET', "dummy_secret", create=True)
    request = factory.get('/', HTTP_AUTHORIZATION='Bearer token')
    with pytest.raises(exceptions.AuthenticationFailed) as exc:
        auth.authenticate(request)
    assert 'User is not authenticated' in str(exc.value)
