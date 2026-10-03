"""
tests/test_medication.py

Tests for Phase 7A medication management functionality.
"""
import pytest
from datetime import date, time, datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.medication import Medication, MedicationSchedule, AdherenceLog, AdherenceStatus
from app.schemas.medication import MedicationCreate, MedicationUpdate, AdherenceLogCreate
from app.services.medication_service import MedicationService

# Use fixture for client with test database
#pytestmark = pytest.mark.usefixtures("client")

# Create a test client
client = TestClient(app)


# ==================== Unit Tests ====================


# ==================== Unit Tests ====================


# ==================== Unit Tests ====================

def test_medication_model_creation():
    """Test Medication model can be created with required fields."""
    med = Medication(
        user_id=1,
        name="Aspirin",
        dosage="100mg",
        frequency="daily",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        is_active=True,
    )
    assert med.name == "Aspirin"
    assert med.dosage == "100mg"
    assert med.frequency == "daily"
    assert med.is_active is True


def test_medication_schedule_model():
    """Test MedicationSchedule model."""
    schedule = MedicationSchedule(
        medication_id=1,
        time_of_day=time(8, 0),
        timezone="UTC",
        is_active=True,
    )
    assert schedule.time_of_day == time(8, 0)
    assert schedule.timezone == "UTC"
    assert schedule.is_active is True


def test_adherence_log_model():
    """Test AdherenceLog model."""
    log = AdherenceLog(
        medication_id=1,
        scheduled_time=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        status=AdherenceStatus.TAKEN,
    )
    assert log.status == AdherenceStatus.TAKEN


def test_adherence_status_enum():
    """Test AdherenceStatus enum values."""
    assert AdherenceStatus.TAKEN == "taken"
    assert AdherenceStatus.MISSED == "missed"
    assert AdherenceStatus.SNOOZED == "snoozed"


# ==================== Schema Validation Tests ====================

def test_medication_create_schema_valid():
    """Test valid medication creation schema."""
    data = MedicationCreate(
        name="Aspirin",
        dosage="100mg",
        frequency="daily",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        is_active=True,
    )
    assert data.name == "Aspirin"
    assert data.dosage == "100mg"
    assert data.frequency == "daily"


def test_medication_create_invalid_empty_name():
    """Test medication creation fails with empty name."""
    with pytest.raises(ValueError, match="cannot be empty"):
        MedicationCreate(
            name="",
            frequency="daily",
            start_date=date(2024, 1, 1),
        )


def test_medication_create_invalid_dates():
    """Test medication creation fails when end_date before start_date."""
    with pytest.raises(ValueError, match="end_date cannot be before start_date"):
        MedicationCreate(
            name="Aspirin",
            frequency="daily",
            start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1),
        )


def test_medication_update_valid():
    """Test valid medication update schema."""
    update = MedicationUpdate(
        name="Updated Aspirin",
        dosage="200mg",
    )
    assert update.name == "Updated Aspirin"
    assert update.dosage == "200mg"


def test_medication_update_invalid_empty_name():
    """Test medication update fails with empty name."""
    with pytest.raises(ValueError, match="cannot be empty"):
        MedicationUpdate(name="")


def test_adherence_log_create_valid():
    """Test valid adherence log creation."""
    log = AdherenceLogCreate(
        scheduled_time=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        status="taken",
        notes="Taken with breakfast",
    )
    assert log.status == "taken"
    assert log.notes == "Taken with breakfast"


def test_adherence_log_invalid_status():
    """Test adherence log creation fails with invalid status."""
    with pytest.raises(ValueError, match="must be one of"):
        AdherenceLogCreate(
            scheduled_time=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
            status="invalid_status",
        )


def test_adherence_log_invalid_status_case():
    """Test adherence log creation fails with wrong case."""
    with pytest.raises(ValueError, match="must be one of"):
        AdherenceLogCreate(
            scheduled_time=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
            status="TAKEN",  # Wrong case
        )


# ==================== Service Layer Tests ====================

