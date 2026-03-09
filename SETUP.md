# Mall-E 실행 가이드

## 목차

1. [최초 설정 (.env)](#1-최초-설정-env)
2. [이전 설정에서 마이그레이션](#2-이전-설정에서-마이그레이션)
3. [malle\_service 실행](#3-malle_service-실행)
4. [Web UI 실행](#4-web-ui-실행)
5. [malle\_bot 실행 (로봇)](#5-malle_bot-실행-로봇)
6. [테스트 스크립트](#6-테스트-스크립트)

---

## 1. 최초 설정 (.env)

모든 환경변수는 **프로젝트 루트의 `.env` 하나**에서 관리합니다.

```bash
cd ~/dev_ws/ros-repo-3
cp .env.example .env
```

`.env`를 열어 `{}` 로 감싼 항목을 직접 채웁니다.

```env
# 반드시 채워야 하는 항목 (로봇/환경마다 다름)
ROS_DOMAIN_ID={0}          # 로봇과 동일한 값
ROBOT_ID={1}               # 로봇별로 고유한 정수
ROBOT_NAMESPACE={malle_1}  # 로봇별로 고유한 네임스페이스
BRIDGE_SELF_URL={http://로봇IP:9100}  # 이 로봇의 외부 접속 URL

# DB가 localhost가 아닌 경우 수정
DB_URL=mysql+aiomysql://root:password@localhost:3306/malle
```

> **Web UI** (mobile / robot / admin)의 `VITE_*` 변수는 각 UI 디렉토리의
> `.env.development` 파일로 별도 관리합니다. 아래 [Web UI 실행](#4-web-ui-실행) 참고.

---

## 2. 이전 설정에서 마이그레이션

### 기존 루트 `.env` 삭제 후 재작성

이전 루트 `.env`에는 3개 변수만 있었습니다. 이제 하나의 파일로 전부 통합됐으므로
기존 파일을 지우고 `.env.example`에서 새로 만드세요.

```bash
rm .env
cp .env.example .env
# 이후 {} 항목 채우기
```

### 쉘 프로파일에서 제거해야 할 환경변수

이전에 `~/.bashrc` 또는 `~/.zshrc` 등에 직접 `export` 해뒀던 변수들은
이제 `.env`에서 자동으로 읽으므로 **중복 설정하면 `.env` 값이 무시됩니다.**

아래 변수들이 쉘 프로파일에 있으면 삭제하세요.

```bash
# 삭제 대상 (예시)
export ROS_DOMAIN_ID=...
export ROBOT_ID=...
export ROBOT_NAMESPACE=...
export MALLE_SERVICE_URL=...
export BRIDGE_HTTP_PORT=...
export BRIDGE_SELF_URL=...
export CAMERA_PUSH_ENABLED=...
```

확인 방법:

```bash
grep -E "ROS_DOMAIN_ID|ROBOT_ID|ROBOT_NAMESPACE|MALLE_SERVICE_URL|BRIDGE_HTTP_PORT|BRIDGE_SELF_URL|BRIDGE_BASE_URL" ~/.bashrc ~/.zshrc 2>/dev/null
```

### 변수명 변경 사항

| 이전 이름 | 현재 이름 | 비고 |
|-----------|-----------|------|
| `BRIDGE_BASE_URL` | `BRIDGE_NODE_URL` | malle\_service에서 bridge 호출 시 사용 |

쉘 프로파일이나 다른 스크립트에 `BRIDGE_BASE_URL`이 있으면 `BRIDGE_NODE_URL`로 바꾸세요.

---

## 3. malle\_service 실행

`.env` 로딩은 `config.py`가 자동으로 처리합니다. 별도 `source` 불필요.

```bash
cd ~/dev_ws/ros-repo-3/malle_service

# 최초 1회
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 실행
source .venv/bin/activate
python run.py
```

서버가 `http://0.0.0.0:8000` 에서 시작됩니다.

---

## 4. Web UI 실행

Web UI의 `VITE_*` 변수는 각 디렉토리 안에 `.env.development` 파일로 관리합니다.
파일이 없으면 아래 내용을 참고해 생성하세요.

### Admin

```bash
cd ~/dev_ws/ros-repo-3/malle_web_service/ui/admin
```

`.env.development` (없으면 생성):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

```bash
npm i      # 최초 1회
npm run dev
```

### Mobile

```bash
cd ~/dev_ws/ros-repo-3/malle_web_service/ui/mobile
```

`.env.development` (없으면 생성):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

```bash
npm i      # 최초 1회
npm run dev
```

### Robot

```bash
cd ~/dev_ws/ros-repo-3/malle_web_service/ui/robot
```

`.env.development` (없으면 생성, **로봇별로 VITE\_ROBOT\_ID 다름**):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_ROBOT_ID=1   # malle_1 → 1 / malle_2 → 2 / ...
```

```bash
npm i      # 최초 1회
npm run dev
```

---

## 5. malle\_bot 실행 (로봇)

`.env`에 설정한 값이 launch 파일을 통해 ROS2 노드에 자동 주입됩니다.
실행 전에 `.env`를 쉘에 로드합니다.

```bash
# .env 로드 (터미널당 1회)
set -a && source ~/dev_ws/ros-repo-3/.env && set +a
```

### bridge\_node (서버 PC에서 실행)

로봇과 malle\_service 사이의 HTTP 브릿지입니다.
ROS2 환경이 source 된 터미널에서 실행합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/dev_ws/ros-repo-3/malle_bot/install/setup.bash

ros2 launch malle_controller bridge.launch.xml
```

`.env`에 값이 있으면 인자 생략 가능. 특정 값만 오버라이드하려면:

```bash
ros2 launch malle_controller bridge.launch.xml robot_id:=2 robot_namespace:=malle_2
```

### malle.launch (로봇 본체에서 실행)

미션 실행기, 카메라, lockbox 등 로봇 전체 노드 묶음입니다.

```bash
source /opt/ros/humble/setup.bash
source ~/dev_ws/ros-repo-3/malle_bot/install/setup.bash

ros2 launch malle_controller malle.launch.xml
```

마찬가지로 오버라이드 가능:

```bash
ros2 launch malle_controller malle.launch.xml lockbox_iface:=gpio
```

### bridge\_node 직접 실행 (ROS2 없이, HTTP-only 모드)

```bash
cd ~/dev_ws/ros-repo-3/malle_bot
source .venv/bin/activate   # 또는 시스템 Python
set -a && source ~/dev_ws/ros-repo-3/.env && set +a

python src/malle_controller/malle_controller/bridge_node.py
```

---

## 6. 테스트 스크립트

테스트 스크립트는 루트 `.env`를 자동으로 로드합니다.
`TEST_*` 변수를 `.env`에 미리 설정해두면 인자 없이 실행 가능합니다.

### 전체 테스트

```bash
cd ~/dev_ws/ros-repo-3
python test/run_all.py

# 통합 테스트 포함 (서버 + TEST_ROBOT_A/B 등 필요)
python test/run_all.py --integration
```

### Mutex 통합 테스트

`.env`에 `TEST_ROBOT_A`, `TEST_ROBOT_B`, `TEST_SESSION_B`, `TEST_POI_ID` 설정 시:

```bash
python test/test_occupied_mutex.py --add-item
```

직접 인자로도 가능:

```bash
python test/test_occupied_mutex.py --robot-a 1 --robot-b 2 --session-b 5 --poi 4 --add-item
```

### 통신 확인 스크립트

```bash
# .env 값(BRIDGE_NODE_URL, MALLE_SERVICE_URL, ROBOT_ID 등)을 자동으로 사용
python malle_bot/src/malle_controller/test/verify_comms.py

# 값 오버라이드
python malle_bot/src/malle_controller/test/verify_comms.py \
  --bridge-url http://192.168.4.10:9100 \
  --robot-id 2
```

---

## 전체 실행 순서 (로컬 개발)

터미널 4개 기준:

| 터미널 | 명령 |
|--------|------|
| 1 | `cd malle_service && source .venv/bin/activate && python run.py` |
| 2 | `cd malle_web_service/ui/admin && npm run dev` |
| 3 | `cd malle_web_service/ui/mobile && npm run dev` |
| 4 | `cd malle_web_service/ui/robot && npm run dev` |

> ROS2 연동이 필요하면 터미널을 추가해 `bridge.launch.xml` 또는 `malle.launch.xml` 실행.
