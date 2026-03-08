"""PID zone lock API 통합 테스트.

로봇 진입 시 is_active 토글, 이탈 시 비활성화 흐름을 검증한다.
zones 테이블에 pid_lock_p4 / pid_lock_p6 / pid_lock_p8 이 미리 존재해야 한다.
(seed.py 실행 후 동작 가능)

실행:
    cd malle_service/tests
    python test_pid_zone_lock.py
"""

from base import ok, get, patch, health

PID_LOCK_NAMES = ['pid_lock_p4', 'pid_lock_p6', 'pid_lock_p8']


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def fetch_pid_lock_zones() -> dict[str, dict]:
    """name → zone dict 로 반환."""
    data  = get('/zones').json()
    zones = data if isinstance(data, list) else []
    return {z['name']: z for z in zones if z['name'] in PID_LOCK_NAMES}


def toggle(zone_id: int, active: bool):
    return ok(
        f'PATCH /zones/{zone_id} is_active={active}',
        patch(f'/zones/{zone_id}', {'is_active': active}),
    )


# ── 전제 조건 확인 ────────────────────────────────────────────────────────────

def check_seed_zones(pid_zones: dict) -> bool:
    """seed 후 pid_lock zone 이 존재하는지 확인."""
    print('\n[pid_lock] seed zone 존재 확인')
    missing = [n for n in PID_LOCK_NAMES if n not in pid_zones]
    if missing:
        print(f'  [SKIP] zone 없음: {missing}')
        print('         → seed.py 를 먼저 실행하세요: python -m scripts.seed')
        return False
    for name, z in pid_zones.items():
        print(f'  → id={z["id"]} name={name} is_active={z["is_active"]}')
    print('  [PASS] 전제 조건 확인 OK')
    return True


# ── 개별 테스트 ───────────────────────────────────────────────────────────────

def test_initial_state_inactive(pid_zones: dict):
    """seed 직후 pid_lock zone 은 is_active=False 여야 한다."""
    print('\n[pid_lock] 초기 비활성 상태 확인')
    for name, z in pid_zones.items():
        assert z['is_active'] is False, \
            f'{name} is_active={z["is_active"]} (False 기대)'
    print('  [PASS] 전체 비활성 확인 OK')


def test_activate_zone(zone: dict):
    """진입 시 is_active=True 로 토글."""
    print(f'\n[pid_lock] 활성화 (id={zone["id"]} name={zone["name"]})')
    toggle(zone['id'], True)

    # 재조회로 확인
    data = get('/zones').json()
    updated = next((z for z in data if z['id'] == zone['id']), None)
    assert updated is not None
    assert updated['is_active'] is True, f'is_active={updated["is_active"]} (True 기대)'
    print('  [PASS] 활성화 확인 OK')
    return updated


def test_deactivate_zone(zone: dict):
    """이탈 시 is_active=False 로 복원."""
    print(f'\n[pid_lock] 비활성화 (id={zone["id"]} name={zone["name"]})')
    toggle(zone['id'], False)

    data = get('/zones').json()
    updated = next((z for z in data if z['id'] == zone['id']), None)
    assert updated is not None
    assert updated['is_active'] is False, f'is_active={updated["is_active"]} (False 기대)'
    print('  [PASS] 비활성화 확인 OK')


def test_zone_type_is_restricted(pid_zones: dict):
    """pid_lock zone 은 RESTRICTED 타입이어야 keepout mask 에 반영된다."""
    print('\n[pid_lock] zone_type 확인')
    for name, z in pid_zones.items():
        assert z['zone_type'] == 'RESTRICTED', \
            f'{name} zone_type={z["zone_type"]} (RESTRICTED 기대)'
    print('  [PASS] 전체 RESTRICTED 확인 OK')


def test_full_toggle_lifecycle(zone: dict):
    """비활성 → 활성 → 비활성 전체 라이프사이클."""
    print(f'\n{"─"*50}')
    print(f'[pid_lock] 전체 라이프사이클 (name={zone["name"]})')
    print(f'{"─"*50}')

    # 초기 비활성 보장
    toggle(zone['id'], False)

    # 활성화 (로봇 진입)
    toggle(zone['id'], True)
    data = get('/zones').json()
    z = next(x for x in data if x['id'] == zone['id'])
    assert z['is_active'] is True, '활성화 실패'
    print('  → 활성화 OK')

    # 비활성화 (로봇 이탈)
    toggle(zone['id'], False)
    data = get('/zones').json()
    z = next(x for x in data if x['id'] == zone['id'])
    assert z['is_active'] is False, '비활성화 실패'
    print('  → 비활성화 OK')

    print('  [PASS] 라이프사이클 완료')


def test_two_zones_simultaneously(pid_zones: dict):
    """로봇 2대가 서로 다른 구간에 동시 진입 — 두 zone 동시 활성."""
    print('\n[pid_lock] 두 zone 동시 활성 (로봇 2대 시나리오)')
    names = list(pid_zones.keys())
    if len(names) < 2:
        print('  [SKIP] zone 2개 미만')
        return

    z1, z2 = pid_zones[names[0]], pid_zones[names[1]]

    # 둘 다 활성화
    toggle(z1['id'], True)
    toggle(z2['id'], True)

    data = get('/zones').json()
    active_ids = {z['id'] for z in data if z.get('is_active')}
    assert z1['id'] in active_ids and z2['id'] in active_ids, \
        f'두 zone 모두 활성이어야 함 (active: {active_ids})'
    print(f'  → 두 zone 동시 활성 확인 OK (ids={z1["id"]}, {z2["id"]})')

    # 정리 (순서 다르게 해제)
    toggle(z2['id'], False)
    toggle(z1['id'], False)
    print('  → 순서 다르게 비활성화 OK')


def test_idempotent_deactivate(zone: dict):
    """이미 비활성인 zone 을 한 번 더 비활성화해도 안전해야 한다."""
    print(f'\n[pid_lock] 중복 비활성화 안전성 (id={zone["id"]})')
    toggle(zone['id'], False)
    toggle(zone['id'], False)  # 두 번째 호출
    data = get('/zones').json()
    z = next(x for x in data if x['id'] == zone['id'])
    assert z['is_active'] is False
    print('  [PASS] 중복 비활성화 안전 OK')


# ── 메인 ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    health()

    pid_zones = fetch_pid_lock_zones()
    if not check_seed_zones(pid_zones):
        raise SystemExit(1)

    test_zone_type_is_restricted(pid_zones)
    test_initial_state_inactive(pid_zones)

    first_zone = next(iter(pid_zones.values()))
    test_full_toggle_lifecycle(first_zone)
    test_activate_zone(first_zone)
    test_deactivate_zone(first_zone)
    test_two_zones_simultaneously(pid_zones)
    test_idempotent_deactivate(first_zone)

    print('\n완료.')