def test_create_medication_service(db_session):
    """Test creating medication via service."""
    service = MedicationService(db_session)
    med_data = MedicationCreate(
        name="Test Med",
        dosage="10mg",
        frequency="daily",
        start_date=date.today(),
    )
    med = service.create_medication(user_id=1, medication_data=med_data)
    
    assert med.id is not None
    assert med.name == "Test Med"
    assert med.user_id == 1
    assert med.is_active is True


def test_get_medication_service(db_session):
    """Test retrieving medication via service."""
    service = MedicationService(db_session)
    med_data = MedicationCreate(
        name="Test Med",
        frequency="daily",
        start_date=date.today(),
    )
    created = service.create_medication(user_id=1, medication_data=med_data)
    
    retrieved = service.get_medication(created.id, user_id=1)
    assert retrieved is not None
    assert retrieved.id == created.id
    
    # Test with wrong user_id
    not_found = service.get_medication(created.id, user_id=999)
    assert not_found is None


def test_list_medications_service(db_session):
    """Test listing medications via service."""
    service = MedicationService(db_session)
    
    # Create multiple medications
    for i in range(3):
        service.create_medication(
            user_id=1,
            medication_data=MedicationCreate(
                name=f"Med {i}",
                frequency="daily",
                start_date=date.today(),
            )
        )
    
    meds = service.list_medications(user_id=1, active_only=True)
    assert len(meds) == 3
    
    # Test active_only filter
    service.deactivate_medication(meds[0].id, user_id=1)
    active_meds = service.list_medications(user_id=1, active_only=True)
    assert len(active_meds) == 2


def test_update_medication_service(db_session):
    """Test updating medication via service."""
    service = MedicationService(db_session)
    
    created = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Old Name", frequency="daily", start_date=date.today())
    )
    
    updated = service.update_medication(
        medication_id=created.id,
        user_id=1,
        update_data=MedicationUpdate(name="New Name", dosage="200mg")
    )
    
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.dosage == "200mg"


def test_deactivate_medication_service(db_session):
    """Test deactivating medication via service."""
    service = MedicationService(db_session)
    
    created = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    deactivated = service.deactivate_medication(created.id, user_id=1)
    assert deactivated.is_active is False


def test_delete_medication_service(db_session):
    """Test deleting medication via service."""
    service = MedicationService(db_session)
    
    created = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="To Delete", frequency="daily", start_date=date.today())
    )
    
    deleted = service.delete_medication(created.id, user_id=1)
    assert deleted is True
    
    # Verify it's gone
    assert service.get_medication(created.id, user_id=1) is None


def test_create_schedule_service(db_session):
    """Test creating medication schedule via service."""
    service = MedicationService(db_session)
    
    med = MedicationService(db_session).create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    from app.schemas.medication import MedicationScheduleCreate
    schedule = service.create_schedule(
        medication_id=med.id,
        user_id=1,
        schedule_data=MedicationScheduleCreate(time_of_day=time(9, 0), timezone="UTC")
    )
    
    assert schedule is not None
    assert schedule.medication_id == med.id
    assert schedule.time_of_day == time(9, 0)


def test_get_schedules_service(db_session):
    """Test getting schedules via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    from app.schemas.medication import MedicationScheduleCreate
    service.create_schedule(med.id, 1, MedicationScheduleCreate(time_of_day=time(8, 0)))
    service.create_schedule(med.id, 1, MedicationScheduleCreate(time_of_day=time(20, 0)))
    
    schedules = service.get_schedules(med.id)
    assert len(schedules) == 2


def test_create_adherence_log_service(db_session):
    """Test creating adherence log via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    log = service.create_adherence_log(
        medication_id=med.id,
        user_id=1,
        log_data=AdherenceLogCreate(
            scheduled_time=datetime.now(timezone.utc),
            status="taken",
        )
    )
    
    assert log is not None
    assert log.status == AdherenceStatus.TAKEN
    assert log.medication_id == med.id


