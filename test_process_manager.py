import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ros2_system_manager import ProcessManager

def test_process_manager():
    app = QApplication(sys.argv)
    manager = ProcessManager()
    
    # Test Data
    test_name = "Test Echo"
    test_cmd = "echo 'Hello Process Manager'; sleep 1; echo 'Done'"

    # 1. Start Process
    print(f"Starting process: {test_name}")
    manager.start_local_process(test_name, test_cmd)
    
    # Check if process exists
    if test_name in manager.processes:
        print("PASS: Process created locally.")
    else:
        print("FAIL: Process not found in manager.")

    # 2. Monitor Output
    def on_log(source, msg):
        print(f"LOG RECEIVED [{source}]: {msg}")

    manager.log_received.connect(on_log)
    
    # 3. Monitor Finish
    def on_finished(name):
        print(f"Process {name} Finished.")
        if name == test_name:
            print("PASS: Process finished correctly.")
            app.quit()

    manager.process_finished.connect(on_finished)
    
    # Run loop
    QTimer.singleShot(3000, lambda: (print("Timeout!"), app.quit())) # fail-safe
    app.exec()

if __name__ == "__main__":
    try:
        test_process_manager()
        print("Test Complete.")
    except Exception as e:
        print(f"Test Failed: {e}")
