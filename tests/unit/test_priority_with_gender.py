"""Tests for gender-aware priority calculation for missing wrestlers."""

import pytest

from joshirank.scrape.priority import calculate_missing_wrestler_priority


class TestMissingWrestlerPriorityWithGender:
    """Tests for calculate_missing_wrestler_priority with gender prediction."""

    def test_high_confidence_female_gets_urgent_priority(self, monkeypatch):
        """Test that high-confidence female wrestlers get urgent priority."""

        # Mock guess_gender_of_wrestler to return high female confidence
        def mock_guess(wrestler_id):
            return 0.95  # Very confident female

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

        # Mock database
        class MockDb:
            pass

        db = MockDb()

        # Many opponents + high confidence = URGENT priority (1-3)
        result = calculate_missing_wrestler_priority(
            n_opponents=25, wrestler_id=12345, wrestler_db=db
        )
        assert 1 <= result <= 3

    def test_high_confidence_male_gets_low_priority(self, monkeypatch):
        """Test that high-confidence male wrestlers get low priority."""

        def mock_guess(wrestler_id):
            return 0.1  # Very likely male

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

        class MockDb:
            pass

        db = MockDb()

        # Many opponents but low confidence = deprioritized
        result = calculate_missing_wrestler_priority(
            n_opponents=25, wrestler_id=12345, wrestler_db=db
        )
        assert result >= 70  # Heavily deprioritized

    def test_medium_confidence_uses_base_priority(self, monkeypatch):
        """Test that medium confidence uses base opponent-count priority."""

        def mock_guess(wrestler_id):
            return 0.55  # Uncertain

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

        class MockDb:
            pass

        db = MockDb()

        # 20+ opponents normally = URGENT (1)
        result = calculate_missing_wrestler_priority(
            n_opponents=25, wrestler_id=12345, wrestler_db=db
        )
        # Should be close to base priority (URGENT = 1)
        assert 1 <= result <= 5

    def test_fallback_when_no_database(self):
        """Test that it falls back to base priority without database."""
        # No wrestler_id or db provided
        result = calculate_missing_wrestler_priority(n_opponents=25)

        # Should use base priority (URGENT = 1 for 20+ opponents)
        assert result == 1

    def test_fallback_when_prediction_fails(self, monkeypatch):
        """Test that it falls back gracefully when prediction fails."""

        def mock_guess_error(wrestler_id):
            raise Exception("Prediction failed")

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess_error)

        class MockDb:
            pass

        db = MockDb()

        # Should fall back to base priority without crashing
        result = calculate_missing_wrestler_priority(
            n_opponents=25, wrestler_id=12345, wrestler_db=db
        )
        assert result == 1  # Base priority for 20+ opponents

    def test_scaling_with_opponent_count(self, monkeypatch):
        """Test that priority scales correctly with opponent count."""

        def mock_guess(wrestler_id):
            return 0.95  # High confidence female

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

        class MockDb:
            pass

        db = MockDb()

        # Test different opponent counts
        result_20plus = calculate_missing_wrestler_priority(
            n_opponents=25, wrestler_id=12345, wrestler_db=db
        )
        result_10plus = calculate_missing_wrestler_priority(
            n_opponents=15, wrestler_id=12345, wrestler_db=db
        )
        result_5plus = calculate_missing_wrestler_priority(
            n_opponents=7, wrestler_id=12345, wrestler_db=db
        )

        # More opponents = higher priority (lower number)
        assert result_20plus < result_10plus < result_5plus

    def test_likely_female_gets_moderate_boost(self, monkeypatch):
        """Test that likely-female wrestlers get moderate priority boost."""

        def mock_guess(wrestler_id):
            return 0.80  # Likely female

        from joshirank.scrape import priority

        monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

        class MockDb:
            pass

        db = MockDb()

        result = calculate_missing_wrestler_priority(
            n_opponents=15, wrestler_id=12345, wrestler_db=db
        )

        # Should be in HIGH range (15-18 for 10+ opponents with 0.75-0.95 confidence)
        assert 15 <= result <= 18

    def test_priority_respects_confidence_levels(self, monkeypatch):
        """Test that different confidence levels produce appropriate priorities."""
        from joshirank.scrape import priority

        class MockDb:
            pass

        db = MockDb()

        confidence_levels = {
            0.95: (1, 5),  # Very confident female: very high priority
            0.80: (10, 25),  # Likely female: high priority
            0.55: (1, 10),  # Uncertain: base priority
            0.25: (70, 95),  # Likely male: low priority
        }

        for confidence, (min_prio, max_prio) in confidence_levels.items():

            def mock_guess(wid):
                return confidence

            monkeypatch.setattr(priority, "guess_gender_of_wrestler", mock_guess)

            result = calculate_missing_wrestler_priority(
                n_opponents=20, wrestler_id=12345, wrestler_db=db
            )

            assert min_prio <= result <= max_prio, (
                f"Confidence {confidence} gave priority {result}, expected {min_prio}-{max_prio}"
            )
