with open('app/services/audit_logger.py', 'r', encoding='utf-8') as f:
    audit_content = f.read()

audit_content = audit_content.replace('from app.database import db', 'from app.database import DatabaseRepository')
audit_content = audit_content.replace('def record_match_audit(\n        request: Dict[str, Any],', 'def record_match_audit(\n        repo: DatabaseRepository,\n        request: Dict[str, Any],')
audit_content = audit_content.replace('db.add_audit_log(audit_entry)', 'repo.add_audit_log(audit_entry)')

with open('app/services/audit_logger.py', 'w', encoding='utf-8') as f:
    f.write(audit_content)

with open('app/services/escalation_engine.py', 'r', encoding='utf-8') as f:
    engine_content = f.read()

engine_content = engine_content.replace('audit_logger.record_match_audit(request, match_summary)', 'audit_logger.record_match_audit(repo, request, match_summary)')

with open('app/services/escalation_engine.py', 'w', encoding='utf-8') as f:
    f.write(engine_content)

print("Fixed audit_logger")