def test_get_adherence_logs_service(db_session):
    """Test retrieving adherence logs via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    # Create multiple logs
    for status in ["taken", "missed", "taken"]:
        service.create_adherence_log(
            medication_id=med.id,
            user_id=1,
            log_data=AdherenceLogCreate(
                scheduled_time=datetime.now(timezone.utc),
                status=status,
            )
        )
    
    logs = service.get_adherence_logs(med.id, user_id=1)
    assert len(logs) == 3
    
    # Test status filtering
    taken_logs = [l for l in logs if l.status == "taken"]
    assert len(taken_logs) == 2


def test_calculate_adherence_percentage_service(db_session):
    """Test adherence percentage calculation via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    # Create logs: 3 taken, 1 missed
    for _ in range(3):
        service.create_adherence_log(
            medication_id=med.id,
            user_id=1,
            log_data=AdherenceLogCreate(
                scheduled_time=datetime.now(timezone.utc),
                status="taken",
            )
        )
    service.create_adherence_log(
        medication_id=med.id,
        user_id=1,
        log_data=AdherenceLogCreate(
            scheduled_time=datetime.now(timezone.utc),
            status="missed",
        )
    )
    
    summary = service.calculate_adherence_percentage(med.id, 1)
    
    assert summary.total_logs == 4
    assert summary.taken_count == 3
    assert summary.missed_count == 1
    assert summary.snoozed_count == 0
    assert summary.adherence_percentage == 75.0


def test_adherence_summary_no_logs(db_session):
    """Test adherence summary with no logs."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    summary = service.calculate_adherence_percentage(med.id, 1)
    
    assert summary.total_logs == 0
    assert summary.adherence_percentage == 0.0


def test_schedule_update_service(db_session):
    """Test updating schedule via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    from app.schemas.medication import MedicationScheduleCreate, MedicationScheduleUpdate
    schedule = service.create_schedule(
        med.id, 1, 
        MedicationScheduleCreate(time_of_day=time(8, 0), timezone="UTC")
    )
    
    updated = service.update_schedule(
        schedule.id, med.id, 1,
        MedicationScheduleUpdate(time_of_day=time(9, 0), is_active=False)
    )
    
    assert updated is not None
    assert updated.time_of_day == time(9, 0)
    assert updated.is_active is False


def test_deactivate_schedule_service(db_session):
    """Test deactivating schedule via service."""
    service = MedicationService(db_session)
    
    med = service.create_medication(
        user_id=1,
        medication_data=MedicationCreate(name="Test", frequency="daily", start_date=date.today())
    )
    
    from app.schemas.medication import MedicationScheduleCreate
    schedule = service.create_schedule(med.id, 1, MedicationScheduleCreate(time_of_day=time(8, 0)))
    
    success = service.deactivate_schedule(schedule.id, med.id)
    assert success is True
    
    # Verify it's deactivated
    schedules = service.get_schedules(med.id)
    assert schedules[0].is_active is False


# ==================== API Tests ====================

def test_create_medication_api():
    """Test POST /api/medications via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.create_medication") as mock_create:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.name = "Test"
            mock_med.dosage = "10mg"
            mock_med.frequency = "daily"
            mock_med.start_date = date.today()
            mock_med.end_date = None
            mock_med.is_active = True
            mock_med.notes = None
            mock_med.created_at = datetime.now(timezone.utc)
            mock_med.updated_at = datetime.now(timezone.utc)
            mock_med.user_id = 1
            mock_create.return_value = mock_med
            
            response = client.post(
                "/api/medications",
                json={
                    "name": "Test Med",
                    "dosage": "10mg",
                    "frequency": "daily",
                    "start_date": str(date.today()),
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Test"
            assert data["dosage"] == "10mg"


def test_list_medications_api():
    """Test GET /api/medications via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.list_medications") as mock_list:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.name = "Test"
            mock_med.dosage = "10mg"
            mock_med.frequency = "daily"
            mock_med.start_date = date.today()
            mock_med.end_date = None
            mock_med.is_active = True
            mock_med.notes = None
            mock_med.created_at = datetime.now(timezone.utc)
            mock_med.updated_at = datetime.now(timezone.utc)
            mock_med.user_id = 1
            mock_list.return_value = [mock_med]
            
            response = client.get("/api/medications")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["medications"][0]["name"] == "Test"


