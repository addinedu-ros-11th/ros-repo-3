import sys
import os
os.environ["QT_LOGGING_RULES"] = "qt.qpa.theme.gnome.debug=false;qt.qpa.theme.generic.debug=false;qt.qpa.theme.gtk3.debug=false"
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QSpinBox, QHBoxLayout, QFrame, QLineEdit, QGroupBox,
                             QMessageBox, QInputDialog, QTextEdit, QGridLayout, QScrollArea,
                             QSizePolicy, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QProcess, QTimer, QSize, QProcessEnvironment
from PyQt6.QtGui import QFont, QColor, QIcon
from ssh_key_manager import SSHKeyManager

# ---------------------------------------------------------
# UI CONSTANTS
# ---------------------------------------------------------
COLOR_BG = "#2E3440"
COLOR_FG = "#ECEFF4"
COLOR_ACCENT = "#88C0D0"
COLOR_RED = "#BF616A"
COLOR_GREEN = "#A3BE8C"
COLOR_YELLOW = "#EBCB8B"
COLOR_PURPLE = "#B48EAD"
COLOR_DARK_BTN = "#3B4252"
COLOR_HOVER = "#4C566A"

STYLESHEET = f"""
    QWidget {{
        background-color: {COLOR_BG};
        color: {COLOR_FG};
        font-family: 'Segoe UI', sans-serif;
    }}
    QPushButton {{
        background-color: {COLOR_DARK_BTN};
        border-radius: 6px;
        padding: 8px 15px;
        font-weight: bold;
        border: 1px solid #4C566A;
    }}
    QPushButton:hover {{
        background-color: {COLOR_HOVER};
    }}
    QLineEdit, QSpinBox {{
        padding: 5px;
        border-radius: 4px;
        background-color: #3B4252;
        border: 1px solid #4C566A;
        color: white;
    }}
    QGroupBox {{
        border: 1px solid #4C566A;
        border-radius: 6px;
        margin-top: 10px;
        font-weight: bold;
        padding-top: 15px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}
    QScrollBar:vertical {{
        border: none;
        background: {COLOR_BG};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_HOVER};
        min-height: 20px;
        border-radius: 5px;
    }}
"""

