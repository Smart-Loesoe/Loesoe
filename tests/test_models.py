from loesoe.api.model_router import generate_response

def test_model_response():
    result = generate_response("Zeg hallo in het Nederlands.")
    assert result["status"] == "success"
    assert "hallo" in result["response"].lower()
