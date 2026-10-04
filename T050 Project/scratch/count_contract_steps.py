import requests

r = requests.post('http://localhost:8000/api/v1/auth/login', json={'email':'admin@acme.io','password':'Demo1234!'})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

contracts = requests.get('http://localhost:8000/api/v1/contracts?limit=100', headers=headers).json()
for c in contracts:
    cid = c['id']
    timeline = requests.get(f'http://localhost:8000/api/v1/approvals/contract/{cid}', headers=headers).json()
    print(f"[{c['contract_number']}] {c['status']:<18} : {len(timeline)} steps | Title: {c['title']}")
