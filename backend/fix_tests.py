with open('tests/test_api_endpoints.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('''    try:
        repo.add_donor({
        "id": "donor-test-01",
        "name": "Alex Smith",
        "phone": "+14155550199",
        "blood_type": "O-",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "city": "San Francisco",
        "is_active": True,
        "is_available": True
    })''', '''    try:
        repo.add_donor({
            "id": "donor-test-01",
            "name": "Alex Smith",
            "phone": "+14155550199",
            "blood_type": "O-",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "city": "San Francisco",
            "is_active": True,
            "is_available": True
        })
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()''')

with open('tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed test_api_endpoints.py")
