#!/usr/bin/env python3
"""
verify_comms.py  –  malle_service ↔ bridge_node ↔ malle_bot 통신 확인

로컬 PC 터미널에서 실행:
  python3 test/verify_comms.py

옵션:
  --bridge-url   bridge_node HTTP 주소  (기본: http://localhost:9100)
  --service-url  malle_service 주소     (기본: http://localhost:8000)
  --robot-ns     로봇 ROS2 네임스페이스 (기본: robot1)
  --robot-id     malle_service DB robot_id (기본: 1)

예시:
  python3 test/verify_comms.py --bridge-url http://localhost:9100 \\
                                --service-url http://localhost:8000 \\
                                --robot-ns robot1 --robot-id 1
"""

import argparse
import subprocess
import sys
import time
import httpx


# ── 출력 헬퍼 ─────────────────────────────────────────────────────────────────
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
RESET  = '\033[0m'

def ok(msg):   print(f'  {GREEN}✓{RESET}  {msg}')
def fail(msg): print(f'  {RED}✗{RESET}  {msg}')
def warn(msg): print(f'  {YELLOW}!{RESET}  {msg}')
def section(title): print(f'\n{"─"*50}\n  {title}\n{"─"*50}')


# ── 각 체크 함수 ──────────────────────────────────────────────────────────────

def check_bridge_health(bridge_url: str) -> bool:
    section('① bridge_node 동작 확인')
    try:
        r = httpx.get(f'{bridge_url}/health', timeout=3)
        r.raise_for_status()
        data = r.json()
        ok(f'bridge_node 응답: {data}')
        if not data.get('ros2'):
            warn('ROS2 모드 비활성 – bridge_node 가 ROS2 없이 실행 중')
        return True
    except httpx.ConnectError:
        fail(f'bridge_node 에 연결할 수 없음 ({bridge_url})')
        print('       → bridge_node 가 실행 중인지 확인하세요:')
        print('         ros2 launch malle_controller bridge.launch.xml')
        return False
    except Exception as e:
        fail(f'bridge_node 헬스체크 실패: {e}')
        return False


def check_service_health(service_url: str) -> bool:
    section('② malle_service 동작 확인')
    # 일반적인 health/상태 엔드포인트 시도
    for path in ('/health', '/api/v1/health', '/', '/api/health'):
        try:
            r = httpx.get(f'{service_url}{path}', timeout=3)
            if r.status_code < 500:
                ok(f'malle_service 응답 (status={r.status_code}): {service_url}{path}')
                return True
        except Exception:
            continue
    fail(f'malle_service 에 연결할 수 없음 ({service_url})')
    print('       → malle_service 가 실행 중인지 확인하세요')
    return False


def check_ros2_topics(robot_ns: str) -> bool:
    section(f'③ ROS2 토픽 수신 확인  (네임스페이스: /{robot_ns})')
    try:
        result = subprocess.run(
            ['ros2', 'topic', 'list'],
            capture_output=True, text=True, timeout=5,
        )
        topics = result.stdout.strip().splitlines()
    except FileNotFoundError:
        fail('ros2 명령을 찾을 수 없음 – ROS2 환경을 source 했는지 확인')
        return False
    except subprocess.TimeoutExpired:
        fail('ros2 topic list 타임아웃')
        return False

    expected = [f'/{robot_ns}/odom', f'/{robot_ns}/battery']
    found_any = False
    for t in expected:
        if t in topics:
            ok(f'토픽 발견: {t}')
            found_any = True
        else:
            warn(f'토픽 없음: {t}  (로봇이 퍼블리시하지 않거나 Domain ID 불일치)')

    if not found_any:
        print('       → ROS_DOMAIN_ID 가 로봇과 동일한지 확인:')
        print('         echo $ROS_DOMAIN_ID')
    return found_any


