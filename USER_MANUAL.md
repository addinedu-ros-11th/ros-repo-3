# ROS2 System Manager - User Manual

## 1. Introduction
The **ROS2 System Manager** (also known as the **ROS2 Developer Dashboard**) is a GUI application designed to streamline the management of local and remote ROS2 services. It allows developers to:
- Monitor and control multiple ROS2 nodes and services.
- Manage SSH connections to remote robots.
- View real-time system logs.
- Perform global workspace builds and emergency stops.

## 2. Prerequisites
Before running the application, ensure you have the following installed:

*   **Python 3**
*   **ROS2** (Humble or Jazzy recommended, depending on your setup)
*   **Python Dependencies**:
    ```bash
    pip install PyQt6 paramiko
    ```

## 3. Installation & Launch
1.  Navigate to the directory containing `ros2_system_manager.py`.
2.  Make the script executable (optional):
    ```bash
    chmod +x ros2_system_manager.py
    ```
3.  Run the application:
    ```bash
    python3 ros2_system_manager.py
    ```
    *Or if executable:*
    ```bash
    ./ros2_system_manager.py
    ```

## 4. Interface Overview
The application window is divided into three main sections:

### A. Sidebar (Left Panel)
Controls configuration and global actions.
-   **Configuration**: Set the `ROS_DOMAIN_ID` (default: 0).
-   **Robot Connection**: Manage SSH settings (User, IP) and keys.
-   **Global Controls**: Build the workspace or kill all processes.

### B. Service Grid (Center/Top Panel)
Displays individual "Service Cards" for each managed component.
-   **Remote Robot Node**: The main driver running on the robot.
-   **Local Services**: AI Server, Main Service, Web Service, Admin UI.
-   **Service Card**: Shows the service name, status LED (Green=Running, Gray=Stopped), and a Start/Stop toggle button.

### C. Log Panel (Bottom Panel)
Displays real-time logs from the system and running services.
-   **System Logs**: Cyan
-   **Remote Logs**: Red
-   **AI Logs**: Green
-   **Standard Logs**: White

## 5. Usage Guide

### 5.1. Connecting to the Robot
1.  In the Sidebar under **Robot Connection**:
    -   **User**: Enter the username (default: `pinky`).
    -   **IP**: Enter the robot's IP address (default: `192.168.4.1`).
2.  **Setup SSH Keys**:
    -   Click **Setup SSH Keys**.
    -   If no local key exists, you will be asked to generate one.
    -   Enter the robot's password when prompted to copy the public key to the robot.
    -   *Success Message*: "Key transferred successfully."
3.  **Open Terminal (SSH)**:
    -   Clicking this opens a new `gnome-terminal` window already logged into the robot.

### 5.2. Managing Services
-   **Start a Service**: Click the **START** button on any service card. The LED will turn **Green**, and the button will change to **STOP** (Red).
-   **Stop a Service**: Click the **STOP** button. The LED will turn Gray.
-   **Remote Robot Node**: Starting this uses the configured SSH connection to launch the robot's bringup launch file.

### 5.3. Global Actions
-   **Build Workspace**: Click **Build Workspace** to run `colcon build --symlink-install` in the local workspace. Logs will appear in the Log Panel.
-   **KILL ALL**: Click this button to immediately terminate **all** running local and remote processes managed by the dashboard.

## 6. Configuration Details
-   **Local Services**: Currently hardcoded to run specific paths (e.g., `~/pinky_pro/ros-repo-3/...`). Ensure your directory structure matches or edit the `self.local_services` list in `ros2_system_manager.py`.
-   **Remote Command**: The remote launch command is defined in `handle_remote_toggle` inside the script.

## 7. Troubleshooting

| Issue | Possible Cause | Solution |
| :--- | :--- | :--- |
| **SSH Authentication Failed** | Wrong password or missing key. | Click "Setup SSH Keys" and seek the correct password. |
| **Service won't start** | Path not found. | Verify the paths in `ros2_system_manager.py` match your file system. |
| **"Module not found"** | Missing dependencies. | Run `pip install PyQt6 paramiko`. |
| **Remote Node Fails** | Network issue or ROS Domain mismatch. | Check IP reachability (`ping 192.168.4.1`) and ensure `ROS_DOMAIN_ID` matches. |
