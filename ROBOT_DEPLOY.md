# 로봇 자동 실행 설정 (Raspberry Pi)

각 로봇(RPi)에 SSH 접속 후 진행합니다.
설정 완료 후 전원만 켜면 전체 스택이 자동으로 실행됩니다.

## 로봇별 설정값

| 로봇 | ROBOT_ID | ROS_DOMAIN_ID | ROBOT_NAMESPACE |
|------|----------|---------------|-----------------|
| malle_15 | 1 | 1 | malle_15 |
| malle_17 | 2 | 2 | malle_17 |
| malle_19 | 3 | 3 | malle_19 |
| malle_vic | 4 | 4 | malle_vic |

---

## 이전 설정에서 변경된 점

### start_robot.sh — launch 인자 제거 가능

이전에는 env var 값을 launch 인자로 **수동으로 넘겨야** 했습니다.

```bash
# 이전 방식
ros2 launch malle_controller malle.launch.xml \
  robot_id:=${ROBOT_ID} \
  robot_ns:=${ROBOT_NAMESPACE} \
  api_base_url:=${MALLE_SERVICE_URL}
```

이제 launch 파일이 `$(optenv ...)` 로 env var를 **직접 읽으므로** 인자 없이 실행해도 됩니다.

```bash
# 변경 후
ros2 launch malle_controller malle.launch.xml
```

### /home/pinky/.env — 변수명/형식 그대로, 내용 동일

기존에 사용하던 `/home/pinky/.env`의 변수명은 바뀐 것이 없습니다.
`MAP_PATH` 등 기존에 추가했던 항목도 그대로 유지합니다.

---

## 1. 사전 준비

### 맵 파일 절대경로 확인

```bash
# image 경로가 절대경로인지 확인
cat /home/pinky/ros-repo-3/malle_bot/map_end_end.yaml

# 상대경로면 절대경로로 수정
sed -i 's|image: map_end_end.pgm|image: /home/pinky/ros-repo-3/malle_bot/map_end_end.pgm|' \
  /home/pinky/ros-repo-3/malle_bot/map_end_end.yaml
```

### 패키지 설치 및 빌드

```bash
pip3 install fastapi uvicorn opencv-python pupil-apriltags --break-system-packages

cd /home/pinky/ros-repo-3/malle_bot
colcon build
```

---

## 2. /home/pinky/.env 작성

로봇별로 다른 값만 관리합니다. 아래에서 로봇에 맞게 수정하세요.

```bash
cat > /home/pinky/.env << 'EOF'
ROS_DOMAIN_ID=1
ROBOT_ID=1
ROBOT_NAMESPACE=malle_15
MALLE_SERVICE_URL=http://192.168.4.9:8000/api/v1
BRIDGE_SELF_URL=http://192.168.4.1:9100
MAP_PATH=/home/pinky/ros-repo-3/malle_bot/map_end_end.yaml
EOF
```

> `MALLE_SERVICE_URL` — malle_service 실행 컴퓨터의 IP
> `BRIDGE_SELF_URL` — 이 로봇(RPi)의 IP:9100 (malle_service가 명령 전송 시 사용)

---

## 방법 A — systemd (전원 켜면 자동 실행)

### start_robot.sh 작성

```bash
cat > /home/pinky/start_robot.sh << 'EOF'
#!/bin/bash
set -a
source /home/pinky/.env
set +a

source /opt/ros/jazzy/setup.bash
source /home/pinky/pinky_pro/install/local_setup.bash
source /home/pinky/ros-repo-3/malle_bot/install/local_setup.bash

ros2 launch pinky_bringup bringup_robot.launch.xml &
sleep 10

ros2 launch pinky_navigation web_nav2.launch.xml map:=${MAP_PATH} &
sleep 5

ros2 launch malle_controller malle.launch.xml &
sleep 2

exec ros2 launch malle_controller bridge.launch.xml
EOF

chmod +x /home/pinky/start_robot.sh
```

