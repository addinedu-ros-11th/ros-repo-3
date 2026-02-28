import cv2
from IPython.display import display, clear_output, Image
import time
from picamera2 import Picamera2

import numpy as np
from glob import glob

class Camera:
    def __init__(self):
        try:
            self.picam2 = Picamera2()
        except:
            raise RuntimeError("현재 카메라가 사용 중입니다. 사용 중인 커널을 종료 후 다시 실행해 주세요")
        
        self.calibration_matrix = None
        self.dist_coeffs = None
        
        self.start_camera = False

    def start(self, width=640, height=480):
        self.picam2.configure(self.picam2.create_preview_configuration(main={"format": "RGB888", "size": (width, height)}))
        self.picam2.start()
        self.start_camera = True

    def display_jupyter(self, frame):
        _, buffer = cv2.imencode('.jpg', frame)
        clear_output(wait=True)
        display(Image(data=buffer, width=500))

    def get_frame(self):
        if not self.start_camera:
            raise RuntimeError("카메라를 시작해 주세요")
        
        frame = self.picam2.capture_array()
        frame = cv2.rotate(frame, cv2.ROTATE_180)

        return frame

    def play_jupyter(self, play_time=3):
        start_time = time.time()
        while time.time() - start_time < play_time:
            frame = self.get_frame()
            self.display_jupyter(frame)
    
            time.sleep(0.01)

    def calibration_camera(self, img_path, checkerboard_size=(8, 6), square_size=25):
        obj_points = []  # 3D 좌표 공간의 점들 (체커보드의 코너들)
        img_points = []  # 이미지 평면의 점들 (체커보드의 코너들)
    
        # 코너 검출 기준 설정
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

        # 3D 체커보드 좌표 초기화
        objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1, 2) * square_size

        # 이미지 파일 경로들 읽기
        images = glob(img_path + '/*.jpg')
        
        for image in images:
            img = cv2.imread(image)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 체커보드 코너 찾기
            ret, corners = cv2.findChessboardCorners(gray, checkerboard_size, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)

            if ret:
                obj_points.append(objp)  # 3D 점 추가
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)  # 코너 정밀화
                img_points.append(corners2)  # 2D 점 추가

                # 이미지에 체커보드 코너 그리기
                img = cv2.drawChessboardCorners(img, checkerboard_size, corners2, ret)

            self.display_jupyter(img)# 이미지 표시
            time.sleep(0.5)  # 0.5초 대기

        # 카메라 캘리브레이션 실행
        ret, camera_matrix, distortion_coefficients, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, gray.shape[::-1], None, None)
        
        # 카메라 캘리브레이션 결과 저장
        np.savez("./camera_calibration.npz", camera_matrix=camera_matrix, distortion_coefficients=distortion_coefficients, rvecs=rvecs, tvecs=tvecs)

    def calibration(self, save_path="./", num_images=10, checkerboard_size=(8, 6), square_size=25): 
        start_time = time.time()
        last_save_time = time.time()
        count = 0

        while time.time() - start_time < num_images + 1:
            frame = self.get_frame()
            save_frame = frame.copy()

            font = cv2.FONT_HERSHEY_SIMPLEX
            text = str(count)
            font_scale = 1
            color = (255, 0, 0)
            thickness = 2
            
            cv2.putText(frame, text, (500, 100), font, font_scale, color, thickness)

            current_time = time.time()
            
            if current_time - last_save_time >= 1.0:
                count += 1
                filename = f"{save_path}image_{count}.jpg"
                cv2.imwrite(filename, save_frame)
                print(f"{filename} 저장 완료")
    
                last_save_time = current_time
            
            self.display_jupyter(frame)
            
            time.sleep(0.01)

        self.calibration_camera(save_path, checkerboard_size=checkerboard_size, square_size=square_size)
        print("Camera Calibration Finished")
        
    def set_calibration(self, file_path="camera_calibration.npz"):
        with np.load(file_path) as data:
            self.calibration_matrix = data['camera_matrix']
            self.dist_coeffs = data['distortion_coefficients']

    def detect_aruco(self, frame, aruco_dict_type=cv2.aruco.DICT_5X5_250, marker_size=0.02):
        if self.calibration_matrix is None or self.dist_coeffs is None:
            print("please set calibration file")
            return
        
        output_frame, pose = self.pose_estimation(frame, aruco_dict_type, self.calibration_matrix, self.dist_coeffs, marker_size)
    
        if pose is None:
            print("not detect aruco")
    
        return output_frame, pose

    def pose_estimation(self, frame, aruco_dict_type, matrix_coefficients, distortion_coefficients, marker_size=0.02):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
        dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_type)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    
        corners, ids, rejected_img_points = detector.detectMarkers(gray)

        pose_list = []
    
        if ids is not None:
            for i in range(len(ids)): 
                obj_points = np.array([
                    [-marker_size / 2, marker_size / 2, 0], 
                    [marker_size / 2, marker_size / 2, 0], 
                    [marker_size / 2, -marker_size / 2, 0], 
                    [-marker_size / 2, -marker_size / 2, 0]
                ], dtype=np.float32)
    
                success, rvec, tvec = cv2.solvePnP(obj_points, corners[i][0], matrix_coefficients, distortion_coefficients)
                
                if success:
                    aruco_id = ids[i][0]
                    x, y, z = tvec.flatten() * 100  # cm로 변환
                    text = f"id: {aruco_id} x: {x:.2f}, y: {y:.2f}, z: {z:.2f}"
                    cv2.putText(frame, text, (int(corners[i][0][0][0]), int(corners[i][0][0][1]) - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                    cv2.aruco.drawDetectedMarkers(frame, corners)
    
                    pose = [aruco_id, x, y, z]
                    pose_list.append(pose)
    
        else:
            return frame, None
        
        return frame, pose_list


    def detect_aruco_target(self, frame, target_id, aruco_dict_type=cv2.aruco.DICT_5X5_250, marker_size=0.02):
    
        if self.calibration_matrix is None or self.dist_coeffs is None:
            print("please set calibration file")
            return
        
        output_frame, pose = self.target_pose_estimation(frame, aruco_dict_type, self.calibration_matrix, self.dist_coeffs, target_id, marker_size)

        return pose, output_frame

    def target_pose_estimation(self, frame, aruco_dict_type, matrix_coefficients, distortion_coefficients, target_id, marker_size=0.02):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
        dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_type)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    
        corners, ids, rejected_img_points = detector.detectMarkers(gray)

        if ids is not None and target_id in ids:
            i = np.where(ids == target_id)[0][0]

            obj_points = np.array([
                [-marker_size / 2, marker_size / 2, 0], 
                [marker_size / 2, marker_size / 2, 0], 
                [marker_size / 2, -marker_size / 2, 0], 
                [-marker_size / 2, -marker_size / 2, 0]
            ], dtype=np.float32)
    
            success, rvec, tvec = cv2.solvePnP(obj_points, corners[i][0], matrix_coefficients, distortion_coefficients)
            
            if success:
                x, y, z = tvec.flatten() * 100  # cm로 변환
                text = f"id: {ids[i][0]} x: {x:.2f}, y: {y:.2f}, z: {z:.2f}"
                cv2.putText(frame, text, (int(corners[i][0][0][0]), int(corners[i][0][0][1]) - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                cv2.aruco.drawDetectedMarkers(frame, corners)

                pose = [x, y, z]

        else:
            return frame, None
        
        return frame, pose

    def close(self):
        self.picam2.close()
        self.start_camera = False

    def __del__(self):
        self.close()