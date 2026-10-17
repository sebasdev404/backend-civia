import urllib.request
import json

user_token = "EAAdzhZBZCKZCMkBSiSU0MYOrWiO0RfIEDmGdIS2F9ASBbuBD92x3h0ZA8Lq4AGhMCfHfCcyIb9mozLd0ZCHej4htwP2MzRT60Oo6ghEdlx75CHqqvMcartrHKZBm7V1an2HQIn77zfBlsIxvl2nLSjshAOdc7qpZAvYYeM00NYiUM3b2mNKIdZC2HYiLkD8ji2yR3nq1W7lG5x0qltfDLKcwOvwrac8tIz8nhelasytlxnsDyZA81KMbGxcaZCMxRVHZANY4Rf5MGuDy9A2ewiyH4TsS5LoJa25qbkmg8UZD"
res = json.loads(urllib.request.urlopen(f"https://graph.facebook.com/v21.0/me/accounts?access_token={user_token}").read())
page_token = res["data"][0]["access_token"]
page_id = res["data"][0]["id"]
print(f"Testing Page: {res['data'][0]['name']} ({page_id})")

endpoints = ["published_posts", "posts", "feed", "ratings", "conversations"]
for ep in endpoints:
    url = f"https://graph.facebook.com/v21.0/{page_id}/{ep}?access_token={page_token}"
    try:
        r = json.loads(urllib.request.urlopen(url).read())
        print(f"OK [{ep}]: {len(r.get('data', []))} items found")
    except urllib.error.HTTPError as e:
        print(f"ERR [{ep}]: {e.read().decode()[:140]}")