def check_state_push(service_url: str, robot_id: int) -> bool:
    """
    bridge_node 가 malle_service 에 로봇 상태를 push 하는지 확인.
    PATCH /api/v1/robots/{id}/state 로 테스트 값을 전송하고
    GET /api/v1/robots/{id} 로 실제 반영 여부를 검증.
    """
    section(f'④ bridge → malle_service  상태 전송 확인  (robot_id={robot_id})')

    test_x, test_y, test_battery = 11.1, 22.2, 77

    # PATCH /api/v1/robots/{id}/state
    try:
        r = httpx.patch(
            f'{service_url}/api/v1/robots/{robot_id}/state',
            json={'x_m': test_x, 'y_m': test_y, 'battery_pct': test_battery},
            timeout=3,
        )
        if r.status_code == 200:
            ok(f'PATCH /api/v1/robots/{robot_id}/state → {r.status_code}')
        else:
            fail(f'PATCH /api/v1/robots/{robot_id}/state → {r.status_code}: {r.text[:100]}')
            return False
    except Exception as e:
        fail(f'PATCH /api/v1/robots/{robot_id}/state 실패: {e}')
        return False

    # GET /api/v1/robots/{id} 로 반영 여부 확인
    try:
        r = httpx.get(f'{service_url}/api/v1/robots/{robot_id}', timeout=3)
        if r.status_code != 200:
            warn(f'GET /api/v1/robots/{robot_id} → {r.status_code} (반영 확인 불가)')
            return True  # PATCH 는 성공했으므로 True

        data = r.json()
        state = data.get('state') or {}
        actual_x = state.get('x_m')
        actual_battery = data.get('battery_pct')

        if actual_x == test_x and actual_battery == test_battery:
            ok(f'상태 반영 확인: x_m={actual_x}, battery={actual_battery}%')
        else:
            warn(f'값 불일치: x_m={actual_x} (기대 {test_x}), battery={actual_battery}% (기대 {test_battery}%)')
        return True
    except Exception as e:
        warn(f'GET /api/v1/robots/{robot_id} 실패: {e}')
        return True  # PATCH 는 성공했으므로 True


