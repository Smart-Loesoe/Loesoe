def test_prompts_list_and_get():
    from loesoe.core.prompts import list_templates, get_prompt
    tpls = list_templates()
    assert "default" in tpls
    p = get_prompt("default", question="Wat is Loesoe?")
    assert "Wat is Loesoe?" in p

def test_prompts_missing_fields_does_not_crash():
    from loesoe.core.prompts import get_prompt
    # Mist 'snippet' → mag niet crashen in skeleton
    s = get_prompt("dev_review")
    assert isinstance(s, str)
