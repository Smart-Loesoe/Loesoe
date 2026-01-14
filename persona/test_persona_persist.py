from fastapi.testclient import TestClient
import loesoe.api.main as api

client = TestClient(api.app)

def test_persona_persist_roundtrip():
    # Zet persona (POST)
    body = {
        "tone": "zakelijk",
        "verbosity": "kort",
        "language": "nl",
        "voice_hint": "ColetteNeural",
        "safety_level": "normaal",
        "dev_style": "compact",
        "mode": "default"
    }
    r = client.post("/persona", json=body)
    assert r.status_code == 200
    # Lees terug (GET)
    g = client.get("/persona").json()["persona"]
    assert g["tone"] == "zakelijk"
    assert g["verbosity"] == "kort"
    assert g["language"] == "nl"
    assert g["voice_hint"] == "ColetteNeural"
    assert g["dev_style"] == "compact"
