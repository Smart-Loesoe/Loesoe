# loesoe/dev/assistant.py
from __future__ import annotations
import ast
from textwrap import dedent
from typing import Dict, Any, Tuple

RISKY_TOKENS = {
    "eval", "exec", "os.system", "subprocess.", "import pickle", "pickle.loads"
}

def _require_fields(spec: dict, fields: list[str]):
    missing = [f for f in fields if f not in spec or spec[f] in (None, {}, [], "")]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

def _py_type(t: str) -> str:
    ts = (t or "any").lower()
    if ts in {"int", "float", "str", "bool", "dict", "list"}:
        return ts
    return "object"

def _doc(lang: str, verbosity: str) -> str:
    if lang == "nl":
        return "'''Korte uitleg'''"
    return "'''Short description'''" if verbosity == "kort" else "'''Detailed description of the function.'''"

def _todo(lang: str) -> str:
    return "# TODO: implementeer de logica" if lang == "nl" else "# TODO: implement logic"

def _ret_hint_and_value(out_type: str) -> Tuple[str, str]:
    t = (out_type or "none").lower()
    mapping = {
        "int": ("int", "0"),
        "float": ("float", "0.0"),
        "str": ("str", "''"),
        "bool": ("bool", "False"),
        "dict": ("dict", "{}"),
        "list": ("list", "[]"),
        "none": ("None", "None"),
    }
    return mapping.get(t, ("None", "None"))

# ---------- TEMPLATES ----------
def _render_function(name: str, inputs: Dict[str, str], outputs: Dict[str, str], lang: str, verbosity: str) -> str:
    args_sig = ", ".join(f"{k}: {_py_type(v)}" for k, v in inputs.items())
    ret_hint, ret_val = _ret_hint_and_value(next(iter(outputs.values()), "None"))
    return dedent(f"""\
    def {name}({args_sig}) -> {ret_hint}:
        {_doc(lang, verbosity)}
        {_todo(lang)}
        return {ret_val}
    """)

def _render_module(name: str, inputs: Dict[str, str], outputs: Dict[str, str], lang: str, verbosity: str) -> str:
    fn_name = name or "main"
    function_code = _render_function(fn_name, inputs, outputs, lang, verbosity)
    title = "Klein module-skelet" if lang == "nl" else "Small module skeleton"
    return dedent(f"""\
    \"\"\"{title}\"\"\"

    {function_code}

    if __name__ == "__main__":
        # {'Voorbeeld-aanroep' if lang=='nl' else 'Example call'}
        pass
    """)

def _render_fastapi_endpoint(name: str, inputs: Dict[str, str], outputs: Dict[str, str], lang: str, verbosity: str) -> str:
    fn_name = name or "compute"
    args_sig = ", ".join(f"{k}: {_py_type(v)}" for k, v in inputs.items())
    ret_hint, ret_val = _ret_hint_and_value(next(iter(outputs.values()), "dict"))
    explanation = "Eenvoudig FastAPI-endpoint" if lang == "nl" else "Simple FastAPI endpoint"

    defaults = ", ".join(f"{k}=None" for k in inputs.keys()) if inputs else ""
    return dedent(f"""\
    from fastapi import APIRouter
    router = APIRouter()

    def {fn_name}({args_sig}) -> {ret_hint}:
        {_doc(lang, verbosity)}
        {_todo(lang)}
        return {ret_val}

    @router.get("/example")
    def example_endpoint() -> {ret_hint}:
        \"\"\"{explanation}\"\"\"
        return {fn_name}({defaults})
    """)

def _render_tests(name: str, template: str, lang: str) -> str:
    title_ok = "werkt" if lang == "nl" else "works"
    if template == "endpoint":
        return dedent(f"""\
        from fastapi.testclient import TestClient
        from loesoe.api.main import app

        client = TestClient(app)

        def test_example_endpoint_{name or 'fn'}():
            r = client.get("/example")
            assert r.status_code == 200
        """)
    # function/module: simpel rooktestje
    fn = name or "main"
    return dedent(f"""\
    def test_function_{fn}_{title_ok}():
        assert True
    """)

# ---------- PUBLIC ----------
def generate(spec: Dict[str, Any], persona: Dict[str, Any] | None = None) -> Dict[str, str]:
    """
    Genereer code (en optioneel test_code) o.b.v. spec:
      - fields: goal, inputs, outputs, name?, template? ('function'|'module'|'endpoint'), mode? ('tests-eerst'|'code-eerst')
      - persona: language ('nl'|'en'), verbosity ('kort'|'lang')
    Return: {'code': '...', 'test_code': '...'(optioneel)}
    """
    persona = persona or {}
    lang = (persona.get("language") or "nl").lower()
    verbosity = (persona.get("verbosity") or "kort").lower()

    _require_fields(spec, ["goal", "inputs", "outputs"])
    name = spec.get("name") or "main"
    template = (spec.get("template") or "function").lower()
    mode = (spec.get("mode") or "tests-eerst").lower()

    inputs = spec["inputs"]
    outputs = spec["outputs"]

    if template == "module":
        code = _render_module(name, inputs, outputs, lang, verbosity)
    elif template == "endpoint":
        code = _render_fastapi_endpoint(name, inputs, outputs, lang, verbosity)
    else:
        code = _render_function(name, inputs, outputs, lang, verbosity)

    result = {"code": code}
    if mode == "tests-eerst":
        result["test_code"] = _render_tests(name, template, lang)
    return result

def generate_code(spec: Dict[str, Any], persona: Dict[str, Any] | None = None) -> str:
    """Compat: alleen code-string."""
    return generate(spec, persona).get("code", "")

def review_code(code: str) -> dict:
    """Syntaxis, gevaarlijke tokens, docstrings, regellengte."""
    warnings: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "warnings": [f"SyntaxError: {e}"]}

    lower = code.lower()
    ok = True
    for tok in RISKY_TOKENS:
        if tok in lower:
            ok = False
            warnings.append(f"Gevaarlijk gebruik: {tok}")

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            has_doc = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and hasattr(node.body[0], "value")
                and isinstance(getattr(node.body[0], "value", None), ast.Str)
            )
            if not has_doc:
                warnings.append(f"Functie '{node.name}' mist een docstring.")

    for i, line in enumerate(code.splitlines(), start=1):
        if len(line) > 120:
            warnings.append(f"Regel {i} is langer dan 120 tekens.")

    return {"ok": ok and not any(w.startswith("SyntaxError") for w in warnings), "warnings": warnings}
