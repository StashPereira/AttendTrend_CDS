import { ReactNode } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { X } from "lucide-react";
import { pct, Summary, SubjectStat } from "./types";

export function Card({
  children,
  title,
  action,
  className = "",
}: {
  children: ReactNode;
  title?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={"card " + className}>
      {title && (
        <div className="card-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Empty({
  children = "No records yet. Add your academic data to get started.",
}: {
  children?: ReactNode;
}) {
  return <div className="empty">{children}</div>;
}
export function ErrorBox({ error, retry }: { error: any; retry?: () => void }) {
  return (
    <div role="alert" className="error">
      {error?.message || String(error)}{" "}
      {retry && <button onClick={retry}>Retry</button>}
    </div>
  );
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  return (
    <div className="overlay" onClick={close}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="card-heading">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="Close" onClick={close}>
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function Badge({ value }: { value: string }) {
  return <span className={"badge " + value}>{value.replaceAll("_", " ")}</span>;
}
export function Trend({
  data,
  target = 75,
}: {
  data: Summary["trend"];
  target?: number;
}) {
  if (!data.length)
    return (
      <Empty>Mark conducted classes to build your attendance trend.</Empty>
    );
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#138ce9" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#138ce9" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e4edf7" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(s) => s.slice(5)}
            tick={{ fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(n) => n + "%"}
            tick={{ fontSize: 12 }}
          />
          <Tooltip formatter={(v: any) => pct(Number(v))} />
          <ReferenceLine y={target} stroke="#ffba54" strokeDasharray="4 4" />
          <Area
            isAnimationActive={false}
            type="monotone"
            dataKey="percentage"
            stroke="#0885e5"
            strokeWidth={3}
            fill="url(#area)"
            dot={{ r: 4, fill: "#0885e5", stroke: "#fff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Bars({
  data,
}: {
  data: { name: string; percentage: number | null }[];
}) {
  if (!data.length) return <Empty />;
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data}>
          <CartesianGrid vertical={false} stroke="#e4edf7" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(n) => n + "%"}
            tick={{ fontSize: 11 }}
          />
          <Tooltip formatter={(v: any) => pct(Number(v))} />
          <Bar
            isAnimationActive={false}
            dataKey="percentage"
            fill="#258eec"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Progress({ subject }: { subject: SubjectStat }) {
  return (
    <div className="subject-progress">
      <b>{subject.name}</b>
      <strong>{pct(subject.percentage)}</strong>
      <div className="progress">
        <span
          style={{
            width: `${subject.percentage || 0}%`,
            background: subject.on_track ? "#20af66" : "#f5ad40",
          }}
        />
      </div>
      <small>
        {subject.attended} / {subject.conducted} classes
      </small>
    </div>
  );
}
export function Submit({
  busy,
  label = "Save",
}: {
  busy: boolean;
  label?: string;
}) {
  return (
    <button className="primary" disabled={busy} type="submit">
      {busy ? "Saving…" : label}
    </button>
  );
}
