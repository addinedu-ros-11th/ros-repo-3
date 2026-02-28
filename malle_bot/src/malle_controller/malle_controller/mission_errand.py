#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from enum import Enum, auto

from malle_controller.nav_core import NavCore
from malle_controller.api_client import ApiClient
from malle_controller.poi_manager import PoiManager
from malle_controller.pid_edges import PID_EDGES, PID_DESTINATIONS, DEFAULT_PID_RADIUS

class ErrandState(Enum):
    IDLE         = auto()
    GO_STORE     = auto()
    BOX_EMPTY    = auto()
    GO_MEETUP    = auto()
    BOX_FULL     = auto()
    DONE         = auto()

class MissionErrandNode(Node, NavCore):

    def __init__(self):
        Node.__init__(self, 'mission_errand')
        self.nav_core_init(self)

        self._api = ApiClient(
            base_url=self.declare_parameter('api_base_url', 'http://localhost:8000').value,
            logger=self.get_logger(),
        )
        self._poi_mgr = PoiManager(self._api, logger=self.get_logger())
        self._poi_mgr.load()

        self.trigger_sub  = self.create_subscription(
            String, '/malle/mission_trigger', self._on_trigger, 10)
        self.lockbox_sub  = self.create_subscription(
            String, '/malle/lockbox_status', self._on_lockbox, 10)
        self.result_pub   = self.create_publisher(String, '/malle/mission_result', 10)
        self.lockbox_pub  = self.create_publisher(String, '/malle/lockbox_cmd', 10)

        self._state      = ErrandState.IDLE
        self._store_poi  = ''
        self._meetup_poi = ''
        self._prev_poi_id = ''

        self.get_logger().info('[MissionErrand] 준비 완료')

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token.startswith('start_errand:'):
            parts = token.split(':', 1)[1].split(',')
            self._store_poi  = parts[0] if len(parts) > 0 else ''
            self._meetup_poi = parts[1] if len(parts) > 1 else ''
            self._transition(ErrandState.GO_STORE)
        elif token == 'idle':
            self._transition(ErrandState.IDLE)

    def _on_lockbox(self, msg: String):
        status = msg.data.strip().lower()
        if status == 'loaded' and self._state == ErrandState.BOX_EMPTY:
            self._publish_result('box_loaded')
            self._transition(ErrandState.GO_MEETUP)
        elif status == 'delivered' and self._state == ErrandState.BOX_FULL:
            self._publish_result('errand_done')
            self._transition(ErrandState.DONE)

    def _transition(self, new_state: ErrandState):
        self.get_logger().info(
            f'[MissionErrand] {self._state.name} → {new_state.name}')
        self._state = new_state

        if new_state == ErrandState.GO_STORE:
            self._go_to_poi(self._store_poi, self._on_store_arrived)

        elif new_state == ErrandState.BOX_EMPTY:
            self._publish_result('arrived_store')
            self._open_box()

        elif new_state == ErrandState.GO_MEETUP:
            self._go_to_poi(self._meetup_poi, self._on_meetup_arrived)

        elif new_state == ErrandState.BOX_FULL:
            # TODO: 사용자 인증 대기 (QR / 앱 확인)
            pass

        elif new_state == ErrandState.DONE:
            self.cmd_vel(0.0, 0.0)

        elif new_state == ErrandState.IDLE:
            self.cancel_navigation()
            self.cmd_vel(0.0, 0.0)

    def _go_to_poi(self, poi_id: str, done_cb):
        poi = self._poi_mgr.get(poi_id)
        if poi is None:
            self.get_logger().error(f'[MissionErrand] POI 없음: {poi_id}')
            self._publish_result('exception')
            return
        edge = (self._prev_poi_id, poi_id)
        pid_radius = PID_EDGES.get(edge, PID_DESTINATIONS.get(poi_id, DEFAULT_PID_RADIUS))
        self._prev_poi_id = poi_id
        self.navigate_to_pose(poi['x'], poi['y'], poi.get('yaw', 0.0),
                              done_callback=done_cb,
                              pid_zone_radius=pid_radius)

    def _on_store_arrived(self, success: bool):
        if success:
            self._transition(ErrandState.BOX_EMPTY)
        else:
            self.get_logger().warn('[MissionErrand] 매장 이동 실패')
            self._publish_result('exception')

    def _on_meetup_arrived(self, success: bool):
        if success:
            self._transition(ErrandState.BOX_FULL)
            self._publish_result('user_auth_done')   # TODO: 실제 인증 후 전송
        else:
            self.get_logger().warn('[MissionErrand] meet-up 이동 실패')
            self._publish_result('exception')

    def _open_box(self):
        msg = String()
        msg.data = 'open'
        self.lockbox_pub.publish(msg)

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)


def main():
    rclpy.init()
    node = MissionErrandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
