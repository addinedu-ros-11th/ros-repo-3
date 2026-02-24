#!/usr/bin/env python3
import subprocess
import sys
import signal
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINKY_PRO_DIR = os.path.join(BASE_DIR, '../../pinky_pro')

MODES = {
    'follow': {
        'name': 'Follow',
        'path': os.path.join(BASE_DIR, 'malle_follow.py'),
    },
    'parking': {
        'name': 'Parking',
        'path': os.path.join(BASE_DIR, 'malle_parking.py'),
    },
    'tdrive': {
        'name': 'T-Drive',
        'path': os.path.join(BASE_DIR, 'malle_tdrive.py'),
    },
    'linetrack': {
        'name': 'LineTrack',
        'path': os.path.join(BASE_DIR, 'malle_linetrack.py'),
    },
}

BRINGUP = {
    'name': 'Bringup',
    'path': os.path.join(PINKY_PRO_DIR, 'pinky_bringup/pinky_bringup/bringup.py'),
}

processes = []


def start_module(mod):
    path = os.path.normpath(mod['path'])
    if not os.path.exists(path):
        print(f"[ERROR] {mod['name']}: 파일 없음 - {path}")
        return False

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
        return True
    except Exception as e:
        print(f"[ERROR] {mod['name']} 시작 실패: {e}")
        return False


def start_modules(mode):
    print(f"  Malle Robot - {mode.upper()} 모드")

    start_module(BRINGUP)
    start_module(MODES[mode])

    print("=" * 40)
    print(f"  {len(processes)}개 모듈 실행 중 | Ctrl+C 종료")
    print("=" * 40)


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


def print_usage():
    print(__doc__)
    print("사용 가능한 모드:")
    for key, val in MODES.items():
        print(f"  {key:10} - {val['name']}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in MODES:
        print(f"[ERROR] 알 수 없는 모드: {mode}\n")
        print_usage()
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_modules(mode)

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
