def test_search_web_exists_and_returns_list():
    from loesoe.search.google import search_web
    res = search_web("loesoe", limit=3)
    assert isinstance(res, list)
