# ros-repo-3
파이널 프로젝트 3조 저장소. Mall-E - 대형 쇼핑 컴플렉스에서 고객을 보조하는 스마트 쇼핑 메이트 봇 (Autonomous Mobile Shopping Assistant Robot)
# 🛒 MALL-STERS: mall-E (Autonomous Shopping Helper Robot)

> **대형 쇼핑몰에서의 비효율적인 쇼핑 경험을 혁신하는 ROS 2 기반 자율주행 로봇 프로젝트**

## 📝 프로젝트 개요
대형 쇼핑몰 방문객들이 겪는 **매장 찾기의 어려움, 무거운 짐 이동, 최적 동선 부재** 등의 페인 포인트(Pain Points)를 해결하기 위해 기획되었습니다. `mall-E`는 자율주행, 객체 추종, 사용자 인터페이스를 결합하여 사용자에게 스마트한 쇼핑 경험을 제공합니다.

- **개발 기간**: 2026. 02 ~ 2026. 03
- **개발 환경**: Ubuntu 22.04, ROS 2 Humble, C++, Python
- **팀명**: MALL-STERS (ROS 2 11기 Final Project 3팀)

## ✨ 주요 기능

### 1. 자율주행 및 목적지 안내 (NAV2)
- **SLAM & Localization**: 정밀한 맵 빌딩 및 AMCL 보정을 통한 위치 추정
- **Path Planning**: 최적 동선 설계 및 동적 장애물 회피 주행
- **POI Navigation**: 주요 매장 위치 좌표 설계를 통한 원터치 이동

### 2. 사용자 추종 및 인식 (Depth Camera)
- **Depth Cam 객체 인식**: 깊이 카메라를 활용한 사용자 인식 및 거리 유지
- **Human Follower**: 사용자를 실시간으로 추적하며 짐을 운반하는 추종 주행 구현
- **MediaPipe 제어**: 손동작 인식을 통한 로봇 제어 및 음성 명령 연동

### 3. 스마트 도킹 및 관리
- **AprilTag 파킹**: 정밀한 스테이션 태그 인식을 통한 자동 충전 및 파킹
- **FMS 통합**: 로봇의 상태 모니터링 및 Command & Control 서버 연동
- **Lockbox 시스템**: 물품 보관을 위한 스마트 락박스 설계 및 제어

## 🏗️ 시스템 아키텍처


## 🛠️ 기술 스택
| Category | Tech Stack |
| :--- | :--- |
| **O.S.** | Linux ubuntu 24.04 |
| **Framework** | ROS 2 jazzy |
| **Language** | C++, Python |
| **Navigation** | NAV2, SLAM Toolbox, AMCL |
| **Perception** | OpenCV, MediaPipe, Depth Camera, AprilTag |
| **Communication** | Fast DDS, WebBridge (Server-Robot) |
| **Simulation** | Gazebo, Rviz2 |

## 👥 팀원 소개 및 역할 (Our Crew)

| 이름 | 역할 (Role) | 주요 구현 내용 |
| :--- | :--- | :--- |
| **이가람** | **SLAM / NAV2** | SLAM 맵빌딩, NAV2 파라미터 튜닝, Path Planning 알고리즘 비교 연구 |
| **김용준** | **Navigation / Control** | April Tag 추종 주행, 맵 설계, IR 센서 라인트래킹, 스테이션 태그 파킹, 비전 장애물 회피 |
| **양효인** | **System / Nav** | POI 설계, 도착 지점 좌표 오차 보정, 태그 파킹, 락박스 설계 및 코딩 |
| **용도원** | **FMS / GUI** | 기획, GUI 빌드, 서버 구현, 로봇 Command&Control, 데이터 설계, SLAM 맵빌딩 |
| **전민재** | **Control / Nav** | PID 제어, NAV2 튜닝, 통신 설계, AMCL 보정, Waypoint 설계 및 적용 |
| **홍성민** | **Perception / Control** | Depth Cam 객체인식, 추종 주행 구현, MediaPipe 제어, 음성 명령 제어, Gazebo 시뮬레이션 |

## 🚀 시작하기

### 1. 워크스페이스 빌드
```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
