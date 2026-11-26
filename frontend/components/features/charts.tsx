"use client";
import * as React from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export const PALETTE = ["#b5573a", "#6f6254", "#7f9a82", "#c9a15b", "#8b7aa8"];
const tickStyle = { fontSize: 12, fill: "currentColor" };

function Frame({ children, height = 260, label }: { children: React.ReactElement; height?: number; label: string }) {
  return (
    <div className="text-muted" style={{ height }} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
    </div>
  );
}

const tooltipStyle = {
  contentStyle: { background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12, color: "hsl(var(--fg))" },
  cursor: { fill: "hsl(var(--sunken))" },
};

export interface BarDatum { name: string; [k: string]: string | number | null }

export function MetricBars({ data, series, format = (v: number) => String(v), height, label, domain }: {
  data: BarDatum[]; series: { key: string; name: string }[]; format?: (v: number) => string; height?: number; label: string; domain?: [number, number];
}) {
  return (
    <Frame height={height} label={label}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.12} />
        <XAxis dataKey="name" tick={tickStyle} tickLine={false} axisLine={false} />
        <YAxis tick={tickStyle} tickLine={false} axisLine={false} tickFormatter={(v) => format(Number(v))} domain={domain} width={54} />
        <Tooltip {...tooltipStyle} formatter={(v) => (v === null || v === undefined ? "n/a" : format(Number(v)))} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={PALETTE[i % PALETTE.length]} radius={[6, 6, 0, 0]} maxBarSize={44} />)}
      </BarChart>
    </Frame>
  );
}

export function Donut({ data, label }: { data: { name: string; value: number }[]; label: string }) {
  return (
    <Frame height={240} label={label}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90} paddingAngle={3} stroke="none">
          {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
        <Tooltip {...tooltipStyle} formatter={(v) => `${v}%`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </Frame>
  );
}

export function Lines({ data, series, format = (v: number) => String(v), label, height }: {
  data: Record<string, number | string | null>[]; series: { key: string; name: string }[]; format?: (v: number) => string; label: string; height?: number;
}) {
  return (
    <Frame height={height} label={label}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.12} />
        <XAxis dataKey="x" tick={tickStyle} tickLine={false} axisLine={false} />
        <YAxis tick={tickStyle} tickLine={false} axisLine={false} tickFormatter={(v) => format(Number(v))} width={54} />
        <Tooltip {...tooltipStyle} formatter={(v) => (v === null || v === undefined ? "n/a" : format(Number(v)))} labelFormatter={(l) => `Run #${l}`} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={{ r: 3 }} connectNulls />)}
      </LineChart>
    </Frame>
  );
}
