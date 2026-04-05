import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User

class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', None)
        
        if not jwt_secret:
            raise exceptions.AuthenticationFailed('SUPABASE_JWT_SECRET is not configured on the backend.')

        try:
            # Спроба 1: Розкодувати як Base64 (стандарт для хмарного Supabase)
            import base64
            try:
                decoded_secret = base64.b64decode(jwt_secret)
                payload = jwt.decode(token, decoded_secret, algorithms=['HS256'], options={"verify_aud": False})
            except jwt.ExpiredSignatureError:
                # Якщо токен просто прострочився, це означає що сам секрет ПРАВИЛЬНИЙ. Прокидаємо далі.
                raise
            except Exception:
                # Спроба 2: Якщо Base64 не спрацював або це старий локальний токен, використовуємо як рядок
                payload = jwt.decode(token, jwt_secret, algorithms=['HS256'], options={"verify_aud": False})
            
            # В Supabase ID користувача зберігається у полі 'sub'
            user_id = payload.get('sub')
            email = payload.get('email')
            
            # Деякі JWT від Supabase можуть не містити 'role', але мають 'aud' == 'authenticated'
            role = payload.get('role')
            aud = payload.get('aud')
            
            if role != 'authenticated' and aud != 'authenticated':
                raise exceptions.AuthenticationFailed(f'User is not authenticated (role={role}, aud={aud}).')

            # Ми використовуємо user_id (UUID від Supabase) як username в базі Django
            user, created = User.objects.get_or_create(username=user_id)
            
            if created and email:
                user.email = email
                # Якщо це перший логін будь-кого, можна зробити його адміном,
                # АЛЕ в реальності краще роздавати адмінки вручну через консоль.
                user.save()

            return (user, token)

        except jwt.ExpiredSignatureError as e:
            raise exceptions.AuthenticationFailed(f'Token Expired: {str(e)}')
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid Token: {str(e)} | Secret length: {len(str(jwt_secret))}')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Unknown Auth Error: {str(e)}')
