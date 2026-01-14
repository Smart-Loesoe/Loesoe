from loesoe.core import prompts

def test_list_templates_contains_default():
    tpls = prompts.list_templates()
    assert "default" in tpls

def test_get_prompt_inserts_question():
    q = "Wat is Loesoe?"
    p = prompts.get_prompt("default", question=q)
    # Controleer dat de vraag in de gegenereerde prompt zit
    assert q in p

def test_add_and_remove_template():
    name = "mijn-template"
    prompts.add_template(name, "Hallo {question}")
    assert name in prompts.list_templates()
    result = prompts.get_prompt(name, question="test")
    assert "test" in result

    prompts.remove_template(name)
    assert name not in prompts.list_templates()
