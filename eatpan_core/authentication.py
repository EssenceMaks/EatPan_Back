import jwt
from jwt import PyJWKClient
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

# JWKS клієнт для перевірки ES256-токенів від хмарного Supabase.
# PyJWKClient автоматично кешує ключі, тому мережевий запит відбувається рідко.
SUPABASE_PROJECT_REF = 'pkdnyonrejptotlpzclq'
JWKS_URL = f'https://{SUPABASE_PROJECT_REF}.supabase.co/auth/v1/.well-known/jwks.json'
_jwks_client = None

def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(JWKS_URL)
    return _jwks_client


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            # Визначаємо алгоритм токена з його заголовка (без перевірки підпису)
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get('alg', '')

            if alg == 'ES256':
                # --- ES256 (Asymmetric) ---
                # Хмарний Supabase видає токени з ES256 підписом.
                # Перевіряємо через публічний ключ з JWKS ендпоінта.
                jwks_client = get_jwks_client()
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=['ES256'],
                    audience='authenticated'
                )
            elif alg == 'HS256':
                # --- HS256 (Symmetric) ---
                # Локальний Supabase видає токени з HS256 підписом.
                # Перевіряємо через SUPABASE_JWT_SECRET.
                jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', None)
                if not jwt_secret:
                    raise exceptions.AuthenticationFailed(
                        'SUPABASE_JWT_SECRET is not configured on the backend.'
                    )
                
                import base64
                try:
                    decoded_secret = base64.b64decode(jwt_secret)
                    payload = jwt.decode(token, decoded_secret, algorithms=['HS256'], options={"verify_aud": False})
                except jwt.ExpiredSignatureError:
                    raise
                except Exception:
                    payload = jwt.decode(token, jwt_secret, algorithms=['HS256'], options={"verify_aud": False})
            else:
                raise exceptions.AuthenticationFailed(
                    f'Unsupported JWT algorithm: {alg}'
                )

            # В Supabase ID користувача зберігається у полі 'sub'
            user_id = payload.get('sub')
            email = payload.get('email')

            # Перевірка ролі: підтримуємо і 'role', і 'aud'
            role = payload.get('role')
            aud = payload.get('aud')

            if role != 'authenticated' and aud != 'authenticated':
                raise exceptions.AuthenticationFailed(
                    f'User is not authenticated (role={role}, aud={aud}).'
                )

            # Ми використовуємо user_id (UUID від Supabase) як username в базі Django
            user, created = User.objects.get_or_create(username=user_id)

            if created and email:
                user.email = email
                user.save()

            return (user, token)

        except jwt.ExpiredSignatureError as e:
            raise exceptions.AuthenticationFailed(f'Token Expired: {str(e)}')
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid Token: {str(e)}')
        except exceptions.AuthenticationFailed:
            raise
        except Exception as e:
            logger.exception('JWT authentication error')
            raise exceptions.AuthenticationFailed(f'Auth Error: {str(e)}')