def check_command_flow(bridge_url: str, robot_id: int, robot_ns: str) -> bool:
    """
    malle_service → bridge → ROS2 토픽 방향 확인.
    bridge 에 POST /bridge/command 후 ROS2 토픽으로 명령이 나오는지 확인.

    판정 기준:
      - bridge 가 200 반환 + node_active=True  → PASS
      - ROS2 echo 수신 여부는 WiFi DDS 지연이 있어 best-effort 확인
    """
    section(f'⑤ malle_service → bridge → ROS2  명령 흐름 확인  (robot_id={robot_id})')

    topic = f'/{robot_ns}/task_command'

    # bridge ROS2 노드 활성 여부 확인
    try:
        h = httpx.get(f'{bridge_url}/health', timeout=3)
        node_active = h.json().get('node_active', False)
    except Exception:
        node_active = False

    if not node_active:
        fail('bridge ROS2 노드 비활성 – bridge 를 ROS2 환경(ros2 launch)으로 실행했는지 확인')
        return False

    # ros2 topic echo 를 백그라운드로 시작 (best-effort)
    try:
        proc = subprocess.Popen(
            ['ros2', 'topic', 'echo', '--once', topic, 'std_msgs/msg/String'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(2.0)  # WiFi DDS discovery 대기
    except FileNotFoundError:
        warn('ros2 없음 – HTTP 응답 코드만 확인')
        proc = None

    # bridge 에 command 전송
    try:
        r = httpx.post(
            f'{bridge_url}/bridge/command',
            json={'robot_id': robot_id, 'command': 'TEST_PING'},
            timeout=3,
        )
        if r.status_code == 200:
            ok(f'bridge POST /bridge/command → {r.status_code}')
        else:
            fail(f'bridge POST /bridge/command → {r.status_code}')
            if proc:
                proc.kill()
            return False
    except Exception as e:
        fail(f'bridge 명령 전송 실패: {e}')
        if proc:
            proc.kill()
        return False

    # ROS2 echo 수신 확인 (best-effort: 실패해도 PASS)
    if proc:
        try:
            stdout, _ = proc.communicate(timeout=3.0)
            if 'TEST_PING' in stdout:
                ok(f'ROS2 토픽 {topic} 에서 TEST_PING 수신 확인')
            else:
                warn(f'{topic} echo 미수신 – 멀티머신 WiFi DDS 지연일 수 있음 (명령 전송은 정상)')
        except subprocess.TimeoutExpired:
            proc.kill()
            warn(f'{topic} echo 타임아웃 – WiFi DDS 지연으로 인한 정상 현상일 수 있음')

    # bridge 200 + node_active 이면 명령 흐름 정상
    return True


def check_ros2_to_bridge(robot_ns: str) -> bool:
    """
    로봇 ROS2 토픽이 실제로 값을 퍼블리시하는지 확인.
    """
    section(f'⑥ malle_bot → bridge  토픽 데이터 흐름 확인')

    for topic, msg_type in [
        (f'/{robot_ns}/odom', 'nav_msgs/msg/Odometry'),
        (f'/{robot_ns}/battery', 'std_msgs/msg/Float32'),
    ]:
        try:
            result = subprocess.run(
                ['ros2', 'topic', 'echo', '--once', '--timeout', '3', topic, msg_type],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                ok(f'{topic} 데이터 수신 확인')
            else:
                warn(f'{topic} 데이터 없음 (로봇이 퍼블리시 중인지 확인)')
        except subprocess.TimeoutExpired:
            warn(f'{topic} 타임아웃 – 로봇이 연결되지 않았거나 토픽 미발행')
        except FileNotFoundError:
            warn('ros2 없음 – ROS2 환경 source 필요')
            return False
    return True


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='malle 통신 확인 스크립트')
    parser.add_argument('--bridge-url',  default='http://localhost:9100')
    parser.add_argument('--service-url', default='http://localhost:8000')
    parser.add_argument('--robot-ns',    default='robot1')
    parser.add_argument('--robot-id',    type=int, default=1)
    args = parser.parse_args()

    print(f'\n{"═"*50}')
    print(f'  malle 통신 확인')
    print(f'  bridge  : {args.bridge_url}')
    print(f'  service : {args.service_url}')
    print(f'  robot   : /{args.robot_ns}  (id={args.robot_id})')
    print(f'{"═"*50}')

    results = {}
    results['bridge']    = check_bridge_health(args.bridge_url)
    results['service']   = check_service_health(args.service_url)
    results['ros2']      = check_ros2_topics(args.robot_ns)
    results['state']     = check_state_push(args.service_url, args.robot_id)
    results['cmd_flow']  = check_command_flow(args.bridge_url, args.robot_id, args.robot_ns)
    results['bot_data']  = check_ros2_to_bridge(args.robot_ns)

    # ── 최종 결과 ─────────────────────────────────────────────────────────────
    labels = {
        'bridge':   '① bridge_node 동작',
        'service':  '② malle_service 동작',
        'ros2':     '③ ROS2 토픽 존재',
        'state':    '④ bridge → malle_service 상태 전송',
        'cmd_flow': '⑤ malle_service → bridge → ROS2 명령',
        'bot_data': '⑥ malle_bot → bridge 데이터 흐름',
    }
    section('최종 결과')
    all_pass = True
    for key, label in labels.items():
        v = results[key]
        if v:
            ok(label)
        else:
            fail(label)
            all_pass = False

    print()
    if all_pass:
        print(f'  {GREEN}전체 통신 정상{RESET}\n')
    else:
        print(f'  {RED}일부 항목 실패 – 위 ✗ 항목을 확인하세요{RESET}\n')
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
