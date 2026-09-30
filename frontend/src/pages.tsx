import { useEffect, useState, FormEvent } from "react";
import {
  Users,
  CalendarCheck,
  AlertCircle,
  TrendingUp,
  Plus,
  Trash2,
  Pencil,
  Upload,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
} from "lucide-react";
import { useApp } from "./App";
import { api, send, setCsrf, download } from "./api";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Empty,
  ErrorBox,
  Trend,
  Bars,
  Progress,
  Badge,
  Modal,
  Submit,
} from "./components";
import { pct, weekdays, todayInZone, User, ClassRow } from "./types";

function useSafeAction() {
  const { action } = useApp();
  return (work: () => Promise<any>, message?: string) =>
    action(work, message).catch(() => {});
}
function Stats({
  items,
}: {
  items: { title: string; value: any; detail: string; kind?: string }[];
}) {
  const icons = [Users, CalendarCheck, AlertCircle, TrendingUp];
  return (
    <div className="stats">
      {items.map((s, i) => {
        const Icon = icons[i % 4];
        return (
          <Card
            key={s.title}
            className={
              "stat " + (s.kind || ["green", "blue", "red", "amber"][i % 4])
            }
          >
            <div className="stat-label">{s.title}</div>
            <div className="stat-value">
              <span className="stat-icon">
                <Icon size={23} />
              </span>
              <strong>{s.value}</strong>
            </div>
            <small>{s.detail}</small>
          </Card>
        );
      })}
    </div>
  );
}
function AttendanceStats() {
  const { summary: s } = useApp();
  if (!s) return null;
  return (
    <Stats
      items={[
        {
          title: "Overall Attendance",
          value: pct(s.overall.percentage),
          detail: `${s.overall.attended} of ${s.overall.conducted} classes attended`,
        },
        {
          title: "Classes Attended",
          value: s.overall.attended,
          detail: "Conducted classes marked present",
        },
        {
          title: "Classes Missed",
          value: s.overall.missed,
          detail: "Absences this semester",
        },
        {
          title: "Subjects On Track",
          value: `${s.overall.on_track} / ${s.overall.subject_count}`,
          detail: `Meeting ${s.target}% target`,
        },
      ]}
    />
  );
}
function matches(text: string, search: string) {
  return text.toLowerCase().includes(search.toLowerCase());
}
function timeLabel(row: ClassRow) {
  return `${row.starts_at.slice(11, 16)}–${row.ends_at.slice(11, 16)}`;
}

export function Dashboard() {
  const { summary: s, classes, profile, go, search } = useApp();
  if (!s) return null;
  const today = todayInZone(profile?.timezone);
  const upcoming = classes
    .filter(
      (c) =>
        c.starts_at.slice(0, 10) >= today &&
        !c.cancelled &&
        matches(c.subject + " " + c.code, search),
    )
    .slice(0, 8);
  const subjects = s.subjects.filter((x) =>
    matches(x.name + " " + x.code, search),
  );
  return (
    <>
      <AttendanceStats />
      <div className="dashboard-grid">
        <div>
          <Card
            title="Attendance Trend"
            action={<small>Last {s.trend.length} marked dates</small>}
          >
            <Trend data={s.trend} target={s.target} />
          </Card>
          <Card
            title="Subject Progress"
            action={
              <button className="link" onClick={() => go("data")}>
                View all subjects →
              </button>
            }
          >
            <div className="subject-grid">
              {subjects.slice(0, 4).map((x) => (
                <Progress key={x.id} subject={x} />
              ))}
              {!subjects.length && (
                <Empty>
                  No subjects yet. Add subjects or import your academic data.
                </Empty>
              )}
            </div>
          </Card>
        </div>
        <Card className="recommendation">
          <b className="eyebrow">TODAY’S RECOMMENDATION</b>
          <h2>
            {s.overall.at_risk
              ? "Focus on your at-risk subjects."
              : s.overall.conducted
                ? "Keep attending scheduled classes."
                : "Start tracking your attendance."}
          </h2>
          <p>
            {s.overall.at_risk
              ? `${s.overall.at_risk} subjects need attention. Review their recovery plans.`
              : s.overall.conducted
                ? "Review pending records and keep your schedule up to date."
                : "Create subjects and a timetable, then mark completed classes."}
          </p>
          <div className="recommendation-bottom">
            <div className="mini-stats">
              <div>
                <small>Overall</small>
                <strong>{pct(s.overall.percentage)}</strong>
              </div>
              <div>
                <small>At risk</small>
                <strong>{s.overall.at_risk}</strong>
              </div>
              <div>
                <small>Safe to skip</small>
                <strong>{s.overall.safe_to_skip}</strong>
              </div>
            </div>
            <button onClick={() => go("planning")}>Recovery</button>{" "}
            <button className="outline" onClick={() => go("planning")}>
              Safe-Skip
            </button>
          </div>
        </Card>
      </div>
      <div className="two-col">
        <Card
          title="Upcoming / Today’s Classes"
          action={
            <button className="link" onClick={() => go("calendar")}>
              Calendar →
            </button>
          }
        >
          {upcoming.length ? (
            upcoming.map((c) => (
              <div key={c.id} className="list-row">
                <div>
                  <b>{c.subject}</b>
                  <small>
                    {c.starts_at.slice(0, 10)} · {timeLabel(c)} ·{" "}
                    {c.room || "No room set"}
                  </small>
                </div>
                <Badge value={c.status} />
              </div>
            ))
          ) : (
            <Empty>
              No upcoming classes. Add a timetable or additional class.
            </Empty>
          )}
        </Card>
        <Card title="Needs Attention">
          {s.subjects
            .filter((x) => x.risk === "high" || x.risk === "critical")
            .map((x) => (
              <div className="list-row" key={x.id}>
                <div>
                  <b>{x.name}</b>
                  <small>{x.risk_explanation}</small>
                </div>
                <Badge value={x.risk} />
              </div>
            ))}
          <p>
            {s.overall.pending} completed classes still need attendance marking.
          </p>
          <button onClick={() => go("attendance")}>Review attendance</button>
        </Card>
      </div>
    </>
  );
}

