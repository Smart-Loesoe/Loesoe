# loesoe/api/test_api_memory_and_stats.py

import time
import json
import os
import pytest
from fastapi.testclient import TestClient

import loesoe.api.main as api

client = TestClient(api.app)

@pytest.fixture(autouse=True)
def _clean_env_and_state(monkeypatch):
    # Zorg voor voorspelbare ST-limiet en schone ST/MT state voor elke test
    monkeypatch.setenv("ST_MAX_ITEMS", "5")
    # ST leegmaken
    resp = client.delete("/memory/clear?scope=st")
    assert resp.status_code == 200
    # MT leegmaken
    resp = client.delete("/memory/clear?scope=mt")
    assert resp.status_code == 200
    yield
    client.delete("/memory/clear?scope=all")

def test_debug_stats_st_endpoint():
    # Vul ST een beetje via API (scope=st is default)
    r1 = client.post("/memory/k1", json={"value": "v1", "scope": "st"})
    r2 = client.post("/memory/k2", json={"value": "v2", "scope": "st"})
    assert r1.status_code == 200 and r2.status_code == 200

    # Stats endpoint
    resp = client.get("/debug/stats-st")
    assert resp.status_code == 200
    data = resp.json()
    assert "st" in data and "st_keys" in data
    assert "size" in data["st"] and "limit" in data["st"] and "evicted_count" in data["st"]
    assert isinstance(data["st_keys"], list)
    assert set(["k1", "k2"]).issubset(set(data["st_keys"]))

def test_generic_clear_endpoint_scopes():
    # Vul ST en MT via API
    assert client.post("/memory/a", json={"value": 1, "scope": "st"}).status_code == 200
    assert client.post("/memory/b", json={"value": 2, "scope": "st"}).status_code == 200
    assert client.post("/memory/temp", json={"value": "x", "scope": "mt", "ttl_seconds": 60}).status_code == 200

    # Clear alleen ST
    resp = client.delete("/memory/clear?scope=st")
    assert resp.status_code == 200
    cleared = resp.json()
    assert cleared["ok"] is True
    assert "st" in cleared["cleared"]
    # ST is leeg, MT moet nog bestaan
    r = client.get("/memory/temp").json()
    assert r["value"] == "x" and r["source"] == "mt"

    # Clear alleen MT
    resp = client.delete("/memory/clear?scope=mt")
    assert resp.status_code == 200
    r = client.get("/memory/temp").json()
    assert r["value"] is None and r["source"] is None

    # Vul opnieuw ST en MT en clear all
    assert client.post("/memory/c", json={"value": 3, "scope": "st"}).status_code == 200
    assert client.post("/memory/d", json={"value": 4, "scope": "st"}).status_code == 200
    assert client.post("/memory/mtk", json={"value": "y", "scope": "mt", "ttl_seconds": 60}).status_code == 200
    resp = client.delete("/memory/clear?scope=all")
    assert resp.status_code == 200
    # Alles moet weg
    assert client.get("/memory/c").json()["value"] is None
    assert client.get("/memory/mtk").json()["value"] is None

def test_api_mid_term_ttl_flow():
    # Zet MT met korte TTL
    r = client.post("/memory/theme", json={"value": "donker", "scope": "mt", "ttl_seconds": 1})
    assert r.status_code == 200
    # Direct ophalen -> mt
    got = client.get("/memory/theme").json()
    assert got["value"] == "donker" and got["source"] == "mt"
    # Wacht tot TTL verloopt
    time.sleep(1.2)
    got2 = client.get("/memory/theme").json()
    # Na expiry moet value None zijn
    assert got2["value"] is None and got2["source"] is None
