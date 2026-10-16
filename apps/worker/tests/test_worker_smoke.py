def test_worker_smoke() -> None:
    import studio_core
    import studio_media
    import studio_providers
    import worker

    assert worker.__version__ == "0.1.0"
    assert studio_core.__version__ == "0.1.0"
    assert studio_providers.__version__ == "0.1.0"
    assert studio_media.__version__ == "0.1.0"
