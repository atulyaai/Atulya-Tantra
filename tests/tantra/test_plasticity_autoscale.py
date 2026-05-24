"""Tests for PlasticityAutoScaler — strand/layer scaling, cortex pruning."""


class TestPlasticityAutoScaler:
    """Tests for auto-scaling logic."""

    def test_no_action_when_idle(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        actions = ps.check_and_scale(strand_capacity=0.3, loss_history=[0.5, 0.4, 0.3], cortex_size=100, cortex_used=50)
        assert actions == []

    def test_add_strand_when_overloaded(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        actions = ps.check_and_scale(strand_capacity=0.95, loss_history=[0.5], cortex_size=100, cortex_used=50)
        assert "add_strand" in actions

    def test_add_layer_on_plateau(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        # 10 loss values with < 0.001 variance = plateau
        loss_history = [0.1] * 10
        actions = ps.check_and_scale(strand_capacity=0.3, loss_history=loss_history, cortex_size=100, cortex_used=50)
        assert "add_layer" in actions

    def test_prune_cortex_when_mostly_unused(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        # 100 total, only 20 used = 80% unused
        actions = ps.check_and_scale(strand_capacity=0.3, loss_history=[0.5], cortex_size=100, cortex_used=20)
        assert "prune_cortex" in actions

    def test_multiple_actions(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        # High strand load + plateau + mostly unused cortex = all actions
        actions = ps.check_and_scale(strand_capacity=0.95, loss_history=[0.1]*10, cortex_size=100, cortex_used=10)
        assert "add_strand" in actions
        assert "add_layer" in actions
        assert "prune_cortex" in actions

    def test_no_prune_when_cortex_empty(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        actions = ps.check_and_scale(strand_capacity=0.3, loss_history=[0.5], cortex_size=0, cortex_used=0)
        assert "prune_cortex" not in actions

    def test_get_metrics(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        ps.check_and_scale(strand_capacity=0.5, loss_history=[0.5], cortex_size=100, cortex_used=80)
        metrics = ps.get_metrics()
        assert metrics["strand_load"] == 0.5
        assert metrics["cortex_unused"] == 20
        assert metrics["last_check"] > 0

    def test_get_action_history(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        ps.check_and_scale(strand_capacity=0.95, loss_history=[0.5], cortex_size=100, cortex_used=50)
        history = ps.get_action_history()
        assert len(history) == 1
        assert history[0]["action"] == "add_strand"
        assert "timestamp" in history[0]
        assert "reason" in history[0]

    def test_action_history_capped(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler()
        for _ in range(100):
            ps.check_and_scale(strand_capacity=0.95, loss_history=[0.5], cortex_size=100, cortex_used=50)
        history = ps.get_action_history()
        assert len(history) <= 50

    def test_custom_config(self):
        from tantra.npdna.plasticity_autoscale import PlasticityAutoScaler
        ps = PlasticityAutoScaler(config={"auto_scale": True, "max_strands": 48})
        assert ps.config["auto_scale"] is True
        assert ps.config["max_strands"] == 48

    def test_plasticity_metrics_dataclass(self):
        from tantra.npdna.plasticity_autoscale import PlasticityMetrics
        pm = PlasticityMetrics(strand_load=0.8, layer_loss_plateau=5, cortex_unused=30)
        assert pm.strand_load == 0.8
        assert pm.layer_loss_plateau == 5
        assert pm.cortex_unused == 30
        assert pm.last_check > 0
