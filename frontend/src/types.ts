export type User = { id: number; name: string; email: string; csrf: string };
export type Semester = {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
};
export type Subject = {
  id: number;
  code: string;
  name: string;
  kind: string;
  instructor: string;
  semester_id: number;
  planned_lectures?: number | null;
};
export type Recovery = {
  required_consecutive: number | null;
  required_of_remaining: number;
  recoverable: boolean;
  safe_to_skip: number;
  maximum_final_absences: number;
  best_case: number | null;
  worst_case: number | null;
  remaining: number;
};
export type SubjectStat = Subject & {
  planning_warnings?: string[];
  scheduled_remaining?: number;
  calendar_skip_allowance?: number;
  calendar_target?: number;
  attended: number;
  conducted: number;
  missed: number;
  percentage: number | null;
  pending: number;
  on_track: boolean;
  recovery: Recovery;
  forecast: number | null;
  forecast_method: string;
  risk: string;
  risk_explanation: string;
  baseline_through: string | null;
};
export type Summary = {
  overall: {
    attended: number;
    conducted: number;
    missed: number;
    percentage: number | null;
    on_track: number;
    subject_count: number;
    at_risk: number;
    safe_to_skip: number;
    pending: number;
  };
  subjects: SubjectStat[];
  trend: { date: string; percentage: number | null }[];
  weekdays: { weekday: number; percentage: number | null; conducted: number }[];
  target: number;
  safety_buffer: number;
  calculation_policy: string;
};
export type ClassRow = {
  id: number;
  subject_id: number;
  subject: string;
  code: string;
  starts_at: string;
  ends_at: string;
  status: string;
  room: string;
  future: boolean;
  cancelled: boolean;
};
export const pct = (n: number | null | undefined) =>
  n == null ? "—" : `${Number(n.toFixed(1))}%`;
export const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export function todayInZone(zone = "Asia/Kolkata") {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
