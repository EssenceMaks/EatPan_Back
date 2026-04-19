import urllib.request
import json

url = "http://localhost:8000/auth/v1/signup"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzc1Mzk4ODE3LCJleHAiOjE5MzMwNzg4MTd9.JswW_RO1LTOWvShTqg2Q1t7TNOMydJrS8OhLl-8MXTY"

headers = {
    "apikey": anon_key,
    "Content-Type": "application/json"
}

users = [
    {"email": f"test_user_{i}@eatpan.com", "password": "TestPass123!", "data": {"display_name": f"Test User {i}"}}
    for i in range(1, 6)
]

print("Creating 5 test users in Supabase Auth...")

for u in users:
    req = urllib.request.Request(url, data=json.dumps(u).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            print(f"[OK] Created {u['email']} - UUID: {res_data.get('user', {}).get('id')}")
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode()
        if "already registered" in error_msg.lower():
            print(f"[SKIP] {u['email']} already exists.")
        else:
            print(f"[ERROR] {u['email']} - HTTP {e.code}: {error_msg}")
    except Exception as e:
        print(f"[ERROR] {u['email']} - {e}")
