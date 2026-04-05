import jwt
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInN1YiI6ImQ0NDQwMWYwLWNmZjAtNGQ1ZC1iZjcxLTliMThmMTI2NzU5YyIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJleHAiOjE3NzUzODAzNDB9.1z3C9HWM-kF0_Zt6-w1_m7O7Z"
secret = 'CWyKZkTEPaduvYZ651Z6KGPKtsj24ctyUL4/G81kx2WRaSysRT+F1NtO7jRASVJgfT+8908QtN7LwDfkLkvrqQ=='
try:
    jwt.decode(token, secret, algorithms=['HS256'], options={"verify_aud": False})
except Exception as e:
    import builtins
    print(type(e).__name__, str(e))
