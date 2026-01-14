# C:\Loesoe\tests\api\test_search.py
def test_search_endpoint_stub():
    from fastapi.testclient import TestClient
    from loesoe.api.main import app
    client = TestClient(app)

    r = client.get("/search", params={"q": "loesoe", "limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "loesoe"
    assert data["limit"] == 2
    assert isinstance(data["results"], list)
    assert len(data["results"]) <= 2
