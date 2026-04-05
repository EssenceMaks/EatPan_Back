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
            # Валідуємо токен за допомогою нашого спільного Supabase JWT Secret
            payload = jwt.decode(
                token, 
                jwt_secret, 
                algorithms=['HS256'], 
                options={"verify_aud": False}
            )
            
            # В Supabase ID користувача зберігається у полі 'sub'
            user_id = payload.get('sub')
            email = payload.get('email')
            role = payload.get('role')

            if role != 'authenticated':
                raise exceptions.AuthenticationFailed('User is not authenticated (invalid role).')

            # Ми використовуємо user_id (UUID від Supabase) як username в базі Django
            user, created = User.objects.get_or_create(username=user_id)
            
            if created and email:
                user.email = email
                # Якщо це перший логін будь-кого, можна зробити його адміном,
                # АЛЕ в реальності краще роздавати адмінки вручну через консоль.
                user.save()

            return (user, token)

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Токен застарів (Token Expired).')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Невірний або підроблений токен.')
