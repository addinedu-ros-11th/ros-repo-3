#!/usr/bin/env python3
"""
pid_lock zone 3개만 DB에 추가.

Usage:
    cd malle_service
    python -m scripts.seed_pid_zones
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, async_session

PID_ZONES = [
    ("pid_lock_p4", "RESTRICTED", "HIGH", False, "POLYGON((1.0 -0.23, 2.06 -0.23, 2.06 0.83, 1.0 0.83, 1.0 -0.23))"),
    ("pid_lock_p6", "RESTRICTED", "HIGH", False, "POLYGON((2.98 0.98, 4.02 0.98, 4.02 2.02, 2.98 2.02, 2.98 0.98))"),
    ("pid_lock_p8", "RESTRICTED", "HIGH", False, "POLYGON((2.80 1.50, 4.20 1.50, 4.20 2.90, 2.80 2.90, 2.80 1.50))"),
]


async def main():
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    async with async_session() as db:
        for name, ztype, priority, is_active, wkt in PID_ZONES:
            result = await db.execute(
                text("SELECT id FROM zones WHERE name = :name"),
                {"name": name},
            )
            if result.scalar():
                print(f"  [SKIP] {name} — 이미 존재")
                continue

            await db.execute(text(
                "INSERT INTO zones "
                "(name, zone_type, priority, is_active, speed_limit_mps, one_way, enhanced_avoidance, "
                " polygon, updated_by_source, updated_at, created_at) "
                "VALUES (:name, :ztype, :priority, :is_active, NULL, NULL, NULL, "
                "        ST_GeomFromText(:wkt), 'seed', :now, :now)"
            ), {"name": name, "ztype": ztype, "priority": priority,
                "is_active": is_active, "wkt": wkt, "now": now_str})
            print(f"  [OK] {name} 추가됨")

        await db.commit()

    print("완료.")


if __name__ == "__main__":
    asyncio.run(main())
