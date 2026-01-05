"""Unit tests for Editor debug loop."""


from act.editor.debug_loop import (
    CONSECUTIVE_FAILURE_THRESHOLD,
    MAX_REPLANS,
    TOTAL_VERIFY_LOOP_THRESHOLD,
    DebugLoop,
    DebugLoopState,
    LoopAction,
    VerifyAttempt,
    create_debug_loop,
)


class TestConstants:
    """Tests for debug loop constants."""

    def test_consecutive_failure_threshold(self) -> None:
        """Test consecutive failure threshold is 3."""
        assert CONSECUTIVE_FAILURE_THRESHOLD == 3

    def test_total_verify_loop_threshold(self) -> None:
        """Test total verify loop threshold is 12."""
        assert TOTAL_VERIFY_LOOP_THRESHOLD == 12

    def test_max_replans(self) -> None:
        """Test maximum REPLANs is 3."""
        assert MAX_REPLANS == 3


class TestLoopAction:
    """Tests for LoopAction enum."""

    def test_all_actions_defined(self) -> None:
        """Test all expected actions are defined."""
        expected = ["CONTINUE", "REPLAN", "HARD_STOP", "SUCCESS"]
        actual = [a.name for a in LoopAction]
        assert set(expected) == set(actual)


class TestVerifyAttempt:
    """Tests for VerifyAttempt dataclass."""

    def test_create_passed_attempt(self) -> None:
        """Test creating a passed attempt."""
        attempt = VerifyAttempt(
            run_id="run_001",
            passed=True,
            attempt_number=1,
        )
        assert attempt.run_id == "run_001"
        assert attempt.passed is True
        assert attempt.failure_summary == ""

    def test_create_failed_attempt(self) -> None:
        """Test creating a failed attempt."""
        attempt = VerifyAttempt(
            run_id="run_002",
            passed=False,
            failure_summary="Type error in main.py",
            attempt_number=2,
        )
        assert attempt.passed is False
        assert attempt.failure_summary == "Type error in main.py"


class TestDebugLoopState:
    """Tests for DebugLoopState dataclass."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = DebugLoopState()
        assert state.consecutive_failures == 0
        assert state.total_verify_loops == 0
        assert state.replan_count == 0
        assert state.attempts == []
        assert state.current_hypothesis == ""
        assert state.strategy_history == []

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        state = DebugLoopState(
            consecutive_failures=2,
            total_verify_loops=5,
        )
        result = state.to_dict()
        assert result["consecutive_failures"] == 2
        assert result["total_verify_loops"] == 5

    def test_get_all_run_ids(self) -> None:
        """Test getting all run IDs."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(run_id="run_001", passed=True, attempt_number=1),
            VerifyAttempt(run_id="run_002", passed=False, attempt_number=2),
        ]
        run_ids = state.get_all_run_ids()
        assert run_ids == ["run_001", "run_002"]


