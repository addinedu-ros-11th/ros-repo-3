#!/usr/bin/env python3
"""
test_pid_zone_lock.py — PID zone lock 단위 테스트 (ROS / 서버 없이 실행)

실행:
    cd malle_bot/src/malle_controller/test
    python test_pid_zone_lock.py
"""

import os
import sys
import threading
import types
import unittest
from collections import deque
from unittest.mock import MagicMock, call

# ── ROS / 서드파티 모킹 ──────────────────────────────────────────────────────

def _stub_module(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    sys.modules.setdefault(name, m)
    return sys.modules[name]

for _n in [
    'rclpy', 'rclpy.node',
    'std_msgs', 'std_msgs.msg',
    'nav_msgs', 'nav_msgs.msg',
    'builtin_interfaces', 'builtin_interfaces.msg',
    'yaml', 'websockets', 'httpx',
]:
    _stub_module(_n)


class _FakeNode:
    """rclpy.node.Node 스텁 — MRO 충돌 없이 상속 가능."""
    pass

sys.modules['rclpy.node'].Node = _FakeNode
sys.modules['std_msgs.msg'].String = MagicMock()

# ── malle_controller 패키지 경로 ─────────────────────────────────────────────
_TEST_DIR  = os.path.dirname(os.path.abspath(__file__))
_CTRL_ROOT = os.path.normpath(os.path.join(_TEST_DIR, '..'))
if _CTRL_ROOT not in sys.path:
    sys.path.insert(0, _CTRL_ROOT)

# nav_core 모킹
_nav_core_mod = types.ModuleType('malle_controller.nav_core')

class _StubNavCore:
    def nav_core_init(self, node):      pass
    def navigate_via_waypoints(self, **kwargs): pass
    def cancel_navigation(self):        pass
    def cmd_vel(self, linear, angular): pass

_nav_core_mod.NavCore = _StubNavCore
sys.modules['malle_controller.nav_core'] = _nav_core_mod

_poi_mgr_mod = types.ModuleType('malle_controller.poi_manager')
_poi_mgr_mod.PoiManager = MagicMock
sys.modules['malle_controller.poi_manager'] = _poi_mgr_mod

# ── 실제 모듈 임포트 ─────────────────────────────────────────────────────────
from malle_controller.api_client import ApiClient          # noqa: E402
from malle_controller.mission_guide import GuideExecutor   # noqa: E402
import malle_controller.mission_guide as _mg              # noqa: E402


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _make_executor() -> GuideExecutor:
    node = MagicMock()
    node.get_logger.return_value = MagicMock()
    api     = MagicMock(spec=ApiClient)
    poi_mgr = MagicMock()
    return GuideExecutor(node=node, api=api, poi_mgr=poi_mgr)


# ─────────────────────────────────────────────────────────────────────────────
# 1. ApiClient.find_pid_lock_zone_id
# ─────────────────────────────────────────────────────────────────────────────

class TestFindPidLockZoneId(unittest.TestCase):

    def _client(self, zones=None, exc=None) -> ApiClient:
        c = ApiClient(base_url='http://test', logger=MagicMock())
        if exc:
            c.get = MagicMock(side_effect=exc)
        else:
            c.get = MagicMock(return_value=zones or [])
        return c

    def test_returns_id_when_zone_found(self):
        c = self._client([
            {'id': 42, 'name': 'pid_lock_p4', 'zone_type': 'RESTRICTED'},
        ])
        self.assertEqual(c.find_pid_lock_zone_id('p4'), 42)

    def test_returns_none_when_not_found(self):
        c = self._client([{'id': 1, 'name': 'other_zone'}])
        self.assertIsNone(c.find_pid_lock_zone_id('p4'))

    def test_returns_none_on_exception(self):
        c = self._client(exc=RuntimeError('network error'))
        self.assertIsNone(c.find_pid_lock_zone_id('p4'))

    def test_caches_result(self):
        """두 번째 호출은 GET /zones 없이 캐시에서 반환."""
        c = self._client([{'id': 7, 'name': 'pid_lock_p6'}])
        c.find_pid_lock_zone_id('p6')
        c.find_pid_lock_zone_id('p6')
        self.assertEqual(c.get.call_count, 1)

    def test_cached_value_correct(self):
        c = self._client([{'id': 99, 'name': 'pid_lock_p8'}])
        first  = c.find_pid_lock_zone_id('p8')
        second = c.find_pid_lock_zone_id('p8')
        self.assertEqual(first, second)
        self.assertEqual(second, 99)

    def test_different_poi_ids_independent(self):
        c = self._client([
            {'id': 10, 'name': 'pid_lock_p4'},
            {'id': 20, 'name': 'pid_lock_p6'},
        ])
        self.assertEqual(c.find_pid_lock_zone_id('p4'), 10)
        self.assertEqual(c.find_pid_lock_zone_id('p6'), 20)

    def test_cache_not_polluted_by_failed_lookup(self):
        """GET 실패 시 캐시에 아무것도 저장되지 않아야 한다."""
        c = self._client(exc=RuntimeError('fail'))
        c.find_pid_lock_zone_id('p4')
        self.assertNotIn('p4', c._pid_zone_cache)


# ─────────────────────────────────────────────────────────────────────────────
# 2. ApiClient.set_zone_active
# ─────────────────────────────────────────────────────────────────────────────

class TestSetZoneActive(unittest.TestCase):

    def _client(self, exc=None) -> ApiClient:
        c = ApiClient(base_url='http://test', logger=MagicMock())
        c.patch = MagicMock(side_effect=exc) if exc \
                  else MagicMock(return_value={'ok': True})
        return c

    def test_patches_correct_path_activate(self):
        c = self._client()
        c.set_zone_active(42, True)
        path = c.patch.call_args[0][0]
        self.assertEqual(path, '/zones/42')

    def test_patches_is_active_true(self):
        c = self._client()
        c.set_zone_active(42, True)
        body = c.patch.call_args[0][1]
        self.assertIs(body['is_active'], True)

    def test_patches_is_active_false(self):
        c = self._client()
        c.set_zone_active(42, False)
        body = c.patch.call_args[0][1]
        self.assertIs(body['is_active'], False)

    def test_does_not_raise_on_exception(self):
        c = self._client(exc=RuntimeError('server down'))
        try:
            c.set_zone_active(1, True)
        except Exception:
            self.fail('set_zone_active 이 예외를 전파함')


# ─────────────────────────────────────────────────────────────────────────────
# 3. GuideExecutor 초기 상태
# ─────────────────────────────────────────────────────────────────────────────

class TestGuideExecutorInit(unittest.TestCase):

    def test_locked_zone_id_starts_none(self):
        self.assertIsNone(_make_executor()._locked_zone_id)

    def test_api_client_cache_starts_empty(self):
        """ApiClient 직접 생성 시 캐시가 비어 있어야 한다."""
        c = ApiClient(base_url='http://test')
        self.assertEqual(c._pid_zone_cache, {})


# ─────────────────────────────────────────────────────────────────────────────
# 4. _release_zone_lock
# ─────────────────────────────────────────────────────────────────────────────

class TestReleaseZoneLock(unittest.TestCase):

    def test_deactivates_zone_when_locked(self):
        ex = _make_executor()
        ex._locked_zone_id = 55
        ex._release_zone_lock()
        ex._api.set_zone_active.assert_called_once_with(55, False)

    def test_clears_locked_zone_id_after_release(self):
        ex = _make_executor()
        ex._locked_zone_id = 55
        ex._release_zone_lock()
        self.assertIsNone(ex._locked_zone_id)

    def test_noop_when_not_locked(self):
        ex = _make_executor()
        ex._release_zone_lock()
        ex._api.set_zone_active.assert_not_called()

    def test_thread_safe_multiple_releases(self):
        """여러 스레드 동시 release → set_zone_active(False) 정확히 1회."""
        ex = _make_executor()
        ex._locked_zone_id = 10
        threads = [threading.Thread(target=ex._release_zone_lock) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(ex._api.set_zone_active.call_count, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 5. _navigate_next — zone 활성화
# ─────────────────────────────────────────────────────────────────────────────

class TestNavigateNextZoneLock(unittest.TestCase):

    def setUp(self):
        self._orig_get_pid = _mg.get_pid_radius

    def tearDown(self):
        _mg.get_pid_radius = self._orig_get_pid

    def _executor(self, pid_radius: float, zone_id=77) -> GuideExecutor:
        ex = _make_executor()
        ex._active     = True
        ex._session_id = 1
        ex._prev_poi_id = 'p3'
        ex._queue = deque([{'id': 1, 'poi_id': 'p4', 'poi_name': 'TestPOI'}])
        ex._poi_mgr.get.return_value = {'x_m': 1.0, 'y_m': 2.0}
        ex._api.find_pid_lock_zone_id.return_value = zone_id
        _mg.get_pid_radius = lambda prev, nxt: pid_radius
        return ex

    def test_activates_zone_when_radius_positive(self):
        ex = self._executor(1.03)
        ex._navigate_next()
        ex._api.set_zone_active.assert_called_once_with(77, True)

    def test_zone_id_stored(self):
        ex = self._executor(1.03)
        ex._navigate_next()
        self.assertEqual(ex._locked_zone_id, 77)

    def test_no_activation_when_radius_zero(self):
        ex = self._executor(0.0)
        ex._navigate_next()
        ex._api.set_zone_active.assert_not_called()
        ex._api.find_pid_lock_zone_id.assert_not_called()

    def test_locked_zone_id_none_when_zone_not_found(self):
        ex = self._executor(1.03, zone_id=None)
        ex._navigate_next()
        self.assertIsNone(ex._locked_zone_id)

    def test_no_activation_when_zone_not_found(self):
        """zone DB에 없으면 set_zone_active 호출 안 함."""
        ex = self._executor(1.03, zone_id=None)
        ex._navigate_next()
        ex._api.set_zone_active.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 6. advance / stop — 비활성화 순서 보장
# ─────────────────────────────────────────────────────────────────────────────

class TestZoneLockLifecycle(unittest.TestCase):

    def _waiting_executor(self) -> GuideExecutor:
        ex = _make_executor()
        ex._active         = True
        ex._waiting_at_poi = True
        ex._session_id     = 1
        ex._current_item   = {'id': 10}
        ex._locked_zone_id = 88
        ex._queue          = deque()
        ex._api.update_guide_item.return_value = {}
        return ex

    def test_advance_deactivates_zone(self):
        ex = self._waiting_executor()
        ex.advance()
        ex._api.set_zone_active.assert_called_once_with(88, False)

    def test_advance_deactivate_before_navigate(self):
        """set_zone_active(False) → _navigate_next 순서 보장."""
        ex = self._waiting_executor()
        call_order = []
        ex._api.set_zone_active.side_effect = lambda zid, a: call_order.append('deactivate')
        orig_nn = GuideExecutor._navigate_next
        GuideExecutor._navigate_next = lambda self_: call_order.append('navigate')
        try:
            ex.advance()
        finally:
            GuideExecutor._navigate_next = orig_nn
        self.assertEqual(call_order, ['deactivate', 'navigate'])

    def test_advance_clears_locked_zone_id(self):
        ex = self._waiting_executor()
        ex.advance()
        self.assertIsNone(ex._locked_zone_id)

    def test_advance_noop_when_not_waiting(self):
        ex = _make_executor()
        ex._waiting_at_poi = False
        ex._locked_zone_id = 5
        ex.advance()
        ex._api.set_zone_active.assert_not_called()

    def test_stop_deactivates_zone(self):
        ex = _make_executor()
        ex._locked_zone_id = 99
        ex.cancel_navigation = MagicMock()
        ex.stop()
        ex._api.set_zone_active.assert_called_once_with(99, False)

    def test_stop_deactivate_before_cancel(self):
        """set_zone_active(False) → cancel_navigation 순서 보장."""
        ex = _make_executor()
        ex._locked_zone_id = 99
        call_order = []
        ex._api.set_zone_active.side_effect = lambda zid, a: call_order.append('deactivate')
        ex.cancel_navigation = MagicMock(side_effect=lambda: call_order.append('cancel'))
        ex.stop()
        self.assertEqual(call_order, ['deactivate', 'cancel'])

    def test_stop_clears_locked_zone_id(self):
        ex = _make_executor()
        ex._locked_zone_id = 5
        ex.cancel_navigation = MagicMock()
        ex.stop()
        self.assertIsNone(ex._locked_zone_id)

    def test_stop_noop_when_not_locked(self):
        ex = _make_executor()
        ex.cancel_navigation = MagicMock()
        ex.stop()
        ex._api.set_zone_active.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    unittest.main(verbosity=2)
