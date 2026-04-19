import urllib.request
import urllib.error
import os
import json

# Create dummy text file
with open('test_image.jpg', 'wb') as f:
    # 1x1 GIF just to pass basic MIME checks
    f.write(b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')

# Helper function for multipart/form-data
def build_multipart(filename, content):
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/gif\r\n\r\n"
    ).encode('utf-8') + content + f"\r\n--{boundary}--\r\n".encode('utf-8')
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    return body, headers

with open('test_image.jpg', 'rb') as f:
    content = f.read()

body, headers = build_multipart('test_image.jpg', content)

# Testing Render
url = 'https://eatpan-back.onrender.com/api/v1/media/upload/'
print(f"Uploading to Render: {url}")
req = urllib.request.Request(url, data=body, headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print(f"[OK] Response: {response.status}")
        print(json.loads(response.read().decode()))
except urllib.error.HTTPError as e:
    print(f"[ERROR] HTTP {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"[ERROR] {e}")

# Clean up
os.remove('test_image.jpg')
