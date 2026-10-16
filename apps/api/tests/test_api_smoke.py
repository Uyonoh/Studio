def test_api_smoke() -> None:
    import api
    import studio_core
    import studio_media
    import studio_providers

    assert api.__version__ == "0.1.0"
    assert studio_core.__version__ == "0.1.0"
    assert studio_providers.__version__ == "0.1.0"
    assert studio_media.__version__ == "0.1.0"
