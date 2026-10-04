import requests

r = requests.post('http://localhost:8000/api/v1/auth/login', json={'email':'admin@acme.io','password':'Demo1234!'})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Get contracts with approvals
inbox = requests.get('http://localhost:8000/api/v1/approvals/inbox', headers=headers).json()
seen_cids = set()
for item in inbox:
    cid = item['contract_id']
    if cid in seen_cids:
        continue
    seen_cids.add(cid)
    timeline = requests.get(f'http://localhost:8000/api/v1/approvals/contract/{cid}', headers=headers).json()
    print(f"\nContract on Approvals Page: '{item['contract_title']}' [{item['contract_number']}]")
    print(f"  Counterparty: {item.get('counterparty')} | Value: {item.get('value_amount')} {item.get('value_currency')} | Risk: {item.get('risk_level')}")
    print("  Sequential Workflow Timeline:")
    for s in timeline:
        print(f"    Step {s.get('step_index') + 1}: {s.get('step_name')} (Required Role: {s.get('required_role')}) -> Decision: {s.get('decision').upper()}")