# ---------------------------------------------------------
# SERVICE CARD WIDGET
# ---------------------------------------------------------
class ServiceCard(QFrame):
    toggle_requested = pyqtSignal(str, bool)  # name, is_starting

    def __init__(self, name, description, color_code):
        super().__init__()
        self.name = name
        self.is_running = False
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            ServiceCard {{
                background-color: #3B4252;
                border-radius: 10px;
                border: 1px solid #4C566A;
            }}
        """)
        self.setFixedHeight(120)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header: LED + Name
        header_layout = QHBoxLayout()
        
        # LED Indicator
        self.led = QLabel()
        self.led.setFixedSize(12, 12)
        self.set_led_color(False)
        self.led.setStyleSheet("border-radius: 6px;")
        
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        header_layout.addWidget(self.led)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        
        # Color Strip (Visual identifier)
        strip = QFrame()
        strip.setFixedHeight(3)
        strip.setStyleSheet(f"background-color: {color_code}; border-radius: 1px;")
        
        # Toggle Button
        self.btn_toggle = QPushButton("Start")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.on_toggle)
        self.update_button_style()

        layout.addLayout(header_layout)
        layout.addWidget(strip)
        layout.addStretch()
        layout.addWidget(self.btn_toggle)

    def set_led_color(self, active):
        color = COLOR_GREEN if active else "#4C566A" # Green or Dark Gray
        self.led.setStyleSheet(f"background-color: {color}; border-radius: 6px; border: 1px solid #2E3440;")

    def update_button_style(self):
        if self.is_running:
            self.btn_toggle.setText("STOP")
            self.btn_toggle.setStyleSheet(f"background-color: {COLOR_RED}; color: white; border: none;")
        else:
            self.btn_toggle.setText("START")
            self.btn_toggle.setStyleSheet(f"background-color: {COLOR_DARK_BTN}; color: {COLOR_FG};")

    def set_status(self, running):
        self.is_running = running
        self.set_led_color(running)
        self.update_button_style()

    def on_toggle(self):
        # Emit signal to request start/stop
        # Logic handles exact state, but here we toggle intent
        self.toggle_requested.emit(self.name, not self.is_running)


# ---------------------------------------------------------
# PROCESS MANAGER (BACKEND)
# ---------------------------------------------------------
class ProcessManager(QObject):
    log_received = pyqtSignal(str, str) # source, message
    process_started = pyqtSignal(str)
    process_finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.processes = {} # name -> QProcess

    def start_local_process(self, name, command, domain_id=0):
        if name in self.processes and self.processes[name].state() != QProcess.ProcessState.NotRunning:
            return

        process = QProcess()
        
        # Prepare Environment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("ROS_DOMAIN_ID", str(domain_id))
        process.setProcessEnvironment(env)

        # Merge Channels for simple logging
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        # Signals
        process.readyRead.connect(lambda: self.read_output(name, process))
        process.finished.connect(lambda: self.on_process_finished(name))
        
        # Start
        # Using bash -c to handle complex commands (source, etc.)
        process.start("bash", ["-c", command])
        
        self.processes[name] = process
        self.process_started.emit(name)
        self.log_received.emit("System", f"Starting local service: {name} (ID: {domain_id})...")

    def start_remote_process(self, name, user, ip, command, domain_id=0):
        if name in self.processes and self.processes[name].state() != QProcess.ProcessState.NotRunning:
            return

        process = QProcess()
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        process.readyRead.connect(lambda: self.read_output(name, process))
        process.finished.connect(lambda: self.on_process_finished(name))

        # Check connectivity first (optional/fast check?)
        # For now, simply launching ssh
        
        import shlex
        
        full_remote_cmd = f"export ROS_DOMAIN_ID={domain_id}; {command}"
        
        # Use shlex.quote to handle nested quotes correctly in the command string
        quoted_cmd = shlex.quote(full_remote_cmd)
        
        ssh_args = [
            f"{user}@{ip}", 
            "-tt", 
            f"bash -c {quoted_cmd}"
        ]

        process.start("ssh", ssh_args)
        
        self.processes[name] = process
        self.process_started.emit(name)
        self.log_received.emit("System", f"Starting remote service: {name} on {ip}...")

    def stop_process(self, name):
        if name in self.processes:
            process = self.processes[name]
            if process.state() != QProcess.ProcessState.NotRunning:
                self.log_received.emit("System", f"Stopping {name}...")
                process.terminate()
                # If it doesn't close in 2 seconds, kill it
                QTimer.singleShot(2000, lambda: self._force_kill_if_needed(process))

    def _force_kill_if_needed(self, process):
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()

    def stop_all(self):
        for name in list(self.processes.keys()):
            self.stop_process(name)

    def read_output(self, name, process):
        data = process.readAll()
        text = data.data().decode('utf-8', errors='ignore').strip()
        if text:
            self.log_received.emit(name, text)

    def on_process_finished(self, name):
        self.log_received.emit("System", f"Service {name} stopped.")
        self.process_finished.emit(name)
        if name in self.processes:
            del self.processes[name]


# ---------------------------------------------------------
# MAIN APPLICATION
# ---------------------------------------------------------
class ROS2SystemManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROS2 Developer Dashboard")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)
        
        self.process_manager = ProcessManager()
        self.ssh_manager = SSHKeyManager()
        
        self.process_manager.log_received.connect(self.append_log)
        self.process_manager.process_started.connect(self.on_service_started)
        self.process_manager.process_finished.connect(self.on_service_stopped)
        
        self.service_cards = {} # name -> ServiceCard widget
        
        # Data
        # Use absolute paths based on the script location
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.local_services = [
            {
                "name": "Local AI Server",
                # Fixed path: run.py is in root of malle_ai_service, not app/
                "cmd": f"cd {base_dir}/malle_ai_service && [ -d venv ] && source venv/bin/activate || echo 'VENV MISSING'; python3 run.py",
                "color": "#A3BE8C" # Green
            },
            {
                "name": "Local Main Service",
                "cmd": f"source /opt/ros/jazzy/setup.bash; cd {base_dir}/malle_service && [ -d venv ] && source venv/bin/activate || echo 'VENV MISSING'; uvicorn main:app --reload --port 8000",
                "color": "#B48EAD" # Purple
            },
            {
                "name": "Local Web Service",
                "cmd": f"cd {base_dir}/malle_web_service/service && [ -d venv ] && source venv/bin/activate || echo 'VENV MISSING'; uvicorn main:app --reload --port 8001",
                "color": "#EBCB8B" # Yellow
            },
            {
                "name": "Local Admin UI",
                # Fixed command: use 'npm run dev' instead of 'npm start'
                "cmd": f"cd {base_dir}/malle_web_service/ui/admin && npm run dev",
                "color": "#D08770" # Orange
            }
        ]
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # 1. SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(300)
        sidebar.setStyleSheet(f"background-color: #242933; border-right: 1px solid #4C566A;")
        sidebar_layout = QVBoxLayout(sidebar)
        
        # Title
        title = QLabel("System Manager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        sidebar_layout.addWidget(title)
        
        # Domain Config
        conf_group = QGroupBox("Configuration")
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("ROS_DOMAIN_ID:"))
        self.domain_spin = QSpinBox()
        self.domain_spin.setRange(0, 100)
        conf_layout.addWidget(self.domain_spin)
        conf_group.setLayout(conf_layout)
        sidebar_layout.addWidget(conf_group)
        
        # SSH Config
        ssh_group = QGroupBox("Robot Connection")
        ssh_layout = QVBoxLayout()
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("User:"))
        self.ssh_user = QLineEdit("pinky")
        self.ssh_user.textChanged.connect(self.update_ssh_settings)
        h1.addWidget(self.ssh_user)
        ssh_layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("IP:"))
        self.ssh_ip = QLineEdit("192.168.4.1")
        self.ssh_ip.textChanged.connect(self.update_ssh_settings)
        h2.addWidget(self.ssh_ip)
        ssh_layout.addLayout(h2)
        
        btn_ssh_key = QPushButton("Setup SSH Keys")
        btn_ssh_key.clicked.connect(self.setup_ssh_keys)
        ssh_layout.addWidget(btn_ssh_key)
        
        btn_term = QPushButton("Open Terminal (SSH)")
        btn_term.clicked.connect(self.open_ssh_terminal)
        ssh_layout.addWidget(btn_term)
        
        ssh_group.setLayout(ssh_layout)
        sidebar_layout.addWidget(ssh_group)
        
        sidebar_layout.addStretch()

        # Global Actions
        action_group = QGroupBox("Global Controls")
        action_layout = QVBoxLayout()
        
        btn_build = QPushButton("Build Workspace")
        btn_build.setStyleSheet(f"background-color: {COLOR_PURPLE}; color: #2E3440;")
        btn_build.clicked.connect(self.global_build)
        action_layout.addWidget(btn_build)
        
        btn_kill = QPushButton("KILL ALL")
        btn_kill.setStyleSheet(f"background-color: {COLOR_RED}; color: white; font-weight: bold; padding: 15px;")
        btn_kill.clicked.connect(self.kill_all_systems)
        action_layout.addWidget(btn_kill)
        
        action_group.setLayout(action_layout)
        sidebar_layout.addWidget(action_group)
        
        main_layout.addWidget(sidebar)

        # 2. MAIN CONTENT AREA
        content_split = QSplitter(Qt.Orientation.Vertical)
        content_split.setStyleSheet("QSplitter::handle { background-color: #4C566A; height: 2px; }")
        
        # Service Grid Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: transparent; border: none;")
        
        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(15)
        
        # Populate Grid
        self.add_service_cards()
        
        scroll_area.setWidget(grid_widget)
        content_split.addWidget(scroll_area)

        # 3. LOGGING AREA
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; background-color: #242933;")
        self.log_view.setPlaceholderText("System logs will appear here...")
        content_split.addWidget(self.log_view)
        
        # Set splitter ratio (70% grid, 30% log)
        content_split.setStretchFactor(0, 3)
        content_split.setStretchFactor(1, 1)

        main_layout.addWidget(content_split)

    def add_service_cards(self):
        row, col = 0, 0
        max_cols = 3
        
        # A. Remote Robot
        remote_card = ServiceCard("Remote Robot Node", "Main ROS2 Driver", COLOR_RED)
        remote_card.toggle_requested.connect(self.handle_remote_toggle)
        self.service_cards["Remote Robot Node"] = remote_card
        self.grid_layout.addWidget(remote_card, row, col)
        col += 1

        # B. Local Services
        for srv in self.local_services:
            if col >= max_cols:
                col = 0
                row += 1
            card = ServiceCard(srv["name"], "Local Service", srv["color"])
            card.setProperty("cmd", srv["cmd"]) # Store cmd in widget property
            card.toggle_requested.connect(self.handle_local_toggle)
            
            self.service_cards[srv["name"]] = card
            self.grid_layout.addWidget(card, row, col)
            col += 1

    # ------------------ LOGIC HANDLERS ------------------

    def update_ssh_settings(self):
        self.ssh_manager.user = self.ssh_user.text()
        self.ssh_manager.ip = self.ssh_ip.text()

    def handle_local_toggle(self, name, should_start):
        if should_start:
            card = self.service_cards[name]
            cmd = card.property("cmd")
            self.process_manager.start_local_process(name, cmd, self.domain_spin.value())
        else:
            self.process_manager.stop_process(name)

    def handle_remote_toggle(self, name, should_start):
        if should_start:
            # Remote command
            # Try to source workspace if it exists
            # We assume it might be in ~/ros2_ws or ~/pinky_pro/ros-repo-3/install
            # But likely ~/ros2_ws/install/setup.bash for user deployed code
            # Remote command: Simplified to prioritize finding the workspace and launching
            # We try common workspace paths.
            cmd = (
                "source /opt/ros/jazzy/setup.bash 2>/dev/null || source /opt/ros/humble/setup.bash; "
                "if [ -f ~/pinky_pro/ros-repo-3/install/setup.bash ]; then source ~/pinky_pro/ros-repo-3/install/setup.bash; "
                "elif [ -f ~/pinky_pro/install/setup.bash ]; then source ~/pinky_pro/install/setup.bash; "
                "elif [ -f ~/ros2_ws/install/setup.bash ]; then source ~/ros2_ws/install/setup.bash; "
                "elif [ -f ~/dev_ws/install/setup.bash ]; then source ~/dev_ws/install/setup.bash; fi; "
                "echo 'Remote: Launching pinky_bringup (bringup_robot.launch.xml)...'; "
                "ros2 launch pinky_bringup bringup_robot.launch.xml"
            )
            self.process_manager.start_remote_process(
                name, 
                self.ssh_user.text(), 
                self.ssh_ip.text(),
                cmd,
                self.domain_spin.value()
            )

    # Replaces the old start_remote_process call in handle_remote_toggle
    # We need to adjust handle_remote_toggle to NOT call start_remote_process but do it directly 
    # OR modify start_remote_process. 
    # Let's modify handle_remote_toggle to simply call start_remote_process with the new command logic if we can, 
    # BUT start_remote_process implementation in ProcessManager (lines 190-216) constructs the ssh command itself.
    # So we should modify ProcessManager.start_remote_process OR change how we call it.
    # The clean way is to pass the full command to start_remote_process and let it wrap it, 
    # but ProcessManager.start_remote_process adds 'export ROS_DOMAIN_ID'. 
    # Let's update handle_remote_toggle to construct the command string cleanly, 
    # and update ProcessManager.start_remote_process to use -tt.

        else:
            self.process_manager.stop_process(name)

    def on_service_started(self, name):
        if name in self.service_cards:
            self.service_cards[name].set_status(True)

    def on_service_stopped(self, name):
        if name in self.service_cards:
            self.service_cards[name].set_status(False)

    def append_log(self, source, message):
        color = "#ECEFF4"
        if source == "System": color = "#88C0D0"
        elif "Remote" in source: color = "#BF616A"
        elif "AI" in source: color = "#A3BE8C"
        
        formatted = f'<span style="color: {color};"><b>[{source}]</b></span>: {message}'
        self.log_view.append(formatted)

    def kill_all_systems(self):
        self.process_manager.stop_all()
        # Attempt to kill likely stuck ports
        ports = [8000, 8001, 5173]
        for port in ports:
            subprocess.run(f"fuser -k {port}/tcp", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        self.log_view.append('<span style="color: #BF616A;"><b>[SYSTEM] ALL PROCESSES TERMINATED (Requested port cleanup).</b></span>')

    def global_build(self):
        # Starts a separate build process
        # Source ROS2 before building
        cmd = "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"
        self.process_manager.start_local_process("Global Build", cmd, self.domain_spin.value())

    def open_ssh_terminal(self):
        # Just launches a gnome-terminal with ssh
        user = self.ssh_user.text()
        ip = self.ssh_ip.text()
        cmd = f"gnome-terminal -- bash -c 'ssh {user}@{ip}; exec bash'"
        subprocess.Popen(cmd, shell=True)

    def setup_ssh_keys(self):
        # Reuse SSH Key Manager logic
        if not self.ssh_manager.check_local_key():
            reply = QMessageBox.question(self, "Setup SSH", "No local SSH key found. Generate?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.ssh_manager.generate_local_key()
        
        pwd, ok = QInputDialog.getText(self, "SSH Password", f"Enter password for {self.ssh_manager.user}@{self.ssh_manager.ip}:", QLineEdit.EchoMode.Password)
        if ok and pwd:
            success, msg = self.ssh_manager.transfer_key(pwd)
            if success: QMessageBox.information(self, "Success", msg)
            else: QMessageBox.warning(self, "Failed", msg)

if __name__ == "__main__":
    # Force Fusion style to avoid GTK/Wayland dbus issues
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ROS2SystemManager()
    window.show()
    sys.exit(app.exec())
