"""Tests for sub-phase 7: structured pipeline timing in design_completed events."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, ANY

import pytest

os.environ.setdefault("TESTING", "1")


class TestPipelineTiming:
    """Verify timing fields are captured and logged during create_design."""

    def test_timing_dict_in_design_completed_event(self):
        """The design_completed event includes a timing dict with all stage keys."""
        from app.auth import get_current_user
        from app.main import app
        from fastapi.testclient import TestClient

        _user = {"user_id": "timing-user-1", "email": "t@test.com", "token": "tok"}
        app.dependency_overrides[get_current_user] = lambda: _user

        # Mock the entire pipeline to run fast
        with patch("app.api.routes.parse_intake") as mock_intake, \
             patch("app.api.routes.interpret_style") as mock_style, \
             patch("app.api.routes.plan_composition") as mock_comp, \
             patch("app.api.routes.validate_composition") as mock_gate, \
             patch("app.api.routes.AmazonAdapter") as mock_adapter, \
             patch("app.api.routes.select_products") as mock_select, \
             patch("app.api.routes._build_response") as mock_build, \
             patch("app.api.routes.log_event") as mock_log_event, \
             patch("app.api.routes.log_selections"), \
             patch("services.concurrency.acquire_llm_slots", return_value=True), \
             patch("services.concurrency.release_llm_slots"), \
             patch("services.design_store.save_design"):

            # Minimal mocks to get through the pipeline
            mock_room_req = MagicMock()
            mock_room_req.run_id = "timing-run-1"
            mock_room_req.room_type = "bedroom"
            mock_room_req.bed_size = None
            mock_room_req.mirror_type = None
            mock_room_req.screen_size = None
            mock_room_req.interests = []
            mock_intake.return_value = mock_room_req

            mock_style_profile = MagicMock()
            mock_style_profile.sourcing_terms = ["wood"]
            mock_style_profile.keywords = ["wood"]
            mock_style_profile.priority_terms = []
            mock_style.return_value = mock_style_profile

            # Empty slot plan (no slots to source/select)
            mock_slot_plan = MagicMock()
            mock_slot_plan.slots = []
            mock_comp.return_value = mock_slot_plan
            mock_gate.return_value = (mock_slot_plan, None)

            mock_response = MagicMock()
            mock_response.run_id = "timing-run-1"
            mock_response.total_spent = 0.0
            mock_build.return_value = mock_response

            # Need to return a serializable dict from the endpoint
            from app.api.schemas import DesignResponse, StyleResult
            real_response = DesignResponse(
                run_id="timing-run-1",
                room_type="bedroom",
                style=StyleResult(
                    style_name="warm_minimalist",
                    keywords=["wood"],
                    mood="calm",
                    confidence=0.9,
                    fallback=False,
                ),
                target_budget=1000.0,
                total_spent=0.0,
                is_feasible=True,
                slots=[],
                user_id=_user["user_id"],
            )
            mock_build.return_value = real_response

            client = TestClient(app)
            resp = client.post("/design", json={
                "room_type": "bedroom",
                "budget": 2000,
                "style_description": "warm minimalist",
            })

            # The design_completed event should have been logged
            completed_calls = [
                c for c in mock_log_event.call_args_list
                if len(c.args) >= 2 and c.args[1] == "design_completed"
            ]
            assert len(completed_calls) == 1, f"Expected 1 design_completed event, got {len(completed_calls)}"

            event_data = completed_calls[0].args[2]
            assert "timing" in event_data, f"timing dict missing from event data: {event_data}"

            timing = event_data["timing"]
            expected_keys = {"intake_ms", "style_ms", "composition_ms", "sourcing_ms", "selection_ms", "total_ms"}
            assert expected_keys.issubset(timing.keys()), f"Missing timing keys: {expected_keys - timing.keys()}"

            # All values should be non-negative numbers
            for key, val in timing.items():
                assert isinstance(val, (int, float)), f"{key} is not a number: {val}"
                assert val >= 0, f"{key} is negative: {val}"

        app.dependency_overrides.pop(get_current_user, None)

    def test_render_timing_in_event(self):
        """The render_generated event includes render_ms when render succeeds."""
        from app.api.routes import _render_worker

        mock_redis = MagicMock()

        with patch("services.redis_client.get_redis", return_value=mock_redis), \
             patch("services.render_service.render_room", return_value="/fake/path.jpg"), \
             patch("app.api.routes.log_event") as mock_log:

            _render_worker(
                job_id="timing-job-1",
                run_id="timing-render-1",
                room_type="bedroom",
                style_name="warm_minimalist",
                mood="calm",
                keywords=["wood"],
                products={},
                user_id="timing-user-1",
            )

            render_calls = [
                c for c in mock_log.call_args_list
                if len(c.args) >= 2 and c.args[1] == "render_generated"
            ]
            assert len(render_calls) == 1
            event_data = render_calls[0].args[2]
            assert "render_ms" in event_data
            assert isinstance(event_data["render_ms"], float)
            assert event_data["render_ms"] >= 0
