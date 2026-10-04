"""
app/services/fitness_service.py

Business logic for fitness data management.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.fitness import FitnessData, FitnessSource
from app.schemas.fitness import (
    FitnessDataCreate,
    FitnessDataUpdate,
    FitnessDataResponse,
    FitnessDataListResponse,
    FitnessDailyResponse,
)


class FitnessService:
    """Service layer for fitness data management."""

    def __init__(self, db: Session):
        self.db = db

    def create_fitness_data(self, fitness_data: FitnessDataCreate) -> FitnessData:
        """Create a new fitness data record."""
        # Extract date from recorded_at
        data_date = fitness_data.recorded_at.date()

        fitness = FitnessData(
            user_id=fitness_data.user_id,
            steps=fitness_data.steps,
            sleep_duration=fitness_data.sleep_duration,
            recorded_at=fitness_data.recorded_at,
            date=data_date,
            source=fitness_data.source,
        )
        self.db.add(fitness)
        self.db.commit()
        self.db.refresh(fitness)
        return fitness

    def get_fitness_data(self, fitness_id: int, user_id: Optional[int] = None) -> Optional[FitnessData]:
        """Get a fitness data record by ID, optionally filtered by user."""
        query = self.db.query(FitnessData).filter(FitnessData.id == fitness_id)
        if user_id is not None:
            query = query.filter(FitnessData.user_id == user_id)
        return query.first()

    def get_fitness_history(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
        source: Optional[str] = None,
    ) -> List[FitnessData]:
        """Get fitness history for a user with optional date range and source filtering."""
        query = self.db.query(FitnessData).filter(FitnessData.user_id == user_id)

        if start_date:
            query = query.filter(FitnessData.date >= start_date)
        if end_date:
            query = query.filter(FitnessData.date <= end_date)
        if source:
            query = query.filter(FitnessData.source == source)

        return query.order_by(FitnessData.recorded_at.desc()).limit(limit).offset(offset).all()

    def get_fitness_for_date(self, user_id: int, target_date: date) -> List[FitnessData]:
        """Get all fitness records for a specific date."""
        return self.db.query(FitnessData).filter(
            FitnessData.user_id == user_id,
            FitnessData.date == target_date
        ).order_by(FitnessData.recorded_at.desc()).all()

    def get_daily_summary(self, user_id: int, target_date: date) -> FitnessDailyResponse:
        """Get a daily fitness summary for a user."""
        records = self.get_fitness_for_date(user_id, target_date)

        total_steps = sum(r.steps for r in records if r.steps is not None) if records else None
        total_sleep = sum(r.sleep_duration for r in records if r.sleep_duration is not None) if records else None
        sources = [FitnessSource(r.source.value) for r in records] if records else []

        return FitnessDailyResponse(
            user_id=user_id,
            date=target_date,
            total_steps=total_steps,
            total_sleep_duration=total_sleep,
            sources=sources,
            records=[FitnessDataResponse.model_validate(r) for r in records],
        )

    def update_fitness_data(
        self,
        fitness_id: int,
        user_id: int,
        update_data: FitnessDataUpdate
    ) -> Optional[FitnessData]:
        """Update a fitness data record."""
        fitness = self.get_fitness_data(fitness_id, user_id)
        if not fitness:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(fitness, field, value)

        fitness.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(fitness)
        return fitness

    def delete_fitness_data(self, fitness_id: int, user_id: int) -> bool:
        """Delete a fitness data record."""
        fitness = self.get_fitness_data(fitness_id, user_id)
        if not fitness:
            return False

        self.db.delete(fitness)
        self.db.commit()
        return True

    def get_latest_fitness(self, user_id: int) -> Optional[FitnessData]:
        """Get the most recent fitness record for a user."""
        return self.db.query(FitnessData).filter(
            FitnessData.user_id == user_id
        ).order_by(FitnessData.recorded_at.desc()).first()

    def get_date_range_stats(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> dict:
        """Get aggregate statistics for a date range."""
        query = self.db.query(FitnessData).filter(
            FitnessData.user_id == user_id,
            FitnessData.date >= start_date,
            FitnessData.date <= end_date
        )

        records = query.all()

        if not records:
            return {
                "total_records": 0,
                "total_steps": 0,
                "total_sleep_minutes": 0,
                "avg_steps_per_day": 0,
                "avg_sleep_per_day": 0,
                "days_with_data": 0,
            }

        total_steps = sum(r.steps for r in records if r.steps is not None)
        total_sleep = sum(r.sleep_duration for r in records if r.sleep_duration is not None)

        # Count unique dates with data
        dates_with_data = set(r.date for r in records)

        return {
            "total_records": len(records),
            "total_steps": total_steps,
            "total_sleep_minutes": total_sleep,
            "avg_steps_per_day": total_steps / len(dates_with_data) if dates_with_data else 0,
            "avg_sleep_per_day": total_sleep / len(dates_with_data) if dates_with_data else 0,
            "days_with_data": len(dates_with_data),
        }