> `malle.launch.xml`과 `bridge.launch.xml` 모두 `.env`의 env var를 자동으로 읽습니다.
> 기존처럼 `robot_id:=` 등의 인자를 넘길 필요가 없습니다.

### systemd 서비스 등록

```bash
sudo tee /etc/systemd/system/malle_robot.service << 'EOF'
[Unit]
Description=Malle Robot Stack
After=network-online.target
Wants=network-online.target

[Service]
User=pinky
WorkingDirectory=/home/pinky
EnvironmentFile=/home/pinky/.env
ExecStart=/home/pinky/start_robot.sh
Restart=on-failure
RestartSec=10
KillMode=control-group

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable malle_robot.service
sudo systemctl start malle_robot.service
```

### 상태 확인

```bash
sudo systemctl status malle_robot.service
journalctl -u malle_robot.service -f        # 실시간 로그
journalctl -u malle_robot.service -n 50 --no-pager  # 최근 로그
```

### 이후 관리

```bash
# 설정(.env) 변경 후
nano /home/pinky/.env
sudo systemctl restart malle_robot.service

# colcon build 후 재시작
sudo systemctl restart malle_robot.service

# 터미널에서 직접 작업하고 싶을 때
sudo systemctl stop malle_robot.service
# ... 작업 ...
sudo systemctl start malle_robot.service
```

---

## 방법 B — Python 런처 (systemd 없이)

systemd 없이 Python 스크립트로 실행하는 방식입니다.
개발/디버깅 시 또는 systemd 설정이 번거로울 때 사용합니다.

```bash
cat > /home/pinky/start_robot.py << 'EOF'
#!/usr/bin/env python3
"""Malle 로봇 스택 런처 — .env 로드 후 ROS2 프로세스 순차 실행."""

import os
import subprocess
import time
import signal
import sys
from pathlib import Path

# .env 로드
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

ROS_SETUP = [
    "/opt/ros/jazzy/setup.bash",
    "/home/pinky/pinky_pro/install/local_setup.bash",
    "/home/pinky/ros-repo-3/malle_bot/install/local_setup.bash",
]
MAP_PATH = os.environ.get("MAP_PATH", "/home/pinky/ros-repo-3/malle_bot/map_end_end.yaml")

def ros2_launch(pkg, launch_file, extra_args="", wait=0):
    source_cmds = " && ".join(f"source {p}" for p in ROS_SETUP)
    cmd = f"{source_cmds} && ros2 launch {pkg} {launch_file} {extra_args}"
    proc = subprocess.Popen(["bash", "-c", cmd], env=os.environ)
    if wait:
        time.sleep(wait)
    return proc

procs = []

def shutdown(sig, frame):
    print("\n[launcher] 종료 중...")
    for p in reversed(procs):
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

print("[launcher] bringup 시작...")
procs.append(ros2_launch("pinky_bringup", "bringup_robot.launch.xml", wait=10))

print("[launcher] navigation 시작...")
procs.append(ros2_launch("pinky_navigation", f"web_nav2.launch.xml map:={MAP_PATH}", wait=5))

print("[launcher] malle controller 시작...")
procs.append(ros2_launch("malle_controller", "malle.launch.xml", wait=2))

print("[launcher] bridge 시작...")
procs.append(ros2_launch("malle_controller", "bridge.launch.xml"))

print("[launcher] 전체 스택 실행 중. Ctrl+C 로 종료.")
try:
    while True:
        time.sleep(5)
        # 비정상 종료된 프로세스 감지
        for p in procs:
            if p.poll() is not None:
                print(f"[launcher] 경고: 프로세스 {p.pid} 종료됨 (returncode={p.returncode})")
except KeyboardInterrupt:
    shutdown(None, None)
EOF

chmod +x /home/pinky/start_robot.py
```

실행:

```bash
python3 /home/pinky/start_robot.py
```

부팅 시 자동 실행이 필요하면 crontab으로 등록:

```bash
crontab -e
# 아래 줄 추가
@reboot sleep 30 && python3 /home/pinky/start_robot.py >> /home/pinky/robot.log 2>&1
```
