"""
Dev Buddy – tester.py
Maakt simpele rooktestjes (later pytest integratie).
"""

def make_smoke_test(name: str) -> str:
    """
    Genereer een mini-testfunctie die altijd slaagt.
    """
    name = (name or "sample").strip().replace(" ", "_")
    return f"def test_{name}():\n    assert True\n"
