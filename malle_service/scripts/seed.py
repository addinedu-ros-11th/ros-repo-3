#!/usr/bin/env python3
"""
Seed script: Populate the Mall-E database with demo data.

Usage:
    cd malle_service
    python -m scripts.seed

Requires DB_URL in config/.env or environment variable.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine, async_session, Base
from app.models import *  # noqa: register all models
from app.models.user import User
from app.models.robot import Robot, RobotStateCurrent, RobotMode, RobotMotionState, RobotNavState, RobotStopState
from app.models.poi import Poi, PoiType, PoiArrivalConfirm
from app.models.store import Store
from app.models.product import Product
from app.models.lockbox import LockboxSlot, LockboxSlotStatus
from app.models.zone import RestrictedZone
from app.models.congestion import CongestionCurrent, CongestionLevel
from app.models.charger import ChargerCurrent, ChargerStatus


async def seed():
    print("🌱 Seeding Mall-E database...")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Tables created")

    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        if count and count > 0:
            print("  ⚠ Database already has data. Skipping seed.")
            print("  To re-seed, truncate tables first.")
            return

        # --- Users ---
        users = [
            User(id=1, phone="+1-555-123-4567"),
            User(id=2, phone="+82-10-1234-5678"),
        ]
        db.add_all(users)
        await db.flush()
        print("  ✓ Users: 2")

        # --- POIs ---
        pois = [
            # Stores
            Poi(id=1,  name="Zara",              type=PoiType.STORE,   x_m=40.0,  y_m=90.0,  wait_x_m=38.0,  wait_y_m=88.0),
            Poi(id=2,  name="Nike",              type=PoiType.STORE,   x_m=280.0, y_m=80.0,  wait_x_m=278.0, wait_y_m=78.0),
            Poi(id=3,  name="Apple",             type=PoiType.STORE,   x_m=160.0, y_m=30.0,  wait_x_m=158.0, wait_y_m=28.0),
            Poi(id=4,  name="Starbucks",         type=PoiType.STORE,   x_m=120.0, y_m=150.0, wait_x_m=118.0, wait_y_m=148.0),
            Poi(id=5,  name="H&M",               type=PoiType.STORE,   x_m=220.0, y_m=120.0, wait_x_m=218.0, wait_y_m=118.0),
            Poi(id=6,  name="Intersport",        type=PoiType.STORE,   x_m=300.0, y_m=140.0, wait_x_m=298.0, wait_y_m=138.0),
            Poi(id=7,  name="SportyStyle",       type=PoiType.STORE,   x_m=60.0,  y_m=150.0, wait_x_m=58.0,  wait_y_m=148.0),
            Poi(id=8,  name="ProGym Equipment",  type=PoiType.STORE,   x_m=200.0, y_m=40.0,  wait_x_m=198.0, wait_y_m=38.0),
            # Facilities
            Poi(id=9,  name="Main Station",      type=PoiType.STATION, x_m=350.0, y_m=300.0, approach_x_m=348.0, approach_y_m=298.0),
            Poi(id=10, name="Charger Bay A",     type=PoiType.CHARGER, x_m=355.0, y_m=305.0, approach_x_m=353.0, approach_y_m=303.0),
            Poi(id=11, name="Charger Bay B",     type=PoiType.CHARGER, x_m=360.0, y_m=305.0, approach_x_m=358.0, approach_y_m=303.0),
            Poi(id=12, name="Restroom",          type=PoiType.FACILITY,x_m=100.0, y_m=200.0),
            Poi(id=13, name="Info Desk",         type=PoiType.FACILITY,x_m=180.0, y_m=180.0),
            Poi(id=14, name="Lounge Area",       type=PoiType.LOUNGE,  x_m=250.0, y_m=200.0),
        ]
        db.add_all(pois)
        await db.flush()
        print(f"  ✓ POIs: {len(pois)}")

        # --- Stores ---
        stores = [
            Store(id=1, poi_id=1,  category="fashion"),
            Store(id=2, poi_id=2,  category="sports"),
            Store(id=3, poi_id=3,  category="electronics"),
            Store(id=4, poi_id=4,  category="cafe"),
            Store(id=5, poi_id=5,  category="fashion"),
            Store(id=6, poi_id=6,  category="sports"),
            Store(id=7, poi_id=7,  category="fashion"),
            Store(id=8, poi_id=8,  category="fitness"),
        ]
        db.add_all(stores)
        await db.flush()
        print(f"  ✓ Stores: {len(stores)}")

        # --- Products ---
        products = [
            # Zara (store_id=1)
            Product(store_id=1, name="Linen Blend Shirt",   price=45.90, sku="ZARA-001"),
            Product(store_id=1, name="Pleated Trousers",    price=59.90, sku="ZARA-002"),
            Product(store_id=1, name="Cotton Jacket",       price=89.90, sku="ZARA-003"),
            # Nike (store_id=2)
            Product(store_id=2, name="Air Zoom Pegasus",    price=120.00, sku="NIKE-001"),
            Product(store_id=2, name="Running Socks (3pk)", price=18.00,  sku="NIKE-002"),
            Product(store_id=2, name="Dri-FIT Headband",    price=12.00,  sku="NIKE-003"),
            Product(store_id=2, name="Training Shorts",     price=35.00,  sku="NIKE-004"),
            # Apple (store_id=3)
            Product(store_id=3, name="USB-C Charge Cable",  price=19.00, sku="AAPL-001"),
            Product(store_id=3, name="AirPods Pro",         price=249.00, sku="AAPL-002"),
            Product(store_id=3, name="iPhone Case",         price=49.00,  sku="AAPL-003"),
            # Starbucks (store_id=4)
            Product(store_id=4, name="Tumbler",             price=24.00, sku="SBUX-001"),
            Product(store_id=4, name="Iced Americano",      price=5.50,  sku="SBUX-002"),
            # H&M (store_id=5)
            Product(store_id=5, name="Basic T-Shirt",       price=9.99,  sku="HM-001"),
            Product(store_id=5, name="Slim Fit Jeans",      price=29.99, sku="HM-002"),
            # Intersport (store_id=6)
            Product(store_id=6, name="Yoga Mat",            price=25.00, sku="ISPT-001"),
            Product(store_id=6, name="Tennis Racket",       price=89.00, sku="ISPT-002"),
            # SportyStyle (store_id=7)
            Product(store_id=7, name="Athletic Hoodie",     price=55.00, sku="SS-001"),
            # ProGym (store_id=8)
            Product(store_id=8, name="Resistance Bands",    price=15.00, sku="PG-001"),
            Product(store_id=8, name="Foam Roller",         price=22.00, sku="PG-002"),
        ]
        db.add_all(products)
        await db.flush()
        print(f"  ✓ Products: {len(products)}")

        # --- Robots ---
        now = datetime.utcnow()
        robots = [
            Robot(id=1, name="PinkyPro-1", model="PinkyPro", is_online=True,  battery_pct=82, current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
            Robot(id=2, name="PinkyPro-2", model="PinkyPro", is_online=True,  battery_pct=65, current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
            Robot(id=3, name="PinkyPro-3", model="PinkyPro", is_online=True,  battery_pct=98, current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
            Robot(id=4, name="BigPinky-1", model="BigPinky", is_online=True,  battery_pct=45, current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
            Robot(id=5, name="PinkyPro-4", model="PinkyPro", is_online=False, battery_pct=5,  current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
            Robot(id=6, name="PinkyPro-5", model="PinkyPro", is_online=True,  battery_pct=14, current_mode=RobotMode.IDLE, last_seen_at=now, home_poi_id=9),
        ]
        db.add_all(robots)
        await db.flush()
        print(f"  ✓ Robots: {len(robots)}")

        # --- Robot State ---
        robot_states = [
            RobotStateCurrent(robot_id=1, x_m=120.0, y_m=80.0,  motion_state=RobotMotionState.STOPPED, updated_at=now),
            RobotStateCurrent(robot_id=2, x_m=200.0, y_m=150.0, motion_state=RobotMotionState.STOPPED, updated_at=now),
            RobotStateCurrent(robot_id=3, x_m=60.0,  y_m=200.0, motion_state=RobotMotionState.STOPPED, updated_at=now),
            RobotStateCurrent(robot_id=4, x_m=300.0, y_m=120.0, motion_state=RobotMotionState.STOPPED, updated_at=now),
            RobotStateCurrent(robot_id=5, x_m=350.0, y_m=300.0, motion_state=RobotMotionState.STOPPED, updated_at=now),
            RobotStateCurrent(robot_id=6, x_m=180.0, y_m=250.0, motion_state=RobotMotionState.STOPPED, updated_at=now),
        ]
        db.add_all(robot_states)
        await db.flush()
        print(f"  ✓ Robot states: {len(robot_states)}")

        # --- Lockbox Slots (5 per robot) ---
        lockbox_slots = []
        for robot in robots:
            for slot_no in range(1, 6):
                lockbox_slots.append(LockboxSlot(
                    robot_id=robot.id,
                    slot_no=slot_no,
                    status=LockboxSlotStatus.EMPTY,
                    size_label="M" if slot_no <= 3 else "L",
                ))
        db.add_all(lockbox_slots)
        await db.flush()
        print(f"  ✓ Lockbox slots: {len(lockbox_slots)}")

        # --- Restricted Zones ---
        zones = [
            RestrictedZone(
                name="North Corridor",
                polygon_wkt="POLYGON((50 30, 250 30, 250 80, 50 80, 50 30))",
                is_active=True,
            ),
            RestrictedZone(
                name="Food Court Area",
                polygon_wkt="POLYGON((320 270, 400 270, 400 340, 320 340, 320 270))",
                is_active=True,
            ),
            RestrictedZone(
                name="West Wing",
                polygon_wkt="POLYGON((150 200, 280 200, 280 280, 150 280, 150 200))",
                is_active=False,
            ),
        ]
        db.add_all(zones)
        await db.flush()
        print(f"  ✓ Restricted zones: {len(zones)}")

        # --- Chargers ---
        chargers = [
            ChargerCurrent(charger_poi_id=10, status=ChargerStatus.FREE, updated_at=now),
            ChargerCurrent(charger_poi_id=11, status=ChargerStatus.FREE, updated_at=now),
        ]
        db.add_all(chargers)
        await db.flush()
        print(f"  ✓ Chargers: {len(chargers)}")

        # --- Congestion ---
        congestions = [
            CongestionCurrent(poi_id=1, level=CongestionLevel.LOW, updated_at=now),
            CongestionCurrent(poi_id=4, level=CongestionLevel.MID, updated_at=now),
            CongestionCurrent(poi_id=5, level=CongestionLevel.HIGH, updated_at=now),
        ]
        db.add_all(congestions)
        await db.flush()
        print(f"  ✓ Congestion: {len(congestions)}")

        await db.commit()

    print("\n✅ Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
