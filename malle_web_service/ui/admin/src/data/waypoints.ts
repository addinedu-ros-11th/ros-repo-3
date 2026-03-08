// admin/src/data/waypoints.ts
// Source: malle_bot/src/malle_controller/config/waypoint_graph.yaml
// 맵 좌표계: meters (x_m, y_m)

export interface Waypoint {
  id: string;
  x: number; // meters
  y: number; // meters
}

export const WAYPOINTS: Waypoint[] = [
  { id: 'p0',       x: 0.391, y: 0.351 },
  { id: 'p1',       x: 0.391, y: 0.845 },
  { id: 'p2',       x: 0.396, y: 1.950 },
  { id: 'p2_1',     x: 0.396, y: 1.700 },
  { id: 'p3',       x: 1.200, y: 1.950 },
  { id: 'p3_1',     x: 1.200, y: 1.700 },
  { id: 'p4',       x: 1.199, y: 0.850 },
  { id: 'p5',       x: 1.650, y: 0.850 },
  { id: 'p6',       x: 2.074, y: 0.856 },
  { id: 'p7',       x: 1.200, y: 1.400 },
  { id: 'p8',       x: 2.100, y: 0.247 },
  { id: 'p9',       x: 2.397, y: 0.254 },
  { id: 'p10',      x: 2.388, y: 1.297 },
  { id: 'p11',      x: 1.804, y: 1.950 },
  { id: 'p11_1',    x: 1.804, y: 1.700 },
  { id: 'p12',      x: 0.917, y: 0.300 },
  { id: 'p13',      x: 0.917, y: 0.845 },
  { id: 'p14',      x: 1.199, y: 0.300 },
  { id: 'p15',      x: 2.000, y: 1.400 },
  { id: 'p16',      x: 1.800, y: 0.300 },
  { id: 'charger1', x: 0.250, y: 0.650 },
  { id: 'charger2', x: 0.450, y: 0.650 },
];