# loesoe/dev/test_dev.py
from .assistant import generate_code, review_code

def test_generate_code_minimal():
    spec = {
        "goal": "Som",
        "inputs": {"a": "int", "b": "int"},
        "outputs": {"result": "int"},
        "rules": ["NL docstrings kort"]
    }
    code = generate_code(spec, persona={"language":"nl","verbosity":"kort"})
    assert "def" in code and "return" in code

def test_review_code_safe():
    code = "def ok(a:int,b:int)->int:\n    '''Som'''\n    return a+b\n"
    res = review_code(code)
    assert res["ok"] is True
    assert res["warnings"] == []

def test_review_code_risky():
    code = "def bad():\n    exec('print(1)')\n"
    res = review_code(code)
    assert res["ok"] is False
    assert any("exec" in w.lower() for w in res["warnings"])
