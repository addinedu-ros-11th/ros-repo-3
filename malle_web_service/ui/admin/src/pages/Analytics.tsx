import { useState, useMemo } from 'react';
import { MI } from '@/components/MaterialIcon';
import PageHeader from '@/components/PageHeader';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { format } from 'date-fns';
import type { DateRange } from 'react-day-picker';

// Data generators per range
function generateData(range: string, customRange?: DateRange) {
  // Seed-like multiplier per range for variety
  const mult = range === 'Today' ? 0.15 : range === 'This Week' ? 1 : range === 'This Month' ? 4.2 : 2.5;
  const variance = range === 'Today' ? 0.3 : 0.15;

  const v = (base: number) => {
    const jitter = 1 + (Math.sin(base * 7 + mult * 3) * variance);
    return Math.round(base * mult * jitter * 10) / 10;
  };

  let dayLabels: string[];
  if (range === 'Today') {
    dayLabels = ['6AM', '8AM', '10AM', '12PM', '2PM', '4PM', '6PM', '8PM'];
  } else if (range === 'This Week') {
    dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  } else if (range === 'This Month') {
    dayLabels = ['Week 1', 'Week 2', 'Week 3', 'Week 4'];
  } else {
    // Custom — generate day labels from range
    if (customRange?.from && customRange?.to) {
      const diffDays = Math.ceil((customRange.to.getTime() - customRange.from.getTime()) / (1000 * 60 * 60 * 24)) + 1;
      if (diffDays <= 7) {
        dayLabels = Array.from({ length: diffDays }, (_, i) => {
          const d = new Date(customRange.from!);
          d.setDate(d.getDate() + i);
          return format(d, 'MM/dd');
        });
      } else {
        const weeks = Math.ceil(diffDays / 7);
        dayLabels = Array.from({ length: Math.min(weeks, 8) }, (_, i) => `Week ${i + 1}`);
      }
    } else {
      dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    }
  }

  const baseMissions = range === 'Today' ? [12, 18, 25, 30, 28, 22, 15, 8] : [180, 220, 195, 250, 210, 160, 140];
  const baseEstop = range === 'Today' ? [0, 1, 2, 1, 0, 1, 0, 0] : [2, 5, 1, 3, 4, 0, 1];

  const missions = dayLabels.map((label, i) => ({
    day: label,
    missions: Math.round((baseMissions[i % baseMissions.length] || 150) * (range === 'Today' ? 1 : range === 'This Month' ? 3.5 : range === 'Custom' ? 1.8 : 1) * (1 + Math.sin(i * 2.3) * 0.2)),
  }));

  const estop = dayLabels.map((label, i) => ({
    day: label,
    count: Math.max(0, Math.round((baseEstop[i % baseEstop.length] || 1) * (range === 'This Month' ? 2.5 : range === 'Custom' ? 1.5 : 1) * (1 + Math.cos(i * 1.7) * 0.3))),
  }));

  const robotDistances = [
    { robot: 'R-422', distance: v(5.2) },
    { robot: 'R-109', distance: v(4.8) },
    { robot: 'R-305', distance: v(4.1) },
    { robot: 'R-118', distance: v(3.9) },
    { robot: 'R-742', distance: v(2.1) },
    { robot: 'R-991', distance: v(1.3) },
  ];

  const guideVal = range === 'Today' ? 40 : range === 'This Week' ? 45 : range === 'This Month' ? 48 : 44;
  const followVal = range === 'Today' ? 35 : range === 'This Week' ? 30 : range === 'This Month' ? 28 : 32;
  const pickupVal = 100 - guideVal - followVal;
  const modeData = [
    { name: 'Guide', value: guideVal },
    { name: 'Follow', value: followVal },
    { name: 'Pickup', value: pickupVal },
  ];

  // KPIs
  const totalDistance = range === 'Today' ? '3.6 km' : range === 'This Week' ? '24.8 km' : range === 'This Month' ? '98.4 km' : '52.1 km';
  const missionSuccess = range === 'Today' ? '97.8%' : range === 'This Week' ? '96.2%' : range === 'This Month' ? '95.1%' : '96.5%';
  const etaError = range === 'Today' ? '±8s' : range === 'This Week' ? '±12s' : range === 'This Month' ? '±15s' : '±11s';
  const teleopCount = range === 'Today' ? '2' : range === 'This Week' ? '7' : range === 'This Month' ? '23' : '14';

  const distTrend = range === 'Today' ? '↑ 5%' : range === 'This Week' ? '↑ 12%' : range === 'This Month' ? '↑ 18%' : '↑ 9%';
  const successTrend = range === 'Today' ? '↑ 1.2%' : range === 'This Week' ? '↑ 3%' : range === 'This Month' ? '↓ 0.8%' : '↑ 2%';
  const etaTrend = range === 'Today' ? '↓ improved' : range === 'This Week' ? '↓ improved' : range === 'This Month' ? '↑ worse' : '↓ improved';
  const teleopTrend = range === 'Today' ? '↓ 50%' : range === 'This Week' ? '↓ 30%' : range === 'This Month' ? '↑ 10%' : '↓ 20%';

  const kpis = [
    { label: 'Total Distance', value: totalDistance, trend: distTrend, trendUp: true, icon: 'straighten' },
    { label: 'Mission Success', value: missionSuccess, trend: successTrend, trendUp: !successTrend.includes('↓ 0') && !successTrend.includes('↑ worse'), icon: 'check_circle' },
    { label: 'Avg ETA Error', value: etaError, trend: etaTrend, trendUp: etaTrend.includes('improved'), icon: 'timer' },
    { label: 'Teleop Interventions', value: teleopCount, trend: teleopTrend, trendUp: teleopTrend.startsWith('↓'), icon: 'settings_remote' },
  ];

  return { missions, estop, robotDistances, modeData, kpis };
}

