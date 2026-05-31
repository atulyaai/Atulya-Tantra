import json


def test_tantra_benchmark_gate_rejects_missing_benchmark(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_FORCE_PROD", raising=False)
    assert _benchmark_allows_tantra(tmp_path) is False


def test_tantra_benchmark_gate_accepts_explicit_approval(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_FORCE_PROD", raising=False)
    (tmp_path / "benchmark.json").write_text(
        json.dumps({"production_gate": {"approved": True}}),
        encoding="utf-8",
    )

    assert _benchmark_allows_tantra(tmp_path) is True


def test_tantra_benchmark_gate_accepts_thresholds(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_FORCE_PROD", raising=False)
    (tmp_path / "benchmark.json").write_text(
        json.dumps({
            "perplexity": 30,
            "generation_speed": {"tokens_per_second": 12},
            "strand_utilization": {
                "layer_0": {"utilization_score": 0.8},
                "layer_1": {"utilization_score": 0.7},
            },
        }),
        encoding="utf-8",
    )

    assert _benchmark_allows_tantra(tmp_path) is True


def test_provider_router_keeps_tantra_behind_free_api_options():
    from atulya.intelligence import GeminiProvider, GroqProvider, OpenRouterProvider, ProviderRouter, TantraProvider

    providers = ProviderRouter().providers
    tantra_index = next(i for i, provider in enumerate(providers) if isinstance(provider, TantraProvider))
    for provider_type in (GroqProvider, OpenRouterProvider, GeminiProvider):
        assert next(i for i, provider in enumerate(providers) if isinstance(provider, provider_type)) < tantra_index
