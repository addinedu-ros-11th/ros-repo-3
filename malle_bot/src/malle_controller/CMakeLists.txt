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

# Python 모듈 설치
install(DIRECTORY ${PROJECT_NAME}/
  DESTINATION lib/python${PYTHON_VERSION}/site-packages/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.py"
)

# -- 실행 스크립트 목록 -----------
set(MALLE_SCRIPTS
  mission_executor
  bridge_node
  mission_guide
  mission_follow
  mission_errand
  tag_tracker
  lockbox_controller
  battery_monitor
  topic_relay
  mission_parking11
)

# 스크립트 자동 생성 및 설치
foreach(script ${MALLE_SCRIPTS})
  file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/${script}
"#!/usr/bin/env python3
import sys
sys.path.insert(0, '${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_VERSION}/site-packages')
from malle_controller.${script} import main
if __name__ == '__main__':
    main()
")
endforeach()

set(script_files)
foreach(script ${MALLE_SCRIPTS})
  list(APPEND script_files ${CMAKE_CURRENT_BINARY_DIR}/${script})
endforeach()

install(PROGRAMS ${script_files} DESTINATION lib/${PROJECT_NAME})

# launch 및 config 파일 설치
install(DIRECTORY launch/ DESTINATION share/${PROJECT_NAME}/launch)
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

ament_package()
