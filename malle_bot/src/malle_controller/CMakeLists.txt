cmake_minimum_required(VERSION 3.5)
project(malle_controller)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# 메시지 생성
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MessageHeader.msg"
  "msg/RobotMessage.msg"
  "msg/TaskCommand.msg"
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

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/mission_executor
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.mission_executor import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/mission_follow
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.mission_follow import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/bridge_node
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.bridge_node import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/mission_guide
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.mission_guide import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/mission_errand
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.mission_errand import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/tag_tracker
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.tag_tracker import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/lockbox_controller
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.lockbox_controller import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/battery_monitor
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.battery_monitor import main
if __name__ == '__main__':
    main()
")

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/topic_relay
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.topic_relay import main
if __name__ == '__main__':
    main()
")

# launch 및 config 파일 설치
install(DIRECTORY launch/ DESTINATION share/${PROJECT_NAME}/launch)
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

install(PROGRAMS
  ${CMAKE_CURRENT_BINARY_DIR}/mission_executor
  ${CMAKE_CURRENT_BINARY_DIR}/mission_follow
  ${CMAKE_CURRENT_BINARY_DIR}/bridge_node
  ${CMAKE_CURRENT_BINARY_DIR}/mission_guide
  ${CMAKE_CURRENT_BINARY_DIR}/mission_errand
  ${CMAKE_CURRENT_BINARY_DIR}/tag_tracker
  ${CMAKE_CURRENT_BINARY_DIR}/lockbox_controller
  ${CMAKE_CURRENT_BINARY_DIR}/battery_monitor
  ${CMAKE_CURRENT_BINARY_DIR}/topic_relay
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
