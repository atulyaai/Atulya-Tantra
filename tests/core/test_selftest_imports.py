def test_selftest_module_imports():
    """The deploy runs `atulya.cli selftest`; a broken import there hides every live check."""
    import tools.selftest

    assert callable(tools.selftest.main)
