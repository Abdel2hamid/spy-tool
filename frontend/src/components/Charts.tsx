'use client';

import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface ChartProps {
  data: any[];
  dataKey: string;
  xAxisKey?: string;
  type?: 'line' | 'area' | 'bar';
  color?: string;
  height?: number;
  showGrid?: boolean;
}

export function SimpleChart({
  data,
  dataKey,
  xAxisKey = 'name',
  type = 'line',
  color = '#6366f1',
  height = 300,
  showGrid = true,
}: ChartProps) {
  const ChartComponent = type === 'area' ? AreaChart : type === 'bar' ? BarChart : LineChart;
  const DataComponent = type === 'area' ? Area : type === 'bar' ? Bar : Line;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ChartComponent data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#e5e7eb"
            vertical={false}
            className="dark:stroke-gray-800"
          />
        )}
        <XAxis
          dataKey={xAxisKey}
          tick={{ fontSize: 12, fill: '#9ca3af' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
          className="dark:text-gray-400"
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          className="dark:text-gray-400"
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
          }}
          labelStyle={{ color: '#374151', fontWeight: 600 }}
        />
        {type === 'area' && <Area type="monotone" dataKey={dataKey} stroke={color} fill={`${color}20`} strokeWidth={2} dot={false} activeDot={{ r: 6, fill: color, strokeWidth: 2, stroke: '#fff' }} />}
        {type === 'bar' && <Bar type="monotone" dataKey={dataKey} stroke={color} fill={color} strokeWidth={2} radius={[4, 4, 0, 0]} />}
        {type === 'line' && <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={{ r: 4, fill: color, strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6, fill: color, strokeWidth: 2, stroke: '#fff' }} />}
      </ChartComponent>
    </ResponsiveContainer>
  );
}

interface RankHistoryChartProps {
  dates: string[];
  ranks: number[];
  height?: number;
}

export function RankHistoryChart({
  dates,
  ranks,
  height = 300,
}: RankHistoryChartProps) {
  const data = dates.map((date, index) => ({
    date: date.slice(5),
    rank: ranks[index],
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="#e5e7eb"
          vertical={false}
          className="dark:stroke-gray-800"
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: '#9ca3af' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
          className="dark:text-gray-400"
        />
        <YAxis
          reversed
          tick={{ fontSize: 12, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          className="dark:text-gray-400"
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
          }}
        />
        <Line
          type="monotone"
          dataKey="rank"
          stroke="#6366f1"
          strokeWidth={2}
          dot={{ r: 3, fill: '#6366f1', strokeWidth: 2, stroke: '#fff' }}
          activeDot={{ r: 6, fill: '#6366f1', strokeWidth: 2, stroke: '#fff' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