const PIE_COLORS = ['hsl(239,84%,67%)', 'hsl(27,97%,61%)', 'hsl(217,91%,60%)'];

const timeRanges = ['Today', 'This Week', 'This Month', 'Custom'];

export default function AnalyticsPage() {
  const [activeRange, setActiveRange] = useState('This Week');
  const [customRange, setCustomRange] = useState<DateRange | undefined>();
  const [customOpen, setCustomOpen] = useState(false);

  const data = useMemo(() => generateData(activeRange, customRange), [activeRange, customRange]);

  const handleRangeClick = (range: string) => {
    if (range === 'Custom') {
      setActiveRange('Custom');
      setCustomOpen(true);
    } else {
      setActiveRange(range);
      setCustomOpen(false);
    }
  };

  const customLabel = customRange?.from && customRange?.to
    ? `${format(customRange.from, 'MMM dd')} – ${format(customRange.to, 'MMM dd')}`
    : 'Custom';

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Fleet performance metrics" />

      {/* Time range */}
      <div className="flex gap-2 mb-8 items-center">
        {timeRanges.map(range => {
          if (range === 'Custom') {
            return (
              <Popover key={range} open={customOpen} onOpenChange={setCustomOpen}>
                <PopoverTrigger asChild>
                  <button
                    onClick={() => handleRangeClick('Custom')}
                    className={`px-4 py-2 rounded-full text-sm font-bold transition-all flex items-center gap-2 ${
                      activeRange === 'Custom' ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-muted-foreground hover:bg-secondary'
                    }`}
                  >
                    <MI icon="date_range" className="text-base" />
                    {customLabel}
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="range"
                    selected={customRange}
                    onSelect={(range) => {
                      setCustomRange(range);
                      if (range?.from && range?.to) {
                        setCustomOpen(false);
                      }
                    }}
                    numberOfMonths={2}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            );
          }
          return (
            <button
              key={range}
              onClick={() => handleRangeClick(range)}
              className={`px-4 py-2 rounded-full text-sm font-bold transition-all ${
                activeRange === range ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-muted-foreground hover:bg-secondary'
              }`}
            >
              {range}
            </button>
          );
        })}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        {data.kpis.map(kpi => (
          <div key={kpi.label} className="bg-card rounded-3xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <MI icon={kpi.icon} className="text-primary text-xl" />
              </div>
              <span className={`text-xs font-bold ${kpi.trendUp ? 'text-emerald-500' : 'text-critical-red'}`}>{kpi.trend}</span>
            </div>
            <p className="text-sm text-muted-foreground">{kpi.label}</p>
            <p className="text-3xl font-bold text-foreground">{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-card rounded-3xl p-6 border border-border shadow-sm">
          <h3 className="text-lg font-bold text-foreground mb-4">
            {activeRange === 'Today' ? 'Missions per Hour' : activeRange === 'This Month' ? 'Missions per Week' : 'Missions per Day'}
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.missions}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
              <Bar dataKey="missions" fill="hsl(239,84%,67%)" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card rounded-3xl p-6 border border-border shadow-sm">
          <h3 className="text-lg font-bold text-foreground mb-4">E-Stop Frequency</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.estop}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
              <Line type="monotone" dataKey="count" stroke="hsl(0,84%,60%)" strokeWidth={2} dot={{ fill: 'hsl(0,84%,60%)', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card rounded-3xl p-6 border border-border shadow-sm">
          <h3 className="text-lg font-bold text-foreground mb-4">Distance by Robot</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.robotDistances} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
              <YAxis dataKey="robot" type="category" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" width={60} />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
              <Bar dataKey="distance" fill="hsl(217,91%,60%)" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card rounded-3xl p-6 border border-border shadow-sm">
          <h3 className="text-lg font-bold text-foreground mb-4">Mode Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={data.modeData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={4} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} fontSize={13}>
                {data.modeData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
