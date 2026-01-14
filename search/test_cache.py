def test_search_cache_basic():
    from loesoe.search.google import search_web, cache_info, selected_provider
    # eerste call -> miss
    before = cache_info()
    _ = search_web("loesoe", limit=1)
    mid = cache_info()
    # tweede call (zelfde query/provider/limit) -> hit
    _ = search_web("loesoe", limit=1)
    after = cache_info()

    # hits moeten niet dalen en size minstens 1
    assert after["hits"] >= mid["hits"]
    assert after["size"] >= 1
    assert selected_provider() in {"serpapi", "bing", "stub"}