import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "test_robots.py",
    "test_dispatcher.py",
    "test_sessions.py",
    "test_guide.py",
    "test_pickup.py",
    "test_lockbox.py",
    "test_pois_stores.py",
    "test_zones_events.py",
]

tests_dir = Path(__file__).parent
results = []

print("=" * 50)
print("  Mall-E API 전체 테스트")
print("=" * 50)

for script in SCRIPTS:
    print(f"\n{'─'*50}")
    print(f"▶ {script}")
    print(f"{'─'*50}")
    result = subprocess.run(
        [sys.executable, str(tests_dir / script)],
        cwd=str(tests_dir),
    )
    results.append((script, result.returncode == 0))

print(f"\n{'='*50}")
print("  결과 요약")
print(f"{'='*50}")
for script, passed in results:
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {script}")

failed = [s for s, p in results if not p]
if failed:
    print(f"\n실패: {len(failed)}개")
    sys.exit(1)
else:
    print(f"\n전체 통과!")
