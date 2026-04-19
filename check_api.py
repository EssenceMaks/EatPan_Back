import urllib.request
import json

endpoints = [
    '/pantry/',
    '/shopping/',
    '/meal-plan/',
    '/meal-plan/labels/',
    '/social/followers/',
    '/social/following/',
    '/social/friend-groups/',
    '/messages/',
]

base_url = "https://eatpan-back.onrender.com/api/v1"

print(f"Testing endpoints on {base_url}...")

for endpoint in endpoints:
    url = f"{base_url}{endpoint}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            print(f"[OK] {endpoint} -> {response.status}")
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            print(f"[AUTH REQUIRED] {endpoint} -> {e.code} (Expected behavior for protected endpoints)")
        else:
            print(f"[ERROR] {endpoint} -> {e.code}")
    except Exception as e:
        print(f"[FAILED] {endpoint} -> {str(e)}")

print("\nTesting Media Upload (/media/upload/)...")
# Send a dummy POST request to see if endpoint exists
req = urllib.request.Request(f"{base_url}/media/upload/", method="POST")
try:
    with urllib.request.urlopen(req) as response:
        print(f"[OK] /media/upload/ -> {response.status}")
except urllib.error.HTTPError as e:
    if e.code == 400:
        print(f"[OK] /media/upload/ -> 400 (Expected, since we didn't send a file)")
    else:
        print(f"[STATUS] /media/upload/ -> {e.code} (Check if this is expected)")
except Exception as e:
    print(f"[FAILED] /media/upload/ -> {str(e)}")
