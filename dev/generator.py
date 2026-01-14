"""
Dev Buddy – generator.py
Maakt simpele stubs/snippets (zonder GPT).
"""

def generate_stub(module: str, name: str) -> str:
    """
    Genereer een minimale Python-stub.
    Voor nu: simpele functie met pass.
    """
    module = (module or "module").strip()
    name = (name or "name").strip()
    return f"# Stub for {module}.{name}\n\ndef {name}():\n    pass\n"