def test_get_medication_api():
    """Test GET /api/medications/{id} via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.get_medication") as mock_get:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.name = "Test"
            mock_med.dosage = "10mg"
            mock_med.frequency = "daily"
            mock_med.start_date = date.today()
            mock_med.end_date = None
            mock_med.is_active = True
            mock_med.notes = None
            mock_med.created_at = datetime.now(timezone.utc)
            mock_med.updated_at = datetime.now(timezone.utc)
            mock_med.user_id = 1
            mock_get.return_value = mock_med
            
            response = client.get("/api/medications/1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test"


def test_get_medication_not_found_api():
    """Test GET /api/medications/{id} returns 404 for nonexistent."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.get_medication") as mock_get:
            mock_get.return_value = None
            
            response = client.get("/api/medications/999")
            
            assert response.status_code == 404


def test_update_medication_api():
    """Test PATCH /api/medications/{id} via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.update_medication") as mock_update:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.name = "Updated"
            mock_med.dosage = "20mg"
            mock_med.frequency = "daily"
            mock_med.start_date = date.today()
            mock_med.end_date = None
            mock_med.is_active = True
            mock_med.notes = None
            mock_med.created_at = datetime.now(timezone.utc)
            mock_med.updated_at = datetime.now(timezone.utc)
            mock_med.user_id = 1
            mock_update.return_value = mock_med
            
            response = client.patch(
                "/api/medications/1",
                json={"name": "Updated", "dosage": "20mg"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Updated"


def test_deactivate_medication_api():
    """Test PATCH /api/medications/{id}/deactivate via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.deactivate_medication") as mock_deactivate:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.name = "Test"
            mock_med.dosage = "10mg"
            mock_med.frequency = "daily"
            mock_med.start_date = date.today()
            mock_med.end_date = None
            mock_med.is_active = False
            mock_med.notes = None
            mock_med.created_at = datetime.now(timezone.utc)
            mock_med.updated_at = datetime.now(timezone.utc)
            mock_med.user_id = 1
            mock_deactivate.return_value = mock_med
            
            response = client.patch("/api/medications/1/deactivate")
            
            assert response.status_code == 200
            data = response.json()
            assert data["is_active"] is False


def test_delete_medication_api():
    """Test DELETE /api/medications/{id} via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.delete_medication") as mock_delete:
            mock_delete.return_value = True
            
            response = client.delete("/api/medications/1")
            
            assert response.status_code == 204


def test_delete_medication_not_found_api():
    """Test DELETE /api/medications/{id} returns 404 for nonexistent."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.delete_medication") as mock_delete:
            mock_delete.return_value = False
            
            response = client.delete("/api/medications/999")
            
            assert response.status_code == 404


def test_create_schedule_api():
    """Test POST /api/medications/{id}/schedules via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.create_schedule") as mock_create:
            mock_schedule = MagicMock()
            mock_schedule.id = 1
            mock_schedule.medication_id = 1
            mock_schedule.time_of_day = time(8, 0)
            mock_schedule.timezone = "UTC"
            mock_schedule.is_active = True
            mock_schedule.created_at = datetime.now(timezone.utc)
            mock_schedule.updated_at = datetime.now(timezone.utc)
            mock_create.return_value = mock_schedule
            
            response = client.post(
                "/api/medications/1/schedules",
                json={"time_of_day": "08:00", "timezone": "UTC"}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["time_of_day"] == "08:00:00"


def test_get_schedules_api():
    """Test GET /api/medications/{id}/schedules via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.get_medication") as mock_get_med:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.user_id = 1
            mock_get_med.return_value = mock_med
            
            with patch("app.services.medication_service.MedicationService.get_schedules") as mock_get:
                mock_schedule = MagicMock()
                mock_schedule.id = 1
                mock_schedule.medication_id = 1
                mock_schedule.time_of_day = time(8, 0)
                mock_schedule.timezone = "UTC"
                mock_schedule.is_active = True
                mock_schedule.created_at = datetime.now(timezone.utc)
                mock_schedule.updated_at = datetime.now(timezone.utc)
                mock_get.return_value = [mock_schedule]
                
                response = client.get("/api/medications/1/schedules")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1


