# loesoe/api/test_dev_endpoints.py
import json
from fastapi.testclient import TestClient
from .main import app

client = TestClient(app)

def test_generate_minimal_spec():
    payload = {
        "goal": "Som van twee getallen",
        "inputs": {"a": "int", "b": "int"},
        "outputs": {"result": "int"},
        "rules": ["NL docstrings kort"]
    }
    r = client.post("/dev/generate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "code" in data
    assert "def" in data["code"]

def test_generate_bad_payload():
    r = client.post("/dev/generate", json={})
    assert r.status_code in (400, 422)

def test_review_ok_code():
    code = "def optel(a:int,b:int)->int:\n    '''Tel op'''\n    return a+b\n"
    r = client.post("/dev/review", json={"code": code})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["warnings"] == []

def test_review_flags_risky_calls():
    code = "def x():\n    eval('2+2')\n"
    r = client.post("/dev/review", json={"code": code})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert any("eval" in w.lower() for w in data["warnings"])