class TestDebugLoop:
    """Tests for DebugLoop class."""

    def test_initial_state(self) -> None:
        """Test initial loop state."""
        loop = DebugLoop()
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 0
        assert loop.replan_count == 0

    def test_reset(self) -> None:
        """Test reset clears all state."""
        loop = DebugLoop()
        loop.record_failure("run_001", "Error")
        loop.reset()
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 0

    def test_record_success_resets_counters(self) -> None:
        """Test that success resets consecutive failures."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        loop.record_failure("run_002")
        assert loop.consecutive_failures == 2

        action = loop.record_success("run_003")
        assert action == LoopAction.SUCCESS
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 3

    def test_record_failure_increments_counters(self) -> None:
        """Test that failure increments both counters."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        assert loop.consecutive_failures == 1
        assert loop.total_verify_loops == 1

    def test_three_failures_triggers_replan(self) -> None:
        """Test that 3 consecutive failures triggers REPLAN."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        loop.record_failure("run_002")
        action = loop.record_failure("run_003")
        assert action == LoopAction.REPLAN

    def test_replan_resets_consecutive_only(self) -> None:
        """Test REPLAN resets consecutive but not total."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        loop.record_failure("run_002")
        loop.record_failure("run_003")

        loop.trigger_replan("New strategy")
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 3  # Not reset
        assert loop.replan_count == 1

    def test_twelve_loops_triggers_hard_stop(self) -> None:
        """Test that 12 total loops triggers hard stop."""
        loop = DebugLoop()

        # Simulate 12 failures
        for i in range(1, 12):
            action = loop.record_failure(f"run_{i:03d}")
            if action == LoopAction.REPLAN:
                loop.trigger_replan(f"Strategy {i}")

        # The 12th failure should trigger hard stop
        action = loop.record_failure("run_012")
        assert action == LoopAction.HARD_STOP

    def test_hard_stop_takes_precedence_over_replan(self) -> None:
        """Test hard stop takes precedence when both triggers fire."""
        loop = DebugLoop()

        # Simulate reaching loop 12 at exactly 3 consecutive failures.
        # Pattern: 3 failures, REPLAN, 3 failures, REPLAN, 3 failures, REPLAN,
        # 3 failures = 12 total
        for round_num in range(4):
            for i in range(3):
                run_id = f"run_{round_num * 3 + i + 1:03d}"
                action = loop.record_failure(run_id)

                if loop.total_verify_loops == 12:
                    # At loop 12, should be hard stop even if consecutive is 3
                    assert action == LoopAction.HARD_STOP
                    return
                elif action == LoopAction.REPLAN:
                    loop.trigger_replan(f"Strategy {round_num}")

    def test_set_hypothesis(self) -> None:
        """Test setting hypothesis."""
        loop = DebugLoop()
        loop.set_hypothesis("The bug is in the parser")
        assert loop.state.current_hypothesis == "The bug is in the parser"

    def test_should_requery_scouts_import_errors(self) -> None:
        """Test re-query decision for import errors."""
        loop = DebugLoop()
        assert loop.should_requery_scouts("ImportError: module not found")
        assert loop.should_requery_scouts("Missing dependency")

    def test_should_requery_scouts_build_errors(self) -> None:
        """Test re-query decision for build errors."""
        loop = DebugLoop()
        assert loop.should_requery_scouts("Build failed")
        assert loop.should_requery_scouts("Compile error")

    def test_should_not_requery_for_logic_errors(self) -> None:
        """Test no re-query for clear logic errors."""
        loop = DebugLoop()
        assert not loop.should_requery_scouts("Expected 5 but got 3")
        assert not loop.should_requery_scouts("Assertion failed")

    def test_get_failure_summary_no_attempts(self) -> None:
        """Test failure summary with no attempts."""
        loop = DebugLoop()
        summary = loop.get_failure_summary()
        assert "No verification attempts" in summary

    def test_get_failure_summary_with_failures(self) -> None:
        """Test failure summary with failures."""
        loop = DebugLoop()
        loop.record_failure("run_001", "First error")
        loop.record_failure("run_002", "Second error")
        summary = loop.get_failure_summary()
        assert "2 failures" in summary
        assert "run_001" in summary

    def test_get_attempt_count_display(self) -> None:
        """Test attempt count display string."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        loop.record_failure("run_002")
        display = loop.get_attempt_count_display()
        assert "2/12" in display

    def test_strategy_history_tracking(self) -> None:
        """Test that strategy history is tracked."""
        loop = DebugLoop()
        loop.record_failure("run_001")
        loop.record_failure("run_002")
        loop.record_failure("run_003")
        loop.trigger_replan("Strategy A")

        loop.record_failure("run_004")
        loop.record_failure("run_005")
        loop.record_failure("run_006")
        loop.trigger_replan("Strategy B")

        assert loop.state.strategy_history == ["Strategy A", "Strategy B"]


class TestCreateDebugLoop:
    """Tests for create_debug_loop factory function."""

    def test_creates_fresh_loop(self) -> None:
        """Test factory creates a fresh loop."""
        loop = create_debug_loop()
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 0

    def test_creates_new_instance(self) -> None:
        """Test factory creates new instance each time."""
        loop1 = create_debug_loop()
        loop2 = create_debug_loop()
        assert loop1 is not loop2


class TestDebugLoopScenarios:
    """Integration tests for debug loop scenarios."""

    def test_example_scenario_from_spec(self) -> None:
        """Test the example scenario from editor.md spec.

        Attempt 1: FAIL  → consecutive=1, total=1
        Attempt 2: FAIL  → consecutive=2, total=2
        Attempt 3: FAIL  → consecutive=3, total=3 → REPLAN triggered
                           consecutive resets to 0
        Attempt 4: FAIL  → consecutive=1, total=4
        ...continues...
        """
        loop = DebugLoop()

        # Attempts 1-3
        loop.record_failure("run_001")
        assert loop.consecutive_failures == 1
        assert loop.total_verify_loops == 1

        loop.record_failure("run_002")
        assert loop.consecutive_failures == 2
        assert loop.total_verify_loops == 2

        action = loop.record_failure("run_003")
        assert action == LoopAction.REPLAN
        assert loop.consecutive_failures == 3
        assert loop.total_verify_loops == 3

        loop.trigger_replan("New approach")
        assert loop.consecutive_failures == 0

        # Attempt 4
        loop.record_failure("run_004")
        assert loop.consecutive_failures == 1
        assert loop.total_verify_loops == 4

    def test_success_in_middle_resets_only_consecutive(self) -> None:
        """Test success in the middle of attempts."""
        loop = DebugLoop()

        loop.record_failure("run_001")
        loop.record_failure("run_002")
        assert loop.consecutive_failures == 2
        assert loop.total_verify_loops == 2

        loop.record_success("run_003")
        assert loop.consecutive_failures == 0
        assert loop.total_verify_loops == 3  # Still counts

        loop.record_failure("run_004")
        assert loop.consecutive_failures == 1

    def test_max_three_replans_before_hard_stop(self) -> None:
        """Test that up to 3 REPLANs occur before hard stop."""
        loop = DebugLoop()
        replan_count = 0

        for i in range(12):
            action = loop.record_failure(f"run_{i + 1:03d}")
            if action == LoopAction.REPLAN:
                replan_count += 1
                loop.trigger_replan(f"Strategy {replan_count}")
            elif action == LoopAction.HARD_STOP:
                break

        # At loop 12, we should have had 3 REPLANs (at 3, 6, 9)
        assert loop.replan_count == 3
