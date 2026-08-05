import re

# 1. Update requests.py
with open('app/api/requests.py', 'r', encoding='utf-8') as f:
    req_content = f.read()

req_content = req_content.replace('escalation_engine.execute_request_matching_and_fanout(saved_req)', 'escalation_engine.execute_request_matching_and_fanout(repo, saved_req)')
req_content = req_content.replace('escalation_engine.check_and_escalate_ring(request_id)', 'escalation_engine.check_and_escalate_ring(repo, request_id)')
req_content = req_content.replace('escalation_engine.find_nearby_blood_banks(req)', 'escalation_engine.find_nearby_blood_banks(repo, req)')

with open('app/api/requests.py', 'w', encoding='utf-8') as f:
    f.write(req_content)

# 2. Update escalation_engine.py
with open('app/services/escalation_engine.py', 'r', encoding='utf-8') as f:
    esc_content = f.read()

esc_content = esc_content.replace('from app.database import db', 'from app.database import DatabaseRepository')
esc_content = esc_content.replace('async def execute_request_matching_and_fanout(\n        self,\n        request: Dict[str, Any],', 'async def execute_request_matching_and_fanout(\n        self,\n        repo: DatabaseRepository,\n        request: Dict[str, Any],')
esc_content = esc_content.replace('async def check_and_escalate_ring(self, req_id: str)', 'async def check_and_escalate_ring(self, repo: DatabaseRepository, req_id: str)')
esc_content = esc_content.replace('def find_nearby_blood_banks(self, request: Dict[str, Any])', 'def find_nearby_blood_banks(self, repo: DatabaseRepository, request: Dict[str, Any])')

esc_content = re.sub(r'\bdb\.', 'repo.', esc_content)

with open('app/services/escalation_engine.py', 'w', encoding='utf-8') as f:
    f.write(esc_content)

print("Fixed escalation_engine and requests")
