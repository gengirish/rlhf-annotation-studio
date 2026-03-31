"""One-off: promote gen.girish@gmail.com to admin."""
import asyncio

from sqlalchemy import text

from app.db import engine


async def main():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE annotators SET role = 'admin' WHERE email = 'gen.girish@gmail.com' RETURNING id, name, email, role")
        )
        row = result.fetchone()
        if row:
            print(f"PROMOTED: {row.name} ({row.email}) -> role={row.role}")
        else:
            print("NOT FOUND: gen.girish@gmail.com")
    await engine.dispose()


asyncio.run(main())
