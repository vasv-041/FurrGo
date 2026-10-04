"""
tests/test_fitness.py

Tests for Phase 8A: Fitness Data Foundation
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock
import uuid

from app.models.fitness import FitnessData, FitnessSource
from app.schemas.fitness import (
    FitnessDataCreate,
    FitnessDataUpdate,
    FitnessDataResponse,
    FitnessDataListResponse,
    FitnessDailyResponse,
    FitnessSource,
)
from app.services.fitness_service import FitnessService
from app.core.database import get_db


class TestFitnessSource:
    """Tests for FitnessSource enum."""

    def test_fitness_source_values(self):
        """Test FitnessSource enum values."""
        assert FitnessSource.GOOGLE_FIT.value == "google_fit"
        assert FitnessSource.FITNESS_TRACKER.value == "fitness_tracker"
        assert FitnessSource.MANUAL.value == "manual"

    def test_fitness_source_membership(self):
        """Test FitnessSource membership."""
        assert "google_fit" in [s.value for s in FitnessSource]
        assert "fitness_tracker" in [s.value for s in FitnessSource]
        assert "manual" in [s.value for s in FitnessSource]


class TestFitnessDataCreate:
    """Tests for FitnessDataCreate schema."""

    def test_valid_fitness_create_steps_only(self):
        """Test creating fitness data with steps only."""
        fitness = FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        )
        assert fitness.steps == 5000
        assert fitness.sleep_duration is None
        assert fitness.source == FitnessSource.MANUAL

    def test_valid_fitness_create_sleep_only(self):
        """Test creating fitness data with sleep only."""
        fitness = FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            sleep_duration=480,  # 8 hours in minutes
            source=FitnessSource.FITNESS_TRACKER,
        )
        assert fitness.sleep_duration == 480
        assert fitness.steps is None

    def test_valid_fitness_create_both_metrics(self):
        """Test creating fitness data with both metrics."""
        fitness = FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=8000,
            sleep_duration=420,
            source=FitnessSource.GOOGLE_FIT,
        )
        assert fitness.steps == 8000
        assert fitness.sleep_duration == 420
        assert fitness.source == FitnessSource.GOOGLE_FIT

    def test_negative_steps_rejected(self):
        """Test that negative steps are rejected."""
        with pytest.raises(ValueError, match="Steps cannot be negative"):
            FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now(),
                steps=-100,
                source=FitnessSource.MANUAL,
            )

    def test_negative_sleep_rejected(self):
        """Test that negative sleep duration is rejected."""
        with pytest.raises(ValueError, match="Sleep duration cannot be negative"):
            FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now(),
                sleep_duration=-30,
                source=FitnessSource.MANUAL,
            )

    def test_invalid_source_rejected(self):
        """Test that invalid source is rejected."""
        with pytest.raises(ValueError):
            FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now(),
                steps=5000,
                source="invalid_source",  # type: ignore
            )

    def test_no_metrics_rejected(self):
        """Test that providing no metrics is rejected."""
        with pytest.raises(ValueError, match="At least one of steps or sleep_duration must be provided"):
            FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now(),
                source=FitnessSource.MANUAL,
            )


class TestFitnessDataUpdate:
    """Tests for FitnessDataUpdate schema."""

    def test_valid_update(self):
        """Test valid update."""
        update = FitnessDataUpdate(steps=6000)
        assert update.steps == 6000

    def test_negative_steps_rejected(self):
        """Test negative steps rejected in update."""
        with pytest.raises(ValueError, match="Steps cannot be negative"):
            FitnessDataUpdate(steps=-100)

    def test_negative_sleep_rejected(self):
        """Test negative sleep rejected in update."""
        with pytest.raises(ValueError, match="Sleep duration cannot be negative"):
            FitnessDataUpdate(sleep_duration=-10)

    def test_invalid_source_rejected(self):
        """Test invalid source rejected in update."""
        with pytest.raises(ValueError):
            FitnessDataUpdate(source="invalid_source")  # type: ignore


class TestFitnessSourceEnum:
    """Tests for FitnessSource enum in schemas."""

    def test_all_sources_accepted(self):
        """Test all valid sources are accepted."""
        for source in FitnessSource:
            fitness = FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now(),
                steps=1000,
                source=source,
            )
            assert fitness.source == source


class TestFitnessService:
    """Tests for FitnessService."""

    def test_create_fitness_data(self, db_session):
        """Test creating fitness data."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            sleep_duration=480,
            source=FitnessSource.MANUAL,
        ))

        assert fitness.id is not None
        assert fitness.user_id == 1
        assert fitness.steps == 5000
        assert fitness.sleep_duration == 480
        assert fitness.source == FitnessSource.MANUAL
        assert fitness.date is not None

    def test_get_fitness_data(self, db_session):
        """Test getting fitness data by ID."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        retrieved = service.get_fitness_data(fitness.id, user_id=1)
        assert retrieved is not None
        assert retrieved.id == fitness.id
        assert retrieved.steps == 5000

        # Test without user_id
        retrieved_any = service.get_fitness_data(fitness.id)
        assert retrieved_any is not None

    def test_get_fitness_data_not_found(self, db_session):
        """Test getting non-existent fitness data."""
        service = FitnessService(db_session)
        result = service.get_fitness_data(9999, user_id=1)
        assert result is None

    def test_get_fitness_history(self, db_session):
        """Test getting fitness history."""
        service = FitnessService(db_session)
        
        # Create multiple records with explicit timestamps to ensure ordering
        base_time = datetime.now()
        for i in range(3):
            service.create_fitness_data(FitnessDataCreate(
                user_id=1,
                recorded_at=base_time - timedelta(days=i),
                steps=5000 + i * 1000,
                source=FitnessSource.MANUAL,
            ))

        history = service.get_fitness_history(user_id=1, limit=10)
        assert len(history) == 3
        # Should be ordered by recorded_at desc (most recent first)
        assert history[0].recorded_at >= history[1].recorded_at
        assert history[1].recorded_at >= history[2].recorded_at

    def test_get_fitness_history_date_filter(self, db_session):
        """Test getting fitness history with date filter."""
        service = FitnessService(db_session)
        
        # Create records for different dates
        today = date.today()
        for i in range(5):
            service.create_fitness_data(FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.combine(today - timedelta(days=i), datetime.min.time()),
                steps=5000,
                source=FitnessSource.MANUAL,
            ))

        # Filter last 3 days
        history = service.get_fitness_history(
            user_id=1,
            start_date=today - timedelta(days=2),
            end_date=today,
        )
        assert len(history) == 3

    def test_get_fitness_for_date(self, db_session):
        """Test getting fitness for a specific date."""
        service = FitnessService(db_session)
        target = date.today()
        
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(target, datetime.min.time()),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))
        
        records = service.get_fitness_for_date(1, target)
        assert len(records) == 1

    def test_get_daily_summary(self, db_session):
        """Test getting daily summary."""
        service = FitnessService(db_session)
        target = date.today()
        
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(target, datetime.min.time()),
            steps=5000,
            sleep_duration=480,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(target, datetime.min.time()) + timedelta(hours=12),
            steps=3000,
            source=FitnessSource.FITNESS_TRACKER,
        ))

        summary = service.get_daily_summary(1, target)
        assert summary.user_id == 1
        assert summary.date == target
        assert summary.total_steps == 8000
        assert summary.total_sleep_duration == 480
        assert len(summary.sources) == 2
        assert len(summary.records) == 2

    def test_update_fitness_data(self, db_session):
        """Test updating fitness data."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        updated = service.update_fitness_data(fitness.id, 1, FitnessDataUpdate(steps=6000))
        assert updated is not None
        assert updated.steps == 6000

    def test_update_fitness_not_found(self, db_session):
        """Test updating non-existent fitness data."""
        service = FitnessService(db_session)
        result = service.update_fitness_data(9999, 1, FitnessDataUpdate(steps=6000))
        assert result is None

    def test_delete_fitness_data(self, db_session):
        """Test deleting fitness data."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        success = service.delete_fitness_data(fitness.id, 1)
        assert success is True

        # Verify deleted
        deleted = service.get_fitness_data(fitness.id, user_id=1)
        assert deleted is None

    def test_delete_fitness_not_found(self, db_session):
        """Test deleting non-existent fitness data."""
        service = FitnessService(db_session)
        result = service.delete_fitness_data(9999, 1)
        assert result is False

    def test_get_latest_fitness(self, db_session):
        """Test getting latest fitness record."""
        service = FitnessService(db_session)
        
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now() - timedelta(days=1),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))
        latest = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=6000,
            source=FitnessSource.MANUAL,
        ))

        result = service.get_latest_fitness(1)
        assert result is not None
        assert result.id == latest.id

    def test_get_date_range_stats(self, db_session):
        """Test getting date range statistics."""
        service = FitnessService(db_session)
        today = date.today()
        
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today - timedelta(days=2), datetime.min.time()),
            steps=5000,
            sleep_duration=480,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today - timedelta(days=1), datetime.min.time()),
            steps=6000,
            sleep_duration=420,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today, datetime.min.time()),
            steps=7000,
            sleep_duration=500,
            source=FitnessSource.MANUAL,
        ))

        stats = service.get_date_range_stats(1, today - timedelta(days=2), today)
        assert stats["total_records"] == 3
        assert stats["total_steps"] == 18000
        assert stats["total_sleep_minutes"] == 1400
        assert stats["days_with_data"] == 3


class TestFitnessAPI:
    """Tests for Fitness API endpoints."""

    def test_create_fitness_data_api(self, client):
        """Test creating fitness data via API."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "steps": 5000,
                "sleep_duration": 480,
                "source": "manual",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["steps"] == 5000
        assert data["sleep_duration"] == 480
        assert data["source"] == "manual"

    def test_create_fitness_steps_only(self, client):
        """Test creating fitness with steps only."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "steps": 5000,
                "source": "manual",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["steps"] == 5000
        assert data["sleep_duration"] is None

    def test_create_fitness_sleep_only(self, client):
        """Test creating fitness with sleep only."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "sleep_duration": 480,
                "source": "manual",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["steps"] is None
        assert data["sleep_duration"] == 480

    def test_create_fitness_negative_steps_rejected(self, client):
        """Test negative steps rejected in API."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "steps": -100,
                "source": "manual",
            },
        )
        assert response.status_code == 422

    def test_create_fitness_negative_sleep_rejected(self, client):
        """Test negative sleep rejected in API."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "sleep_duration": -30,
                "source": "manual",
            },
        )
        assert response.status_code == 422

    def test_create_fitness_invalid_source_rejected(self, client):
        """Test invalid source rejected in API."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "steps": 5000,
                "source": "invalid_source",
            },
        )
        assert response.status_code == 422

    def test_create_fitness_no_metrics_rejected(self, client):
        """Test no metrics rejected in API."""
        response = client.post(
            "/api/fitness",
            json={
                "user_id": 1,
                "recorded_at": datetime.now().isoformat(),
                "source": "manual",
            },
        )
        assert response.status_code == 422

    def test_list_fitness_history(self, client, db_session):
        """Test listing fitness history via API."""
        service = FitnessService(db_session)
        for i in range(3):
            service.create_fitness_data(FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.now() - timedelta(days=i),
                steps=5000 + i * 1000,
                source=FitnessSource.MANUAL,
            ))

        response = client.get("/api/fitness")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["fitness_data"]) == 3

    def test_list_fitness_with_date_filter(self, client, db_session):
        """Test listing fitness with date filter."""
        service = FitnessService(db_session)
        today = date.today()
        for i in range(5):
            service.create_fitness_data(FitnessDataCreate(
                user_id=1,
                recorded_at=datetime.combine(today - timedelta(days=i), datetime.min.time()),
                steps=5000,
                source=FitnessSource.MANUAL,
            ))

        response = client.get(f"/api/fitness?start_date={today - timedelta(days=2)}&end_date={today}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    def test_list_fitness_with_source_filter(self, client, db_session):
        """Test listing fitness with source filter."""
        service = FitnessService(db_session)
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now() - timedelta(hours=1),
            steps=6000,
            source=FitnessSource.FITNESS_TRACKER,
        ))

        response = client.get("/api/fitness?source=manual")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["fitness_data"][0]["source"] == "manual"

    def test_get_daily_fitness(self, client, db_session):
        """Test getting daily fitness summary."""
        service = FitnessService(db_session)
        target = date.today()
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(target, datetime.min.time()),
            steps=5000,
            sleep_duration=480,
            source=FitnessSource.MANUAL,
        ))

        response = client.get(f"/api/fitness/daily?target_date={target.isoformat()}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 1
        assert data["date"] == target.isoformat()
        assert data["total_steps"] == 5000
        assert data["total_sleep_duration"] == 480

    def test_get_fitness_by_id(self, client, db_session):
        """Test getting fitness by ID."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        response = client.get(f"/api/fitness/{fitness.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fitness.id
        assert data["steps"] == 5000

    def test_get_fitness_not_found(self, client):
        """Test getting non-existent fitness."""
        response = client.get("/api/fitness/9999")
        assert response.status_code == 404

    def test_update_fitness(self, client, db_session):
        """Test updating fitness via API."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        response = client.patch(
            f"/api/fitness/{fitness.id}",
            json={"steps": 6000},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["steps"] == 6000

    def test_update_fitness_not_found(self, client):
        """Test updating non-existent fitness."""
        response = client.patch("/api/fitness/9999", json={"steps": 6000})
        assert response.status_code == 404

    def test_delete_fitness(self, client, db_session):
        """Test deleting fitness via API."""
        service = FitnessService(db_session)
        fitness = service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.now(),
            steps=5000,
            source=FitnessSource.MANUAL,
        ))

        response = client.delete(f"/api/fitness/{fitness.id}")
        assert response.status_code == 204

        # Verify deleted
        response2 = client.get(f"/api/fitness/{fitness.id}")
        assert response2.status_code == 404

    def test_delete_fitness_not_found(self, client):
        """Test deleting non-existent fitness."""
        response = client.delete("/api/fitness/9999")
        assert response.status_code == 404

    def test_get_range_stats(self, client, db_session):
        """Test getting range statistics."""
        service = FitnessService(db_session)
        today = date.today()
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today - timedelta(days=2), datetime.min.time()),
            steps=5000,
            sleep_duration=480,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today - timedelta(days=1), datetime.min.time()),
            steps=6000,
            sleep_duration=420,
            source=FitnessSource.MANUAL,
        ))
        service.create_fitness_data(FitnessDataCreate(
            user_id=1,
            recorded_at=datetime.combine(today, datetime.min.time()),
            steps=7000,
            sleep_duration=500,
            source=FitnessSource.MANUAL,
        ))

        response = client.get(f"/api/fitness/stats/range?start_date={today - timedelta(days=2)}&end_date={today}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_records"] == 3
        assert data["total_steps"] == 18000
        assert data["total_sleep_minutes"] == 1400

    def test_get_range_stats_invalid_dates(self, client):
        """Test range stats with invalid dates."""
        response = client.get(
            "/api/fitness/stats/range",
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() - timedelta(days=1)).isoformat(),
            },
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])