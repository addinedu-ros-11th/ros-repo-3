#!/usr/bin/env python3
import subprocess
import sys
import signal
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINKY_PRO_DIR = os.path.join(BASE_DIR, '../../pinky_pro')

MODULES = [
    {
        'name': 'Bringup',
        'path': os.path.join(PINKY_PRO_DIR, 'pinky_bringup/pinky_bringup/bringup.py'),
    },
    {
        'name': 'Follow',
        'path': os.path.join(BASE_DIR, 'malle_follow.py'),
    },
]

processes = []


def start_modules():
    print("  Malle Robot 주행 시스템 시작")

    for mod in MODULES:
        path = os.path.normpath(mod['path'])
        if not os.path.exists(path):
            print(f"[ERROR] {mod['name']}: 파일 없음 - {path}")
            continue

        try:
            proc = subprocess.Popen(
                [sys.executable, path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            processes.append({'name': mod['name'], 'proc': proc})
            print(f"[OK] {mod['name']} 시작 (PID: {proc.pid})")
        except Exception as e:
            print(f"[ERROR] {mod['name']} 시작 실패: {e}")

    print(f"  총 {len(processes)}개 모듈 실행 중")


def stop_modules():
    print("  시스템 종료 중...")

    for p in processes:
        try:
            p['proc'].terminate()
            p['proc'].wait(timeout=3)
            print(f"[OK] {p['name']} 종료")
        except subprocess.TimeoutExpired:
            p['proc'].kill()
            print(f"[KILL] {p['name']} 강제 종료")
        except Exception as e:
            print(f"[ERROR] {p['name']} 종료 실패: {e}")


def signal_handler(sig, frame):
    stop_modules()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_modules()

    try:
        while True:
            for p in processes:
                if p['proc'].poll() is not None:
                    print(f"[WARN] {p['name']} 종료됨 (code: {p['proc'].returncode})")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_modules()


if __name__ == '__main__':
    main()
