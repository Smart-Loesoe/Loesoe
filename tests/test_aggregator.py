def test_aggregate_dedupes_by_url():
    from loesoe.search.aggregator import aggregate
    a = [{"title": "x", "url": "a"}, {"title": "y", "url": "b"}]
    b = [{"title": "z", "url": "a"}]
    out = aggregate([a, b], dedupe=True)
    assert [r.get("url") for r in out] == ["a", "b"]
