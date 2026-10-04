import requests

r = requests.post('http://localhost:8000/api/v1/auth/login', json={'email':'admin@acme.io','password':'Demo1234!'})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

contracts = requests.get('http://localhost:8000/api/v1/contracts?limit=100', headers=headers).json()
print(f"Total contracts returned by /contracts: {len(contracts)}\n")

for i, c in enumerate(contracts, 1):
    approvals = c.get('approvals', [])
    flow = " -> ".join([f"{a.get('step_name')} [{a.get('decision')}]" for a in approvals])
    step = c.get('current_approval_step') or 'N/A'
    print(f"{i:2d}. [{c.get('contract_number')}] Status: {c.get('status'):<18} | Step: {step:<18} | Title: {c.get('title')}")
    print(f"    Flow: {flow if flow else 'No approvals defined'}")
    print(f"    Counterparty: {c.get('counterparty')} | Value: {c.get('value_amount')} {c.get('value_currency')} | Risk: {c.get('risk_level')}")
    print()

inbox = requests.get('http://localhost:8000/api/v1/approvals/inbox', headers=headers).json()
print(f"\n--- Total items in Approvals Inbox (/approvals/inbox): {len(inbox)} ---")
for item in inbox:
    print(f" - Contract: '{item.get('contract_title')}' | Step: '{item.get('step_name')}' | Step Index: {item.get('step_index')} | Required Role: {item.get('required_role')} | Decision: {item.get('decision')}")
