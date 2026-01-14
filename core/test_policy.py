from loesoe.core.policy import select_style, context_to_style, StyleProfile

def test_context_mapping_to_style():
    st = context_to_style({"intent":"code"})
    assert st.tone == "zakelijk" and st.structure == "rapport" and st.emojis is False

def test_policy_cascade_order():
    # persona casual, prefs straat, context kids, explicit zakelijk -> explicit wint
    persona = {"style":{"tone":"casual"}}
    prefs   = {"style":{"tone":"straat","verbosity":"kort","emojis":True}}
    context = {"intent":"kids"}  # would set Jip
    explicit = {"style":{"tone":"zakelijk"}}

    final = select_style(persona=persona, prefs=prefs, context=context, explicit=explicit)
    assert final.tone == "zakelijk"        # explicit override
    assert final.verbosity in ("kort","normaal")  # comes from prefs unless overridden
