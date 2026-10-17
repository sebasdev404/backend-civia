import urllib.request
import json

tokens = {
    "Johan Steed (275486829735525)": "EAAdzhZBZCKZCMkBSiWvwHdfloetJMPlcY6ht8sDLGrFYDkSZBarQHSLZBSAn7Q8wqtfhHsWxYHjyZAZCM60mOc4hQCJNKwfYHE5uascmnZASI5FObAQWqQf6IUOHYxJx84sYbppmZC73hNsPPwSe9mYot4ahk3bX08cBSwQbeWveaHkpEkazQVZA0GxnMCZAK51v8JHlRhZBNENtvVPPsxuWaZA5bfXDQfNTU1iAEbTZCpeqgYJvj5jc22XN2wQd7i",
    "Johan Steed Ortiz Fernandez (322101261805063)": "EAAdzhZBZCKZCMkBSmnhg9p8BWw3uaywFasdygbRDb63dBpcZCpe9OBqOQGp9AbuZAoMOXXNd1e3BFXZAZA0iZC7KEUZCrfhCME1LD4SYMvumjTXuyqeiGQD3KZBSP4CEiupVBqoZBED0WWJZA7NYNt3UGSCbGsDmndHZAwq2JXyenVeM0FZA3F8yP87SdYz4CXfsOQtHtlBLPi0qqkMWslhIY3iZBwsGvl1vvkRUmSFqm2RVdORZCZA2vdONcQAl21HbkDwZDZD"
}

for name, tok in tokens.items():
    print(f"=== Testing {name} ===")
    pid = name.split("(")[1].split(")")[0]
    url = f"https://graph.facebook.com/v21.0/{pid}/posts?fields=id,message,created_time,full_picture&limit=5&access_token={tok}"
    try:
        with urllib.request.urlopen(url) as r:
            res = json.loads(r.read().decode())
            data = res.get("data", [])
            print(f"Posts count: {len(data)}")
            for p in data:
                msg = p.get('message', 'Sin texto')
                print(f" - [{p.get('created_time')}]: {msg[:90]}")
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.read().decode())

