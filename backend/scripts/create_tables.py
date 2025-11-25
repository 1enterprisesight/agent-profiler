"""
Create all database tables from SQLAlchemy models
Run this once to initialize the database schema
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, Base
from app.models import *  # Import all models to register them


async def create_all_tables():
    """Create all tables defined in models.py"""
    print("Creating database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✓ All tables created successfully")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_all_tables())
