def test_simple_route_variants():
    from loesoe.core.router import simple_route
    assert simple_route("search") == "search"
    assert simple_route("recall") == "memory"
    assert simple_route("dev") == "dev"
    assert simple_route(None) == "default"
    assert simple_route("iets-anders") == "default"
