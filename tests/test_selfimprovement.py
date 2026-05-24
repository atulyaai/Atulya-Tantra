"""Tests for UnifiedSelfImprovement — chakras, skills, achievements, learning log."""

import tempfile
import os


class TestUnifiedSelfImprovement:
    """Tests for the self-improvement lifecycle system."""

    def test_initialization(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            assert usi.data_dir.exists()
            assert usi.chakras == {}
            assert usi.skills == {}
            assert usi.achievements == []

    def test_add_chakra(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            assert "wisdom" in usi.chakras
            assert usi.chakras["wisdom"].level == 0

    def test_add_chakra_duplicate(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.add_chakra("wisdom")  # same name
            assert len(usi.chakras) == 1

    def test_gain_experience(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.gain_experience("wisdom", 150)
            assert usi.chakras["wisdom"].experience == 150

    def test_gain_experience_nonexistent_chakra(self):
        """Gaining experience on nonexistent chakra should not throw."""
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.gain_experience("nonexistent", 100)  # no crash

    def test_add_skill(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_skill("python", category="coding")
            assert "python" in usi.skills
            assert usi.skills["python"].category == "coding"

    def test_practice_skill(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_skill("python")
            # practice_skill takes duration, not difficulty
            usi.practice_skill("python", duration=10.0)
            assert usi.skills["python"].level > 0

    def test_unlock_achievement(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.unlock_achievement("first_step", "Completed first interaction")
            assert len(usi.achievements) == 1
            assert usi.achievements[0].name == "first_step"

    def test_log_learning(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.log_learning("Python", "Learned about decorators")
            assert len(usi.learning_log) == 1

    def test_get_stats(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            usi = UnifiedSelfImprovement(tmp)
            usi.add_chakra("wisdom")
            usi.add_chakra("courage")
            usi.add_skill("python")
            usi.unlock_achievement("first", "test")
            # get_stats exists (not get_progress_report)
            stats = usi.get_stats()
            assert "chakras" in stats
            assert "skills" in stats
            assert "achievements" in stats

    def test_persistence(self):
        from atulya.selfimprovement.unified import UnifiedSelfImprovement
        with tempfile.TemporaryDirectory() as tmp:
            s1 = UnifiedSelfImprovement(tmp)
            s1.add_chakra("focus")
            s1.add_skill("writing")
            s1.unlock_achievement("first", "test")

            s2 = UnifiedSelfImprovement(tmp)
            assert "focus" in s2.chakras
            assert "writing" in s2.skills
            assert len(s2.achievements) == 1
