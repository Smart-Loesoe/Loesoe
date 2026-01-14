from loesoe.core.prompts import get_prompt
from loesoe.persona.model import save_persona, Persona

def test_persona_injection_contains_hints():
    # Zet persona 'kort + casual + nl + jip-en-janneke'
    p = Persona(tone="casual", verbosity="kort", language="nl", dev_style="uitleg", mode="jip-en-janneke")
    save_persona(p)

    s = get_prompt("default", question="Wat is Loesoe?")
    # Verwacht NL, kort, jip&janneke, uitleg
    assert "Taal: Nederlands." in s
    assert "Antwoord kort en to-the-point." in s
    assert "Leg het uit in eenvoudige Jip-en-Janneke taal" in s
    assert "Bij code: duidelijke uitleg met stappen" in s
