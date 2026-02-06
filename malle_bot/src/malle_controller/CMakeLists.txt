cmake_minimum_required(VERSION 3.5)
project(malle_controller)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# 메시지 생성
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MessageHeader.msg"
  "msg/RobotMessage.msg"
)

# Python 버전 자동 감지
execute_process(
  COMMAND python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  OUTPUT_VARIABLE PYTHON_VERSION
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Python 모듈 직접 설치
install(DIRECTORY ${PROJECT_NAME}/
  DESTINATION lib/python${PYTHON_VERSION}/site-packages/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.py"
)

# Wrapper 스크립트 생성
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/test_publisher
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.test_publisher import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/test_subscriber
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.test_subscriber import main
if __name__ == '__main__':
    main()
")

# Wrapper 스크립트 설치
install(PROGRAMS
  ${CMAKE_CURRENT_BINARY_DIR}/test_publisher
  ${CMAKE_CURRENT_BINARY_DIR}/test_subscriber
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()