# C:\Loesoe\tests\api\test_memory.py
def test_memory_set_get_st_and_lt_paths():
    from fastapi.testclient import TestClient
    from loesoe.api.main import app
    client = TestClient(app)

    # clear ST first (DELETE i.p.v. POST)
    r = client.delete("/memory/clear-st")
    assert r.status_code == 200

    # Set LT value and get it
    r = client.post("/memory/focus", json={"value": "demo-lt", "scope": "lt"})
    assert r.status_code == 200
    r = client.get("/memory/focus")
    assert r.status_code == 200
    assert r.json()["value"] == "demo-lt"

    # Now override with ST and ensure retrieval prefers ST
    r = client.post("/memory/focus", json={"value": "demo-st", "scope": "st"})
    assert r.status_code == 200
    r = client.get("/memory/focus")
    assert r.status_code == 200
    assert r.json()["value"] == "demo-st"
