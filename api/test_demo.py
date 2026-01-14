# C:\Loesoe\tests\api\test_demo.py
def test_demo_endpoint():
    from fastapi.testclient import TestClient
    from loesoe.api.main import app
    client = TestClient(app)
    r = client.get("/demo")
    assert r.status_code == 200
    data = r.json()

    # basisstructuur
    assert "router" in data and "prompts" in data and "memory" in data
    assert data["router"]["search"] == "search"

    # prompts: juiste keys en inhoud
    assert "templates" in data["prompts"]
    assert "default" in data["prompts"]["templates"]
    assert "Wat is Loesoe?" in data["prompts"]["default"]
