from loesoe.core.context import detect_context

def test_detect_code_intent():
    c = detect_context("maak een script en endpoint met test")
    assert c["intent"] == "code"

def test_detect_kids_intent():
    c = detect_context("leg dit uit voor kind, jip en janneke graag")
    assert c["intent"] == "kids"

def test_detect_chat_intent():
    c = detect_context("hoe is het, even ouwehoeren")
    assert c["intent"] == "chat"
