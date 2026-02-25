#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from collections import deque

from malle_controller.nav_core import NavCore
from malle_controller.api_client import ApiClient
from malle_controller.poi_manager import PoiManager


class MissionGuideNode(Node, NavCore):

    def __init__(self):
        Node.__init__(self, 'mission_guide')
        self.nav_core_init(self)

        self._api = ApiClient(
            base_url=self.declare_parameter('api_base_url', 'http://localhost:8000').value,
            logger=self.get_logger(),
        )
        self._poi_mgr = PoiManager(self._api, logger=self.get_logger())
        self._poi_mgr.load()

        self.trigger_sub = self.create_subscription(
            String, '/malle/mission_trigger', self._on_trigger, 10)
        self.result_pub  = self.create_publisher(String, '/malle/mission_result', 10)

        self._active    = False
        self._poi_queue: deque[str] = deque()

        self.get_logger().info('[MissionGuide] 준비 완료')

    def _on_trigger(self, msg: String):
        token = msg.data.strip()
        if token.startswith('start_guide:'):
            # 포맷: "start_guide:poi1,poi2,poi3"
            poi_ids = token.split(':', 1)[1].split(',')
            self._start(poi_ids)
        elif token == 'stop_guide' or token == 'idle':
            self._stop()

    def _start(self, poi_ids: list[str]):
        self._poi_queue = deque(poi_ids)
        self._active = True
        self.get_logger().info(f'[MissionGuide] 시작 – POI 큐: {list(self._poi_queue)}')
        self._navigate_next()

    def _stop(self):
        self._active = False
        self.cancel_navigation()
        self.stop()
        self.get_logger().info('[MissionGuide] 중지')

    def _navigate_next(self):
        if not self._active or not self._poi_queue:
            self._publish_result('guide_done')
            return

        poi_id = self._poi_queue.popleft()
        poi    = self._poi_mgr.get(poi_id)
        if poi is None:
            self.get_logger().warn(f'[MissionGuide] 알 수 없는 POI: {poi_id}, 건너뜀')
            self._navigate_next()
            return

        self.get_logger().info(f'[MissionGuide] → {poi_id} ({poi["name"]})')
        self.navigate_to_pose(
            x=poi['x'], y=poi['y'], yaw=poi.get('yaw', 0.0),
            done_callback=self._on_nav_done,
        )

    def _on_nav_done(self, future):
        result = future.result().result
        status = future.result().status
        # action_msgs/GoalStatus: SUCCEEDED = 4
        if status == 4:
            self.get_logger().info('[MissionGuide] POI 도착')
            # TODO: 도착 후 동작
            self._navigate_next()
        else:
            self.get_logger().warn(f'[MissionGuide] 이동 실패 (status={status})')
            self._publish_result('exception')

    def _publish_result(self, result: str):
        msg = String()
        msg.data = result
        self.result_pub.publish(msg)


def main():
    rclpy.init()
    node = MissionGuideNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