export function AttendancePage() {
  const { summary: s, classes, profile, search, busy } = useApp();
  const run = useSafeAction();
  const [date, setDate] = useState(todayInZone(profile?.timezone)),
    [marks, setMarks] = useState<Record<number, string>>({}),
    [filter, setFilter] = useState("all"),
    [subject, setSubject] = useState("all");
  const daily = classes.filter(
    (c) =>
      c.starts_at.slice(0, 10) === date &&
      matches(c.subject + " " + c.code, search),
  );
  const history = classes
    .filter(
      (c) =>
        !c.future &&
        matches(c.subject + " " + c.code, search) &&
        (filter === "all" || c.status === filter) &&
        (subject === "all" || c.subject_id === Number(subject)),
    )
    .sort((a, b) => b.starts_at.localeCompare(a.starts_at));
  useEffect(() => setMarks({}), [date]);
  const save = () =>
    run(
      () =>
        send(
          "/attendance",
          {
            records: daily.map((c) => ({
              occurrence_id: c.id,
              status: marks[c.id] || c.status,
            })),
          },
          "PUT",
        ),
      "Attendance saved; all calculations updated",
    ).then(() => setMarks({}));
  return (
    <>
      <AttendanceStats />
      <Card title="Attendance overview">
        <div className="subject-grid">
          {s?.subjects.map((x) => (
            <Progress key={x.id} subject={x} />
          ))}
        </div>
      </Card>
      <Card
        title="Mark a full day"
        action={
          <input
            type="date"
            aria-label="Attendance date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        }
      >
        <div className="toolbar">
          <button
            disabled={!daily.length || busy}
            onClick={() =>
              setMarks(
                Object.fromEntries(
                  daily.filter((c) => !c.future).map((c) => [c.id, "present"]),
                ),
              )
            }
          >
            Mark completed classes present
          </button>
          <small>Future classes can only be left pending or cancelled.</small>
        </div>
        {daily.length ? (
          daily.map((c) => (
            <div className="list-row" key={c.id}>
              <div>
                <b>{c.subject}</b>
                <small>
                  {timeLabel(c)} · {c.room || "Room not specified"}{" "}
                  {c.future ? "· upcoming / ongoing" : ""}
                </small>
              </div>
              <select
                aria-label={`Status for ${c.subject}`}
                value={marks[c.id] || c.status}
                onChange={(e) => setMarks({ ...marks, [c.id]: e.target.value })}
              >
                {["pending", "present", "absent", "excused", "cancelled"].map(
                  (status) => (
                    <option
                      key={status}
                      value={status}
                      disabled={
                        c.future && !["pending", "cancelled"].includes(status)
                      }
                    >
                      {status}
                    </option>
                  ),
                )}
              </select>
            </div>
          ))
        ) : (
          <Empty>No scheduled classes on this date.</Empty>
        )}
        <button
          className="primary"
          disabled={!daily.length || busy}
          onClick={save}
        >
          Save day
        </button>
      </Card>
      <Card
        title="Attendance Records"
        action={
          <div className="toolbar">
            <select
              aria-label="Filter subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              <option value="all">All subjects</option>
              {s?.subjects.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter status"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              {[
                "all",
                "present",
                "absent",
                "excused",
                "cancelled",
                "pending",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
        }
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Subject</th>
                <th>Time</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 300).map((c) => (
                <tr key={c.id}>
                  <td>{c.starts_at.slice(0, 10)}</td>
                  <td>{c.subject}</td>
                  <td>{timeLabel(c)}</td>
                  <td>
                    <Badge value={c.status} />
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Edit attendance ${c.id}`}
                      onClick={() => {
                        setDate(c.starts_at.slice(0, 10));
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-button danger"
                      disabled={busy}
                      aria-label={`Clear attendance ${c.id}`}
                      onClick={() =>
                        run(
                          () =>
                            api("/attendance/" + c.id, { method: "DELETE" }),
                          "Attendance cleared",
                        )
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!history.length && <Empty>No matching attendance records.</Empty>}
        </div>
        {history.length > 300 && (
          <small>
            Showing newest 300 records. Use filters or export the full dataset.
          </small>
        )}
      </Card>
    </>
  );
}

function CalendarGrid({
  month,
  onSelect,
  selected,
  safeIds,
}: {
  month: string;
  onSelect: (d: string) => void;
  selected: string;
  safeIds?: Set<number>;
}) {
  const { classes, events } = useApp();
  const date = new Date(month + "T12:00:00");
  const y = date.getFullYear(),
    m = date.getMonth();
  const first = new Date(y, m, 1);
  const offset = (first.getDay() + 6) % 7;
  const count = new Date(y, m + 1, 0).getDate();
  return (
    <>
      <div className="calendar-days">
        {weekdays.map((d) => (
          <b key={d}>{d}</b>
        ))}
      </div>
      <div className="calendar-grid">
        {Array.from({ length: offset + count }, (_, i) => {
          const n = i - offset + 1;
          if (n < 1) return <div key={i} className="calendar-blank" />;
          const day = `${y}-${String(m + 1).padStart(2, "0")}-${String(n).padStart(2, "0")}`;
          const rows = classes.filter((c) => c.starts_at.slice(0, 10) === day);
          const dayEvents = events.filter(
            (e) => e.start_date <= day && e.end_date >= day,
          );
          const safe = rows.filter((c) => safeIds?.has(c.id));
          return (
            <button
              key={day}
              className={
                "calendar-cell " +
                (selected === day ? "selected " : "") +
                (safe.length ? "safe-day" : "")
              }
              onClick={() => onSelect(day)}
            >
              <span>{n}</span>
              {dayEvents.slice(0, 1).map((e) => (
                <small key={e.id} className="event-chip">
                  {e.title}
                </small>
              ))}
              {safeIds
                ? safe.length > 0 && (
                    <small className="safe-text">
                      {safe.length} within buffer
                    </small>
                  )
                : rows.slice(0, 3).map((c) => (
                    <small
                      key={c.id}
                      className={
                        c.cancelled ? "cancelled class-dot" : "class-dot"
                      }
                    >
                      {c.starts_at.slice(11, 16)} {c.subject}
                    </small>
                  ))}
              {!safeIds && rows.length > 3 && (
                <small>+{rows.length - 3} more</small>
              )}
            </button>
          );
        })}
      </div>
    </>
  );
}

export function CalendarPage() {
  const {
    classes,
    timetable,
    events,
    subjects,
    semester,
    profile,
    open,
    busy,
    search,
  } = useApp();
  const run = useSafeAction();
  const [tabs, setTabs] = useState("calendar"),
    [view, setView] = useState("month"),
    [day, setDay] = useState(todayInZone(profile?.timezone)),
    [month, setMonth] = useState(day.slice(0, 7) + "-01");
  const selected = new Date(day + "T12:00:00");
  const weekStart = new Date(selected);
  weekStart.setDate(selected.getDate() - ((selected.getDay() + 6) % 7));
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const rows = classes.filter(
    (c) =>
      matches(c.subject + " " + c.code, search) &&
      (view === "week"
        ? new Date(c.starts_at) >= weekStart && new Date(c.starts_at) < weekEnd
        : c.starts_at.slice(0, 10) === day),
  );
  function move(delta: number) {
    const d = new Date(month + "T12:00:00");
    d.setMonth(d.getMonth() + delta);
    setMonth(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`,
    );
  }
  return (
    <>
      <div className="tabs">
        <button
          className={tabs === "calendar" ? "active" : ""}
          onClick={() => setTabs("calendar")}
        >
          Calendar
        </button>
        <button
          className={tabs === "timetable" ? "active" : ""}
          onClick={() => setTabs("timetable")}
        >
          Timetable
        </button>
      </div>
      {tabs === "calendar" ? (
        <div className="calendar-layout">
          <Card
            title={new Date(month + "T12:00:00").toLocaleDateString(undefined, {
              month: "long",
              year: "numeric",
            })}
            action={
              <div className="toolbar">
                <button
                  className="icon-button"
                  aria-label="Previous month"
                  onClick={() => move(-1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  className="icon-button"
                  aria-label="Next month"
                  onClick={() => move(1)}
                >
                  <ChevronRight size={18} />
                </button>
                <select
                  aria-label="Calendar view"
                  value={view}
                  onChange={(e) => setView(e.target.value)}
                >
                  <option value="month">Month</option>
                  <option value="week">Week</option>
                  <option value="day">Day</option>
                </select>
              </div>
            }
          >
            {view === "month" ? (
              <CalendarGrid month={month} selected={day} onSelect={setDay} />
            ) : (
              <>
                <input
                  aria-label="Calendar date"
                  type="date"
                  value={day}
                  onChange={(e) => setDay(e.target.value)}
                />
                <div className="schedule-list">
                  {rows.map((c) => (
                    <ClassDetail row={c} key={c.id} />
                  ))}
                  {!rows.length && <Empty>No classes in this {view}.</Empty>}
                </div>
              </>
            )}
          </Card>
          <Card
            title="Classes & Events"
            action={
              <button
                className="link"
                disabled={!subjects.length}
                onClick={() => open("class")}
              >
                + Class
              </button>
            }
          >
            <input
              type="date"
              aria-label="Class detail date"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
            {classes
              .filter(
                (c) =>
                  c.starts_at.slice(0, 10) === day &&
                  matches(c.subject + " " + c.code, search),
              )
              .map((c) => (
                <ClassDetail key={c.id} row={c} />
              ))}
            {events
              .filter((e) => e.start_date <= day && e.end_date >= day)
              .map((e) => (
                <div className="list-row" key={e.id}>
                  <div>
                    <b>{e.title}</b>
                    <small>
                      {e.kind} · {e.start_date}–{e.end_date}
                    </small>
                  </div>
                  <button
                    aria-label={`Delete event ${e.id}`}
                    className="icon-button danger"
                    onClick={() =>
                      run(() => api("/events/" + e.id, { method: "DELETE" }))
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            {!classes.some((c) => c.starts_at.slice(0, 10) === day) && (
              <Empty>No scheduled classes.</Empty>
            )}
            <button onClick={() => open("event")}>Add event / holiday</button>
          </Card>
        </div>
      ) : (
        <Card
          title="Weekly timetable"
          action={
            <div className="toolbar">
              <button
                disabled={busy}
                onClick={() =>
                  run(
                    () => send(`/semesters/${semester!.id}/generate`, {}),
                    "Schedule regenerated without overwriting marked attendance",
                  )
                }
              >
                Generate classes
              </button>
              <button
                className="primary"
                disabled={!subjects.length}
                onClick={() => open("timetable")}
              >
                + Slot
              </button>
            </div>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Weekday</th>
                  <th>Time</th>
                  <th>Subject</th>
                  <th>Room</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {timetable.map((t) => (
                  <tr key={t.id}>
                    <td>{weekdays[t.weekday]}</td>
                    <td>
                      {t.start_time.slice(0, 5)}–{t.end_time.slice(0, 5)}
                    </td>
                    <td>{subjects.find((s) => s.id === t.subject_id)?.name}</td>
                    <td>{t.room || "—"}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Edit slot ${t.id}`}
                        onClick={() => open("timetable", t)}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        className="icon-button danger"
                        aria-label={`Delete slot ${t.id}`}
                        onClick={() =>
                          run(
                            () =>
                              api("/timetable/" + t.id, { method: "DELETE" }),
                            "Slot removed; historical records retained",
                          )
                        }
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!timetable.length && (
              <Empty>
                Add subjects, then create timetable slots. Class occurrences are
                generated automatically.
              </Empty>
            )}
          </div>
        </Card>
      )}
      <Card title="Academic events">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Start</th>
                <th>End</th>
                <th>Type</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{e.title}</td>
                  <td>{e.start_date}</td>
                  <td>{e.end_date}</td>
                  <td>
                    <Badge value={e.kind} />
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Edit event ${e.id}`}
                      onClick={() => open("event", e)}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      className="icon-button danger"
                      aria-label={`Remove ${e.title}`}
                      onClick={() =>
                        run(() => api("/events/" + e.id, { method: "DELETE" }))
                      }
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!events.length && <Empty>No academic events imported or added.</Empty>}
      </Card>
    </>
  );
}

function ClassDetail({ row: c }: { row: ClassRow }) {
  const { open } = useApp();
  return (
    <div className="class-detail">
      <div className="card-heading">
        <b>{c.subject}</b>
        <Badge value={c.status} />
      </div>
      <small>
        {c.starts_at.slice(0, 10)} · {timeLabel(c)}
      </small>
      <small>{c.room || "No room specified"}</small>
      <button className="link" onClick={() => open("class", c)}>
        Details / reschedule
      </button>
    </div>
  );
}

export function AnalyticsPage() {
  const { summary: s, search } = useApp();
  if (!s) return null;
  const w = s.weekdays.filter((w) => w.percentage != null);
  const best = [...w].sort((a, b) => b.percentage! - a.percentage!)[0];
  const worst = [...w].sort((a, b) => a.percentage! - b.percentage!)[0];
  const trend = s.trend;
  const change =
    trend.length > 1 ? trend.at(-1)!.percentage! - trend[0].percentage! : null;
  return (
    <>
      <Stats
        items={[
          {
            title: "Average attendance",
            value: pct(s.overall.percentage),
            detail: "Weighted by conducted class counts",
          },
          {
            title: "Best weekday",
            value: best ? weekdays[best.weekday] : "—",
            detail: best ? pct(best.percentage) : "No daily observations",
          },
          {
            title: "Needs attention",
            value: worst ? weekdays[worst.weekday] : "—",
            detail: worst ? pct(worst.percentage) : "No daily observations",
          },
          {
            title: "Trend change",
            value:
              change == null
                ? "—"
                : `${change > 0 ? "+" : ""}${change.toFixed(1)} pp`,
            detail: "Across available marked dates",
          },
        ]}
      />
      <div className="two-col">
        <Card title="Attendance Trend">
          <Trend data={s.trend} target={s.target} />
        </Card>
        <Card title="Weekday Comparison">
          <Bars
            data={w.map((w) => ({
              name: weekdays[w.weekday],
              percentage: w.percentage,
            }))}
          />
        </Card>
      </div>
      <Card title="Subject Breakdown">
        <div className="subject-grid">
          {s.subjects
            .filter((x) => matches(x.name + " " + x.code, search))
            .map((x) => (
              <div key={x.id}>
                <Progress subject={x} />
                <small>
                  Target gap:{" "}
                  {x.percentage == null
                    ? "—"
                    : `${(x.percentage - s.target).toFixed(1)} pp`}
                </small>
              </div>
            ))}
        </div>
      </Card>
      <div className="two-col">
        <Card title="Risk Distribution">
          <div className="risk-distribution">
            {["low", "medium", "high", "critical", "unknown"].map((r) => (
              <div key={r}>
                <Badge value={r} />
                <strong>
                  {s.subjects.filter((x) => x.risk === r).length} subjects
                </strong>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Record Health">
          <p>
            {s.overall.pending} past classes are pending and excluded from
            percentages.
          </p>
          <p>
            Imported aggregate baselines contribute to totals, but cannot supply
            daily or weekday trends.
          </p>
          <small>{s.calculation_policy}</small>
        </Card>
      </div>
    </>
  );
}

export function PlanningPage() {
  const { summary: s, classes, profile, search, semester } = useApp();
  const run = useSafeAction();
  const [subjectId, setSubjectId] = useState(0),
    [attend, setAttend] = useState(1),
    [miss, setMiss] = useState(0),
    [result, setResult] = useState<any>(null),
    [target, setTarget] = useState(s?.target || 75),
    [month, setMonth] = useState(
      todayInZone(profile?.timezone).slice(0, 7) + "-01",
    ),
    [day, setDay] = useState(todayInZone(profile?.timezone));
  const selected =
    s?.subjects.find((x) => x.id === subjectId) || s?.subjects[0];
  useEffect(() => {
    setResult(null);
  }, [
    subjectId,
    attend,
    miss,
    target,
    semester?.id,
    selected?.attended,
    selected?.conducted,
    selected?.recovery.remaining,
  ]);
  const safeIds = new Set<number>();
  s?.subjects.forEach((subject) => {
    classes
      .filter((c) => c.subject_id === subject.id && c.future && !c.cancelled)
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.id - b.id)
      .slice(0, subject.calendar_skip_allowance ?? 0)
      .forEach((c) => safeIds.add(c.id));
  });
  if (!s) return null;
  return (
    <>
      <div className="two-col">
        <Card title="What-If Simulator">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (selected)
                run(
                  () =>
                    send("/what-if", {
                      subject_id: selected.id,
                      attend,
                      miss,
                      target,
                    }),
                  "Scenario calculated",
                ).then((r) => r && setResult(r));
            }}
          >
            <label>
              Subject
              <select
                value={selected?.id || ""}
                onChange={(e) => setSubjectId(Number(e.target.value))}
              >
                {s.subjects.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="form-row">
              <label>
                Attend classes
                <input
                  type="number"
                  min={0}
                  max={selected?.recovery.remaining || 0}
                  value={attend}
                  onChange={(e) => setAttend(Number(e.target.value))}
                />
              </label>
              <label>
                Miss classes
                <input
                  type="number"
                  min={0}
                  max={selected?.recovery.remaining || 0}
                  value={miss}
                  onChange={(e) => setMiss(Number(e.target.value))}
                />
              </label>
            </div>
            <label>
              Target (%)
              <input
                type="number"
                min={0.01}
                max={100}
                step={0.01}
                value={target}
                onChange={(e) => setTarget(Number(e.target.value))}
              />
            </label>
            <small>
              {selected?.recovery.remaining || 0} scheduled remaining classes
              available.
            </small>
            <button className="primary" type="submit" disabled={!selected}>
              Calculate scenario
            </button>
          </form>
          {result && (
            <div className="scenario-result">
              <div>
                <small>Current</small>
                <strong>{pct(result.current)}</strong>
              </div>
              <div>
                <small>Projected</small>
                <strong>{pct(result.projected)}</strong>
              </div>
              <p>
                {result.meets_target ? "Target met" : "Below target"} ·{" "}
                {result.attended}/{result.conducted} classes
              </p>
              <Bars
                data={[
                  { name: "Current", percentage: result.current },
                  { name: "Projected", percentage: result.projected },
                ]}
              />
            </div>
          )}
        </Card>
        <Card title="Recovery & Safe Skip">
          <small>
            Target {s.target}% · safety buffer {s.safety_buffer} pp
          </small>
          <strong className="hero-number">
            {selected?.recovery.required_consecutive ?? "∞"}
          </strong>
          <p>Consecutive present classes needed to meet the target.</p>
          {selected && (
            <>
              <p>
                {selected.recovery.recoverable
                  ? "Recovery is possible with the scheduled remaining classes."
                  : "The target cannot be reached within the current schedule."}
              </p>
              <div className="metric-list">
                <div>
                  <span>Required of remaining</span>
                  <b>
                    {selected.recovery.required_of_remaining} /{" "}
                    {selected.recovery.remaining}
                  </b>
                </div>
                <div>
                  <span>Safe to skip now</span>
                  <b>{selected.recovery.safe_to_skip}</b>
                </div>
                <div>
                  <span>Maximum final absences</span>
                  <b>{selected.recovery.maximum_final_absences}</b>
                </div>
                <div>
                  <span>Best / worst final attendance</span>
                  <b>
                    {pct(selected.recovery.best_case)} /{" "}
                    {pct(selected.recovery.worst_case)}
                  </b>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
      <Card className="blue-banner">
        <h2>Your plan starts with consistent attendance.</h2>
        <p>
          Skip limits are subject-specific and assume every skipped class is
          absent. Pending records can change these limits when completed.
        </p>
      </Card>
      <Card
        title="Safe-to-Skip Calendar"
        action={
          <input
            type="month"
            aria-label="Safe to skip month"
            value={month.slice(0, 7)}
            onChange={(e) => setMonth(e.target.value + "-01")}
          />
        }
      >
        <p>
          Green dates stay within your target plus safety buffer, without assuming future attendance. Semester lecture totals cap the allowance; holidays and cancelled classes are excluded. Each timetable session counts as one lecture.
        </p>
        {s.subjects.flatMap((subject) => (subject.planning_warnings || []).map((warning, index) => (
          <div className="info" key={`${subject.id}-${index}`}>{subject.name}: {warning}</div>
        )))}
        <CalendarGrid
          month={month}
          selected={day}
          onSelect={setDay}
          safeIds={safeIds}
        />
        <div className="list-row">
          <div>
            <b>{day}</b>
            <small>
              {classes
                .filter(
                  (c) => c.starts_at.slice(0, 10) === day && safeIds.has(c.id),
                )
                .map((c) => c.subject)
                .join(", ") ||
                "No classes within the current skip allowance on this date."}
            </small>
          </div>
        </div>
      </Card>
      <Card title="Subject Recovery Plans">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Subject</th>
                <th>Current</th>
                <th>Consecutive needed</th>
                <th>Remaining</th>
                <th>Safe to skip</th>
                <th>Recovery</th>
              </tr>
            </thead>
            <tbody>
              {s.subjects
                .filter((x) => matches(x.name + " " + x.code, search))
                .map((x) => (
                  <tr key={x.id}>
                    <td>{x.name}</td>
                    <td>{pct(x.percentage)}</td>
                    <td>
                      {x.recovery.required_consecutive ?? "Not reachable"}
                    </td>
                    <td>{x.recovery.remaining}</td>
                    <td>{x.recovery.safe_to_skip}</td>
                    <td>
                      <Badge
                        value={
                          x.recovery.recoverable ? "possible" : "impossible"
                        }
                      />
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!s.subjects.length && <Empty />}
      </Card>
    </>
  );
}

export function PredictionsPage() {
  const { summary: s, search } = useApp();
  if (!s) return null;
  const remaining = s.subjects.reduce(
      (sum, x) => sum + x.recovery.remaining,
      0,
    ),
    conducted = s.overall.conducted + remaining;
  const known = s.subjects.every((x) => x.conducted > 0);
  const predicted =
    known && conducted
      ? (s.subjects.reduce(
          (sum, x) =>
            sum +
            ((x.forecast || 0) / 100) * (x.conducted + x.recovery.remaining),
          0,
        ) /
          conducted) *
        100
      : null;
  const best = conducted
    ? ((s.overall.attended + remaining) / conducted) * 100
    : null;
  const worst = conducted ? (s.overall.attended / conducted) * 100 : null;
  return (
    <>
      <Stats
        items={[
          {
            title: "Best-Case Final Attendance",
            value: pct(best),
            detail: "Attend every remaining class",
            kind: "green",
          },
          {
            title: "Expected Final Attendance",
            value: pct(predicted),
            detail: known
              ? "Smoothed statistical estimate"
              : "Insufficient observations in some subjects",
            kind: "blue",
          },
          {
            title: "Worst-Case Final Attendance",
            value: pct(worst),
            detail: "Miss every remaining class",
            kind: "red",
          },
          {
            title: "Remaining Classes",
            value: remaining,
            detail: "From actual schedule; cancellations excluded",
            kind: "amber",
          },
        ]}
      />
      <Card title="Subject Forecasts">
        <p>
          Forecasts estimate behavior from recorded present/absent counts. Best
          and worst cases are calculated bounds, not confidence intervals.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Subject</th>
                <th>Current</th>
                <th>Remaining</th>
                <th>Expected</th>
                <th>Best</th>
                <th>Worst</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {s.subjects
                .filter((x) => matches(x.name + " " + x.code, search))
                .map((x) => (
                  <tr key={x.id}>
                    <td>
                      {x.name}
                      <small>{x.forecast_method}</small>
                    </td>
                    <td>{pct(x.percentage)}</td>
                    <td>{x.recovery.remaining}</td>
                    <td>{pct(x.forecast)}</td>
                    <td>{pct(x.recovery.best_case)}</td>
                    <td>{pct(x.recovery.worst_case)}</td>
                    <td>
                      <Badge value={x.risk} />
                      <small>{x.risk_explanation}</small>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!s.subjects.length && <Empty />}
      </Card>
      <Card title="Forecast Method">
        <p>
          With recorded classes, the estimated probability of attending the next
          class is (present + 1) ÷ (conducted + 2). It is then applied to
          scheduled remaining classes. Fewer than ten observations are labelled
          as limited history. No observations means no point forecast.
        </p>
        <p>
          This model assumes future attendance behaves like the recorded
          history. Unmarked past classes and missing schedule entries can
          materially affect the result.
        </p>
      </Card>
    </>
  );
}

export function DataPage() {
  const {
    subjects,
    documents,
    reconciliation,
    semester,
    profile,
    open,
    search,
    busy,
    go,
  } = useApp();
  const run = useSafeAction();
  const [tab, setTab] = useState("setup"),
    [step, setStep] = useState("attendance"),
    [review, setReview] = useState<any>(null),
    [baseline, setBaseline] = useState<any>(null);
  const baselineQuery = useQuery<any[]>({
    queryKey: ["baselines", semester?.id],
    queryFn: () => api(`/baselines?semester_id=${semester?.id}`),
    enabled: !!semester,
  });
  const upload = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    data.set("semester_id", String(semester!.id));
    data.set("kind", step);
    const r = await run(
      () => api("/documents", { method: "POST", body: data }),
      "File uploaded; extraction queued",
    );
    if (r) form.reset();
  };
  return (
    <>
      <div className="tabs">
        {["setup", "subjects", "reconciliation", "datasets"].map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t === "setup" ? "Academic setup" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === "setup" && (
        <>
          <div className="info">
            Import your academic data, review the extracted rows, and confirm.
            CSV, PDF and timetable images are supported.
          </div>
          <Card title="Academic setup">
            <div className="setup-steps">
              <button onClick={() => go("profile")}>1 · Profile</button>
              {["attendance", "calendar", "timetable"].map((s, i) => (
                <button
                  key={s}
                  className={step === s ? "selected" : ""}
                  onClick={() => setStep(s)}
                >
                  {i + 2} · {s[0].toUpperCase() + s.slice(1)} import
                </button>
              ))}
              <button
                onClick={() =>
                  documents.find((d) => d.status === "review") &&
                  setReview(documents.find((d) => d.status === "review"))
                }
              >
                5 · Review & confirm
              </button>
            </div>
            <h3>{step[0].toUpperCase() + step.slice(1)} import</h3>
            <p>
              {step === "attendance"
                ? "Upload university attendance counts. Choose an initial baseline or a reconciliation snapshot after review."
                : step === "calendar"
                  ? "Upload holidays, exams and academic events. Holidays cancel unmarked scheduled classes."
                  : "Upload recurring weekly slots. Class occurrences will be generated within this semester."}
            </p>
            <form className="upload-form" onSubmit={upload}>
              <label>
                Document
                <input
                  type="file"
                  name="file"
                  required
                  accept=".pdf,.png,.jpg,.jpeg,.csv,.txt"
                />
              </label>
              <small>
                Maximum 10 MB · PDF up to 60 pages · PNG/JPEG up to 20
                megapixels
              </small>
              <button className="primary" disabled={busy} type="submit">
                <Upload size={16} /> Upload
              </button>
            </form>
          </Card>
          <Card title="Imports">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d) => (
                    <tr key={d.id}>
                      <td>
                        {d.name}
                        {d.error && <small className="danger">{d.error}</small>}
                      </td>
                      <td>{d.kind}</td>
                      <td>
                        <Badge value={d.status} />
                      </td>
                      <td>
                        {d.status === "review" && (
                          <button onClick={() => setReview(d)}>
                            Review & confirm
                          </button>
                        )}
                        {d.status === "confirmed" && (
                          <button onClick={() => setReview(d)}>
                            View reviewed rows
                          </button>
                        )}
                        {["failed", "review"].includes(d.status) && (
                          <button
                            onClick={() =>
                              run(
                                () => send(`/documents/${d.id}/retry`, {}),
                                "Import queued again",
                              )
                            }
                          >
                            {d.status === "review" ? "Re-extract" : "Retry"}
                          </button>
                        )}
                        <button
                          className="icon-button danger"
                          disabled={d.status === "processing"}
                          aria-label={`Delete import ${d.id}`}
                          onClick={() =>
                            run(
                              () =>
                                api("/documents/" + d.id, { method: "DELETE" }),
                              "Document deleted; confirmed academic data retained",
                            )
                          }
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!documents.length && <Empty>No imports yet.</Empty>}
          </Card>
        </>
      )}
      {tab === "setup" && subjects.length > 0 && (
        <Card title="How many lectures are planned per subject this semester?">
          <p>Enter the full semester total for each theory and practical subject, including lectures already conducted. These totals, your timetable and confirmed holidays determine the skip calendar. Each timetable session counts as one lecture.</p>
          {subjects.map((subject) => <div className="list-row" key={subject.id}>
            <div><b>{subject.name}</b><small>{subject.code} · {subject.planned_lectures == null ? "Semester total needed for skip dates" : `${subject.planned_lectures} semester lectures`}</small></div>
            <button onClick={() => open("subject", subject)}>Set lecture total</button>
          </div>)}
        </Card>
      )}
      {tab === "subjects" && (
        <Card
          title="Subjects"
          action={
            <button className="primary" onClick={() => open("subject")}>
              <Plus size={16} /> Subject
            </button>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Course code</th>
                  <th>Name</th>
                  <th>Instructor</th>
                  <th>Type</th>
                  <th>Semester lectures</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {subjects
                  .filter((s) => matches(s.name + " " + s.code, search))
                  .map((s) => (
                    <tr key={s.id}>
                      <td>{s.code}</td>
                      <td>{s.name}</td>
                      <td>{s.instructor || "—"}</td>
                      <td>{s.kind}</td>
                      <td>{s.planned_lectures ?? "Enter total"}</td>
                      <td>
                        <button
                          className="icon-button"
                          aria-label={`Edit ${s.name}`}
                          onClick={() => open("subject", s)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-button danger"
                          aria-label={`Delete ${s.name}`}
                          onClick={() => {
                            if (
                              confirm(
                                `Delete ${s.name} and all of its attendance and schedule records?`,
                              )
                            )
                              run(() =>
                                api("/subjects/" + s.id, { method: "DELETE" }),
                              );
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          {!subjects.length && (
            <Empty>Add subjects manually or through reviewed imports.</Empty>
          )}
        </Card>
      )}
      {tab === "reconciliation" && (
        <Card title="University vs Local Attendance">
          <p>
            Comparisons use matching through-dates. Reviewing a discrepancy
            records your decision and keeps local attendance intact.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Subject / date</th>
                  <th>University</th>
                  <th>Local</th>
                  <th>Difference</th>
                  <th>Status</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {reconciliation.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.subject}
                      <small>{r.through_date}</small>
                    </td>
                    <td>
                      {r.attended}/{r.conducted}
                      <small>{pct(r.official_percentage)}</small>
                    </td>
                    <td>
                      {r.local_attended ?? "—"}/{r.local_conducted ?? "—"}
                      <small>{pct(r.local_percentage)}</small>
                    </td>
                    <td>
                      {r.difference_pp == null ? "—" : `${r.difference_pp} pp`}
                    </td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                    <td>
                      {r.resolution === "review" ? (
                        <button
                          onClick={() => {
                            const note = prompt(
                              "Review note (local attendance will be retained):",
                              "",
                            );
                            if (note !== null)
                              run(
                                () =>
                                  send(
                                    "/reconciliation/" + r.id,
                                    { resolution: "keep_local", note },
                                    "PATCH",
                                  ),
                                "Review recorded",
                              );
                          }}
                        >
                          Keep local / note
                        </button>
                      ) : (
                        <>
                          <Badge value={r.resolution} />
                          <small>{r.note}</small>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!reconciliation.length && (
            <Empty>
              Import attendance and choose “Reconciliation snapshot” at review
              to compare university counts with your records.
            </Empty>
          )}
        </Card>
      )}
      {tab === "datasets" && (
        <Card title="Semester Dataset">
          <div className="metric-list">
            <div>
              <span>Semester</span>
              <b>{semester?.name}</b>
            </div>
            <div>
              <span>Dates</span>
              <b>
                {semester?.start_date} – {semester?.end_date}
              </b>
            </div>
            <div>
              <span>Subjects</span>
              <b>{subjects.length}</b>
            </div>
            <div>
              <span>Student</span>
              <b>{profile?.student_id || "Not set"}</b>
            </div>
          </div>
          <div className="toolbar">
            <button
              onClick={() =>
                run(
                  () =>
                    download(
                      `/export?semester_id=${semester!.id}`,
                      "AttendTrend-data.json",
                    ),
                  "Dataset exported",
                )
              }
            >
              <Download size={16} /> Export full dataset
            </button>
            <button
              onClick={() =>
                run(
                  () =>
                    download(
                      `/export?semester_id=${semester!.id}&format=csv`,
                      "AttendTrend-attendance.csv",
                    ),
                  "Attendance CSV exported",
                )
              }
            >
              Export attendance CSV
            </button>
            <button onClick={() => open("semester", semester)}>
              Edit semester
            </button>
            <button
              className="danger"
              onClick={() => {
                if (
                  confirm(
                    `Delete semester “${semester?.name}” and all academic data in it?`,
                  )
                )
                  run(
                    () =>
                      api("/semesters/" + semester!.id, { method: "DELETE" }),
                    "Semester deleted",
                  );
              }}
            >
              Delete semester
            </button>
          </div>
        </Card>
      )}
      <Card title="Imported Baseline Counts">
        {baselineQuery.error && (
          <ErrorBox
            error={baselineQuery.error}
            retry={() => baselineQuery.refetch()}
          />
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Subject</th>
                <th>Through date</th>
                <th>Present / conducted</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {baselineQuery.data?.map((b) => (
                <tr key={b.id}>
                  <td>{b.name}</td>
                  <td>{b.through_date}</td>
                  <td>
                    {b.attended} / {b.conducted}
                  </td>
                  <td>
                    <button onClick={() => setBaseline(b)}>
                      Correct imported counts
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!baselineQuery.data?.length && (
          <Empty>No aggregate attendance baselines in this semester.</Empty>
        )}
      </Card>
      {baseline && (
        <BaselineCorrection
          baseline={baseline}
          close={() => setBaseline(null)}
        />
      )}{" "}
      {review && (
        <ImportReview document={review} close={() => setReview(null)} />
      )}
    </>
  );
}

const importColumns: Record<string, string[]> = {
  attendance: ["code", "name", "kind", "instructor", "attended", "conducted", "through_date"],
  timetable: ["code", "name", "weekday", "start_time", "end_time", "room"],
  calendar: ["title", "start_date", "end_date", "kind"],
};
function BaselineCorrection({
  baseline: b,
  close,
}: {
  baseline: any;
  close: () => void;
}) {
  const { action, busy } = useApp();
  const [error, setError] = useState<any>(null);
  return (
    <Modal title="Correct imported baseline counts" close={close}>
      <p>
        {b.name} · {b.code}. Save an explicit correction to the aggregate
        counts. The original import is retained in the audit history.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget));
          try {
            await action(
              () =>
                send(
                  "/baselines/" + b.id,
                  {
                    code: b.code,
                    name: b.name,
                    attended: Number(f.attended),
                    conducted: Number(f.conducted),
                    through_date: f.through_date,
                  },
                  "PUT",
                ),
              "Baseline correction saved",
            );
            close();
          } catch (err) {
            setError(err);
          }
        }}
      >
        <div className="form-row">
          <label>
            Present classes
            <input
              required
              name="attended"
              type="number"
              min={0}
              defaultValue={b.attended}
            />
          </label>
          <label>
            Conducted classes
            <input
              required
              name="conducted"
              type="number"
              min={0}
              defaultValue={b.conducted}
            />
          </label>
        </div>
        <label>
          Counts through date
          <input
            required
            name="through_date"
            type="date"
            defaultValue={b.through_date}
          />
        </label>
        {error && <ErrorBox error={error} />}
        <Submit busy={busy} label="Save reviewed correction" />
      </form>
    </Modal>
  );
}
export function ImportReview({
  document: d,
  close,
}: {
  document: any;
  close: () => void;
}) {
  const { action, busy, semester, subjects } = useApp();
  const allRows = d.preview.rows || [];
  const initialRows = d.kind === "calendar" && semester && d.status !== "confirmed"
    ? allRows.filter((r: any) => r.start_date <= semester.end_date && r.end_date >= semester.start_date).map((r: any) => ({...r, start_date: r.start_date < semester.start_date ? semester.start_date : r.start_date, end_date: r.end_date > semester.end_date ? semester.end_date : r.end_date}))
    : allRows;
  const [rows, setRows] = useState<any[]>(initialRows),
    [mode, setMode] = useState("baseline"),
    [error, setError] = useState<any>(null);
  const readonly = d.status === "confirmed",
    columns = importColumns[d.kind];
  const update = (index: number, key: string, value: string) =>
    setRows(
      rows.map((r, i) =>
        i === index
          ? {
              ...r,
              [key]: ["attended", "conducted", "weekday"].includes(key)
                ? Number(value)
                : value,
            }
          : r,
      ),
    );
  const add = () =>
    setRows([
      ...rows,
      Object.fromEntries(
        columns.map((k) => [
          k,
          ["attended", "conducted", "weekday"].includes(k)
            ? 0
            : k === "kind"
              ? (d.kind === "attendance" ? "theory" : "holiday")
              : k.endsWith("date")
                ? semester?.start_date || ""
                : "",
        ]),
      ),
    ]);
  return (
    <Modal
      title={readonly ? "Confirmed import" : "Review extracted data"}
      close={close}
    >
      <p>
        Check every field against the source. Only corrected, confirmed rows
        will be saved.
      </p>
      {d.kind === "calendar" && !readonly && semester && <div className="info">Showing {initialRows.length} of {allRows.length} calendar activities that overlap {semester.name}. Dates are clipped to the selected semester. Check your teaching end date before confirming.</div>}
      {d.kind === "timetable" && !readonly && <div className="info">Choose the existing attendance subject for each slot, including theory/practical type. Review times carefully. Each row is one counted lecture, even when it lasts two hours.</div>}
      {d.preview.warnings?.map((w: string, i: number) => (
        <div className="info" key={i}>
          {w}
        </div>
      ))}
      {d.kind === "attendance" && !readonly && (
        <label>
          Use these counts as
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="baseline">
              Initial attendance baseline · only if no covered local records
              exist
            </option>
            <option value="reconciliation">
              Reconciliation snapshot · compare without changing local records
            </option>
          </select>
        </label>
      )}
      <div className="table-wrap">
        <table className="review-table">
          <thead>
            <tr>
              {columns.map((k) => (
                <th key={k}>{k.replaceAll("_", " ")}</th>
              ))}
              {!readonly && <th>Remove</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((k) => (
                  <td key={k}>
                    {k === "code" && d.kind === "timetable" && subjects.length ? (
                      <select disabled={readonly} aria-label={`Subject row ${i + 1}`} value={r.code} onChange={(e) => {const subject = subjects.find((s) => s.code === e.target.value); setRows(rows.map((row, n) => n === i ? {...row, code: e.target.value, name: subject?.name || row.name} : row));}}>
                        <option value={r.code}>{r.code || "Choose subject"} · {r.name}</option>
                        {subjects.filter((s) => s.code !== r.code).map((s) => <option key={s.id} value={s.code}>{s.code} · {s.name} ({s.kind})</option>)}
                      </select>
                    ) : k === "weekday" ? (
                      <select
                        disabled={readonly}
                        aria-label={`${k} row ${i + 1}`}
                        value={r[k]}
                        onChange={(e) => update(i, k, e.target.value)}
                      >
                        {weekdays.map((d, i) => (
                          <option key={d} value={i}>
                            {d}
                          </option>
                        ))}
                      </select>
                    ) : k === "kind" ? (
                      <select
                        disabled={readonly}
                        value={r[k] || (d.kind === "attendance" ? "theory" : "holiday")}
                        onChange={(e) => update(i, k, e.target.value)}
                      >
                        {(d.kind === "attendance" ? ["theory", "practical"] : ["holiday", "event", "exam"]).map((t) => (
                          <option key={t}>{t}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        aria-label={`${k} row ${i + 1}`}
                        disabled={readonly}
                        type={
                          k.endsWith("date")
                            ? "date"
                            : k.endsWith("time")
                              ? "time"
                              : ["attended", "conducted"].includes(k)
                                ? "number"
                                : "text"
                        }
                        min={0}
                        value={r[k] ?? ""}
                        onChange={(e) => update(i, k, e.target.value)}
                      />
                    )}
                  </td>
                ))}
                {!readonly && (
                  <td>
                    <button
                      className="icon-button danger"
                      aria-label={`Remove row ${i + 1}`}
                      onClick={() => setRows(rows.filter((_, j) => i !== j))}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!readonly && <button onClick={add}>+ Add row</button>}
      <details>
        <summary>Extracted source text</summary>
        <pre className="extracted-text">
          {d.preview.text || "No text extracted."}
        </pre>
      </details>
      {error && <ErrorBox error={error} />}{" "}
      {!readonly && (
        <button
          className="primary"
          disabled={!rows.length || busy}
          onClick={async () => {
            setError(null);
            try {
              await action(
                () => send(`/documents/${d.id}/confirm`, { rows, mode }),
                "Reviewed rows saved",
              );
              close();
            } catch (err) {
              setError(err);
            }
          }}
        >
          <Check size={16} /> Confirm {rows.length} reviewed rows
        </button>
      )}
    </Modal>
  );
}

export function NotificationsPage() {
  const { notifications, busy } = useApp();
  const run = useSafeAction();
  const [filter, setFilter] = useState("all");
  const rows = notifications.filter(
    (n) =>
      filter === "all" || (filter === "unread" && !n.read) || n.kind === filter,
  );
  return (
    <Card
      title="Notifications"
      action={
        <div className="toolbar">
          <select
            aria-label="Notification filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {["all", "unread", "risk", "recovery", "upcoming", "import"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
          <button
            disabled={busy || !notifications.some((n) => !n.read)}
            onClick={() =>
              run(
                () => send("/notifications/read-all", {}),
                "All notifications marked read",
              )
            }
          >
            Mark all read
          </button>
        </div>
      }
    >
      {rows.map((n) => (
        <div
          className={"notification-row " + (!n.read ? "unread" : "")}
          key={n.id}
        >
          <div>
            <Badge value={n.kind} />
            <p>{n.message}</p>
            <small>{new Date(n.created_at + "Z").toLocaleString()}</small>
          </div>
          {!n.read && (
            <button
              aria-label={`Read notification ${n.id}`}
              onClick={() =>
                run(
                  () => api("/notifications/" + n.id, { method: "PATCH" }),
                  "Notification marked read",
                )
              }
            >
              Mark read
            </button>
          )}
        </div>
      ))}
      {!rows.length && (
        <Empty>
          <b>All caught up</b>
          <p>
            No matching notifications. Alerts will appear when your data or
            schedule generates them.
          </p>
        </Empty>
      )}
    </Card>
  );
}

export function ProfilePage({ updateUser }: { updateUser: (u: User) => void }) {
  const { profile, user, action, busy } = useApp();
  const [passwordError, setPasswordError] = useState<any>(null);
  if (!profile)
    return (
      <Card>
        <Empty>Loading profile…</Empty>
      </Card>
    );
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    const body = {
      ...data,
      target: Number(data.target),
      safety_buffer: Number(data.safety_buffer),
      notify_risk: data.notify_risk === "on",
      notify_upcoming: data.notify_upcoming === "on",
      notify_imports: data.notify_imports === "on",
    };
    try {
      const r = await action(
        () => send("/profile", body, "PUT"),
        "Profile saved",
      );
      updateUser({ ...user, name: r.name });
    } catch {}
  }
  async function password(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      const u = await action(
        () => send("/auth/password", Object.fromEntries(new FormData(form))),
        "Password changed; other sessions signed out",
      );
      setCsrf(u.csrf);
      updateUser(u);
      form.reset();
      setPasswordError(null);
    } catch (err) {
      setPasswordError(err);
    }
  }
  return (
    <div className="profile-layout">
      <Card title="Student profile & preferences">
        <form onSubmit={save} key={profile.updated_at || profile.user_id}>
          <label>
            Name
            <input
              name="name"
              required
              defaultValue={profile.name}
              maxLength={100}
            />
          </label>
          <label>
            Email
            <input type="email" value={profile.email} readOnly />
          </label>
          <label>
            Student ID
            <input
              name="student_id"
              defaultValue={profile.student_id}
              maxLength={100}
            />
          </label>
          <label>
            Institution
            <input
              name="institution"
              defaultValue={profile.institution}
              maxLength={200}
            />
          </label>
          <label>
            Section
            <input
              name="section"
              defaultValue={profile.section}
              maxLength={40}
            />
          </label>
          <label>
            Timezone
            <input name="timezone" required defaultValue={profile.timezone} />
            <small>
              IANA name, such as Asia/Kolkata. Fixed after classes are created.
            </small>
          </label>
          <label>
            Attendance target (%)
            <input
              name="target"
              type="number"
              min={0.01}
              max={100}
              step={0.01}
              required
              defaultValue={profile.target}
            />
          </label>
          <label>
            Safety buffer (pp)
            <input
              name="safety_buffer"
              type="number"
              min={0}
              max={25}
              step={0.1}
              required
              defaultValue={profile.safety_buffer}
            />
          </label>
          <label>
            Risk sensitivity
            <select
              name="risk_sensitivity"
              defaultValue={profile.risk_sensitivity}
            >
              <option value="cautious">
                Cautious · include safety buffer in risk threshold
              </option>
              <option value="balanced">Balanced</option>
              <option value="relaxed">
                Relaxed · lower forecast warning threshold by safety buffer
              </option>
            </select>
          </label>
          <label className="check">
            <input
              name="notify_risk"
              type="checkbox"
              defaultChecked={profile.notify_risk}
            />{" "}
            Risk and recovery alerts
          </label>
          <label className="check">
            <input
              name="notify_upcoming"
              type="checkbox"
              defaultChecked={profile.notify_upcoming}
            />{" "}
            Upcoming class reminders
          </label>
          <label className="check">
            <input
              name="notify_imports"
              type="checkbox"
              defaultChecked={profile.notify_imports}
            />{" "}
            Import and data update notifications
          </label>
          <label>
            Theme
            <select name="theme" defaultValue={profile.theme}>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="system">System</option>
            </select>
          </label>
          <Submit busy={busy} label="Save settings" />
        </form>
      </Card>
      <Card title="Account security">
        <form onSubmit={password}>
          <label>
            Current password
            <input
              name="current_password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            New password
            <input
              name="new_password"
              type="password"
              minLength={10}
              maxLength={128}
              required
              autoComplete="new-password"
            />
          </label>
          {passwordError && <ErrorBox error={passwordError} />}
          <Submit busy={busy} label="Change password" />
        </form>
      </Card>
    </div>
  );
}
