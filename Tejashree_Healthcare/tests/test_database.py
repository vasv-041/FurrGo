"""
tests/test_database.py

Test database connectivity and model creation.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User

# Use an in-memory SQLite database for testing to ensure isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    yield session
    
    session.close()
    # Drop tables after test is done
    Base.metadata.drop_all(bind=engine)


def test_database_connection_and_table_creation(db_session):
    """If db_session fixture doesn't fail, connection and table creation work."""
    # The setup of the fixture creates the tables, so just passing confirms it works
    assert True


def test_create_and_retrieve_user(db_session):
    """Verify that a User can be inserted and then retrieved."""
    # Create new user
    new_user = User()
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)

    # Make sure ID was generated
    assert new_user.id is not None
    assert new_user.created_at is not None
    assert new_user.updated_at is not None

    # Retrieve user
    retrieved_user = db_session.query(User).filter(User.id == new_user.id).first()
    
    assert retrieved_user is not None
    assert retrieved_user.id == new_user.id
