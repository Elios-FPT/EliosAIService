"""Quick verification script for Phase 1 tables."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def verify_tables():
    """Verify prompt management tables exist."""
    engine = create_async_engine(os.getenv('DATABASE_URL'))

    async with engine.connect() as conn:
        # Check tables
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname='public' AND tablename LIKE 'prompt%'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]

        print("✅ Phase 1 Tables Created:")
        for table in tables:
            print(f"  - {table}")

        # Check seed data
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM prompt_templates WHERE created_by = 'system'
        """))
        count = result.fetchone()[0]
        print(f"\n✅ Seed Data: {count} system prompts inserted")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify_tables())
