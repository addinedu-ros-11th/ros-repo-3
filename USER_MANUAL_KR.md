# ROS2 시스템 매니저 (ROS2 System Manager) - 사용 설명서

## 1. 소개
**ROS2 시스템 매니저** ("ROS2 Developer Dashboard"라고도 함)는 로컬 및 원격 ROS2 서비스를 효율적으로 관리하기 위한 GUI 애플리케이션입니다. 개발자는 이 도구를 통해 다음 작업을 수행할 수 있습니다.
- 로컬 및 원격 ROS2 노드/서비스 모니터링 및 제어
- 원격 로봇에 대한 SSH 연결 관리 및 터미널 접속
- 실시간 시스템 로그 확인
- 전체 워크스페이스 빌드 및 긴급 정지(KILL ALL) 기능

## 2. 필수 조건 (Prerequisites)
애플리케이션을 실행하기 전에 다음 항목들이 설치되어 있어야 합니다.

*   **Python 3**
*   **ROS2** (Humble 또는 Jazzy 권장)
*   **Python 라이브러리**:
    ```bash
    pip install PyQt6 paramiko
    ```

## 3. 설치 및 실행 방법
1.  `ros2_system_manager.py` 파일이 있는 디렉토리로 이동합니다.
2.  (선택 사항) 실행 권한 부여:
    ```bash
    chmod +x ros2_system_manager.py
    ```
3.  애플리케이션 실행:
    ```bash
    python3 ros2_system_manager.py
    ```
    *또는 실행 권한이 있는 경우:*
    ```bash
    ./ros2_system_manager.py
    ```

## 4. 인터페이스 개요
애플리케이션 화면은 크게 세 부분으로 나뉩니다.

### A. 사이드바 (왼쪽 패널)
설정 및 전역 제어 기능을 담당합니다.
-   **Configuration**: `ROS_DOMAIN_ID` 설정 (기본값: 0).
-   **Robot Connection**: SSH 설정 (User, IP) 및 키 관리.
-   **Global Controls**: 워크스페이스 빌드 및 모든 프로세스 종료 버튼.

### B. 서비스 그리드 (중앙 상단 패널)
관리되는 각 컴포넌트를 "서비스 카드" 형태로 보여줍니다.
-   **Remote Robot Node**: 로봇에서 실행되는 메인 드라이버.
-   **Local Services**: AI 서버, 메인 서비스, 웹 서비스, 관리자 UI.
-   **Service Card**: 서비스 이름, 상태 LED (초록=실행중, 회색=정지), 시작/정지 토글 버튼 포함.

### C. 로그 패널 (하단 패널)
시스템 및 실행 중인 서비스의 실시간 로그를 출력합니다.
-   **System Logs**: 청록색 (Cyan)
-   **Remote Logs**: 빨간색 (Red)
-   **AI Logs**: 초록색 (Green)
-   **Standard Logs**: 흰색 (White)

## 5. 사용 가이드

### 5.1. 로봇 연결 (SSH)
1.  사이드바의 **Robot Connection** 섹션에서:
    -   **User**: 사용자 이름 입력 (기본값: `pinky`).
    -   **IP**: 로봇의 IP 주소 입력 (기본값: `192.168.4.1`).
2.  **SSH 키 설정 (Setup SSH Keys)**:
    -   **Setup SSH Keys** 버튼 클릭.
    -   로컬 키가 없으면 생성 여부를 묻습니다. (Yes 선택)
    -   공개키를 로봇으로 전송하기 위해 로봇의 비밀번호를 입력합니다.
    -   *성공 메시지*: "Key transferred successfully."가 뜨면 완료.
3.  **터미널 열기 (Open Terminal)**:
    -   버튼을 클릭하면 로봇에 로그인된 상태로 새 `gnome-terminal` 창이 열립니다.

### 5.2. 서비스 관리
-   **서비스 시작**: 서비스 카드의 **START** 버튼 클릭. LED가 **초록색**으로 바뀌고 버튼은 **STOP** (빨간색)으로 변경됩니다.
-   **서비스 정지**: **STOP** 버튼 클릭. LED가 회색으로 바뀝니다.
-   **Remote Robot Node**: 이 서비스를 시작하면 설정된 SSH 연결을 통해 로봇의 bringup launch 파일을 실행합니다.

### 5.3. 전역 작업 (Global Actions)
-   **Build Workspace**: `colcon build --symlink-install` 명령어를 실행하여 로컬 워크스페이스를 빌드합니다. 로그 패널에서 진행 상황을 볼 수 있습니다.
-   **KILL ALL**: 이 버튼을 누르면 대시보드에서 관리하는 **모든** 로컬 및 원격 프로세스를 즉시 종료합니다. 비상시 사용하세요.

## 6. 문제 해결 (Troubleshooting)

| 문제 상황 | 원인 | 해결 방법 |
| :--- | :--- | :--- |
| **SSH 인증 실패** | 비밀번호 오류 또는 키 미등록 | "Setup SSH Keys"를 다시 실행하여 키를 등록하세요. |
| **서비스 시작 안됨** | 경로 오류 | `ros2_system_manager.py` 내의 `self.local_services` 경로가 실제 파일 시스템과 일치하는지 확인하세요. |
| **"Module not found"** | 의존성 패키지 누락 | `pip install PyQt6 paramiko` 명령어로 패키지를 설치하세요. |
| **원격 노드 실패** | 네트워크 또는 DOMAIN ID 불일치 | 로봇 IP(`ping 192.168.4.1`) 연결 확인 및 `ROS_DOMAIN_ID` 일치 여부를 확인하세요. |