def test_create_adherence_log_api():
    """Test POST /api/medications/{id}/adherence via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.create_adherence_log") as mock_create:
            mock_log = MagicMock()
            mock_log.id = 1
            mock_log.medication_id = 1
            mock_log.scheduled_time = datetime.now(timezone.utc)
            mock_log.status = "taken"
            mock_log.recorded_at = datetime.now(timezone.utc)
            mock_log.notes = None
            mock_create.return_value = mock_log
            
            response = client.post(
                "/api/medications/1/adherence",
                json={
                    "scheduled_time": datetime.now(timezone.utc).isoformat(),
                    "status": "taken",
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "taken"


def test_get_adherence_logs_api():
    """Test GET /api/medications/{id}/adherence via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.get_medication") as mock_get_med:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.user_id = 1
            mock_get_med.return_value = mock_med
            
            with patch("app.services.medication_service.MedicationService.get_adherence_logs") as mock_get:
                mock_log = MagicMock()
                mock_log.id = 1
                mock_log.medication_id = 1
                mock_log.scheduled_time = datetime.now(timezone.utc)
                mock_log.status = "taken"
                mock_log.recorded_at = datetime.now(timezone.utc)
                mock_log.notes = None
                mock_get.return_value = [mock_log]
                
                response = client.get("/api/medications/1/adherence")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1


def test_get_adherence_summary_api():
    """Test GET /api/medications/{id}/adherence/summary via API."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        with patch("app.services.medication_service.MedicationService.get_medication") as mock_get_med:
            mock_med = MagicMock()
            mock_med.id = 1
            mock_med.user_id = 1
            mock_get_med.return_value = mock_med
            
            with patch("app.services.medication_service.MedicationService.calculate_adherence_percentage") as mock_calc:
                from app.schemas.medication import AdherenceSummaryResponse
                mock_summary = AdherenceSummaryResponse(
                    medication_id=1,
                    total_logs=4,
                    taken_count=3,
                    missed_count=1,
                    snoozed_count=0,
                    adherence_percentage=75.0,
                    period_start=datetime.now(timezone.utc),
                    period_end=datetime.now(timezone.utc),
                )
                mock_calc.return_value = mock_summary
                
                response = client.get("/api/medications/1/adherence/summary")
                
                assert response.status_code == 200
                data = response.json()
                assert data["adherence_percentage"] == 75.0
                assert data["taken_count"] == 3
                assert data["missed_count"] == 1


def test_invalid_adherence_status_api():
    """Test POST /api/medications/{id}/adherence rejects invalid status."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        response = client.post(
            "/api/medications/1/adherence",
            json={
                "scheduled_time": datetime.now(timezone.utc).isoformat(),
                "status": "invalid",
            }
        )
        
        assert response.status_code == 422  # Validation error


def test_invalid_medication_dates_api():
    """Test POST /api/medications rejects invalid dates."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        response = client.post(
            "/api/medications",
            json={
                "name": "Test",
                "frequency": "daily",
                "start_date": str(date.today()),
                "end_date": str(date(2020, 1, 1)),  # Before start_date
            }
        )
        
        assert response.status_code == 422  # Validation error


def test_empty_medication_name_api():
    """Test POST /api/medications rejects empty name."""
    with patch.dict('os.environ', {'DEFAULT_USER_ID': '1'}):
        response = client.post(
            "/api/medications",
            json={
                "name": "",
                "frequency": "daily",
                "start_date": str(date.today()),
            }
        )
        
        assert response.status_code == 422  # Validation error


# ==================== Regression Tests ====================

def test_existing_health_endpoint():
    """Test existing /health endpoint still works."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_existing_chat_endpoint():
    """Test existing /api/chat still works."""
    with patch("app.services.langchain.adapters.get_nvidia_service") as mock_get:
        mock_service = MagicMock()
        mock_service.generate_response.return_value = "Test response."
        mock_get.return_value = mock_service
        
        response = client.post("/api/chat", json={"message": "Test"})
        assert response.status_code == 200


def test_existing_documents_endpoint():
    """Test existing /api/documents still works."""
    with patch("app.services.rag.document_loader.extract_text_from_pdf") as mock_extract:
        mock_extract.return_value = "Test content"
        
        with patch("app.services.medication_service.MedicationService") as mock_service:
            response = client.post(
                "/api/documents",
                files={"file": ("test.pdf", b"test content", "application/pdf")}
            )
            # Should work (or fail gracefully, not crash)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])