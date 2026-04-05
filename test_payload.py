import base64
payload_b64 = 'eyJpc3MiOiJzdXBhYmFzZSIsInN1YiI6ImQ0NDQwMWYwLWNmZjAtNGQ1ZC1iZjcxLTliMThmMTI2NzU5YyIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJleHAiOjE3NzUzODAzNDB9'
payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
print(base64.b64decode(payload_b64).decode('utf-8'))
