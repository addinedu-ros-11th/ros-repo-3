"""Import all models so they register with Base.metadata."""

from app.models.user import User  # noqa: F401
from app.models.robot import Robot, RobotStateCurrent  # noqa: F401
from app.models.poi import Poi  # noqa: F401
from app.models.store import Store  # noqa: F401
from app.models.product import Product, InventoryCurrent  # noqa: F401
from app.models.session import Session  # noqa: F401
from app.models.mission import Mission  # noqa: F401
from app.models.guide import GuideQueueItem  # noqa: F401
from app.models.pickup import PickupOrder, PickupOrderItem  # noqa: F401
from app.models.lockbox import (  # noqa: F401
    LockboxSlot,
    LockboxAssignment,
    LockboxToken,
    LockboxOpenLog,
)
from app.models.shopping import ShoppingList, ShoppingListItem  # noqa: F401
from app.models.zone import RestrictedZone, NavRuleZone  # noqa: F401
from app.models.event import RobotEvent  # noqa: F401
from app.models.charger import ChargerCurrent  # noqa: F401
from app.models.congestion import CongestionCurrent  # noqa: F401

# from .enums import RobotMode, SessionStatus, SessionType
# from .robot import Robot
# from .session import Session

# __all__ = [
#     'RobotMode',
#     'SessionStatus', 
#     'SessionType',
#     'Robot',
#     'Session'
# ]