import base64
import jwt
import os

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInN1YiI6ImI5MGYxMGRjLTYzYTgtNGVlOC05MWE1LWU0ZTVmMWQyMmUyNiIsImV4cCI6MjU1NjA1NzYwMCwiaWF0IjoxNjc1MzY1Mjg1LCJhdWQiOiJhdXRoZW50aWNhdGVkIiwicm9sZSI6ImF1dGhlbnRpY2F0ZWQifQ."
# We don't have the actual valid token signature, but we can generate one.
secret = 'CWyKZkTEPaduvYZ651Z6KGPKtsj24ctyUL4/G81kx2WRaSysRT+F1NtO7jRASVJgfT+8908QtN7LwDfkLkvrqQ=='

decoded_secret = base64.b64decode(secret)
payload = {'role': 'authenticated', 'sub': '123'}
valid_token = jwt.encode(payload, decoded_secret, algorithm='HS256')

try:
    print("Testing string secret:")
    jwt.decode(valid_token, secret, algorithms=['HS256'], options={"verify_aud": False})
    print("Success with string")
except Exception as e:
    print("Failed with string:", type(e), e)

try:
    print("Testing bytes secret:")
    res = jwt.decode(valid_token, decoded_secret, algorithms=['HS256'], options={"verify_aud": False})
    print("Success with bytes:", res)
except Exception as e:
    print("Failed with bytes:", type(e), e)
