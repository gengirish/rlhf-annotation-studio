import asyncio; from sqlalchemy import text; from app.db import get_engine
async def m():
  e=get_engine()
  async with e.begin() as c:
    r=await c.execute(text("UPDATE annotators SET role='admin' WHERE email='gen.girish@gmail.com' RETURNING name,email,role"))
    print(r.fetchone())
  await e.dispose()
asyncio.run(m())
