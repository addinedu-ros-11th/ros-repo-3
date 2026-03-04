#!/usr/bin/env python3

# (출발 POI, 도착 POI) → pid_zone_radius (m)
PID_EDGES: dict[tuple[str, str], float] = {
    ('p3',  'p4'):  1.03,
    ('p4',  'p6'):  0.52,
    ('p6',  'p8'):  0.70,
    #('p12', 'p13'): 0.63,
}

# 특정 목적지 POI에 도착할 때 어느 방향에서 오든 적용할 PID 반경
# 좁은 구간이라 Nav2가 직접 진입하지 못하는 POI에 설정
PID_DESTINATIONS: dict[str, float] = {
    'p6':  1.5,
    'p8':  1.5,
}

DEFAULT_PID_RADIUS = 0.0  # 명시된 구간 외에는 PID 없이 Nav2만 사용

def get_pid_radius(prev_poi: str, next_poi: str) -> float:
    """(prev_poi, next_poi) 엣지에 맞는 PID 진입 반경 반환."""
    edge = (prev_poi, next_poi)
    return PID_EDGES.get(edge, PID_DESTINATIONS.get(next_poi, DEFAULT_PID_RADIUS))
