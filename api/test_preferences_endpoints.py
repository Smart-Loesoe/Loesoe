from fastapi.testclient import TestClient
from loesoe.api.main import app
import os, tempfile

client = TestClient(app)

def test_preferences_crud(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("PREFERENCES_PATH", os.path.join(td, "prefs.json"))
        # GET default
        r = client.get("/memory/preferences")
        assert r.status_code == 200
        assert r.json()["style"]["tone"] in ("casual","zakelijk","jip","straat")

        # POST diff
        r2 = client.post("/memory/preferences", json={"diff":{"style":{"tone":"zakelijk"}}})
        assert r2.status_code == 200
        assert r2.json()["style"]["tone"] == "zakelijk"

        # Feedback
        r3 = client.post("/memory/feedback", json={"text":"korter en straattaal"})
        assert r3.status_code == 200
        assert r3.json()["style"]["verbosity"] == "kort"
        assert r3.json()["style"]["tone"] == "straat"

        # Clear
        r4 = client.post("/memory/clear-prefs")
        assert r4.status_code == 200
