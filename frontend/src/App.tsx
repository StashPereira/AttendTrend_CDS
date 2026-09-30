import {
  useEffect,
  useState,
  FormEvent,
  createContext,
  useContext,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  ClipboardCheck,
  CalendarDays,
  ChartColumn,
  FlaskConical,
  BrainCircuit,
  Database,
  Bell,
  Search,
  ChevronDown,
  Plus,
  Menu,
  LogOut,
  Settings,
} from "lucide-react";
import { api, send, setCsrf, download } from "./api";
import {
  User,
  Semester,
  Subject,
  Summary,
  ClassRow,
  todayInZone,
} from "./types";
import { Card, Empty, ErrorBox, Modal, Submit } from "./components";
import {
  Dashboard,
  AttendancePage,
  CalendarPage,
  AnalyticsPage,
  PlanningPage,
  PredictionsPage,
  DataPage,
  NotificationsPage,
  ProfilePage,
} from "./pages";

const pages = [
  ["dashboard", "Dashboard", LayoutDashboard],
  ["attendance", "Attendance", ClipboardCheck],
  ["calendar", "Calendar & Timetable", CalendarDays],
  ["analytics", "Insights & Analytics", ChartColumn],
  ["planning", "Planning & Recovery", FlaskConical],
  ["predictions", "Predictions", BrainCircuit],
  ["data", "Data & Reconciliation", Database],
  ["notifications", "Notifications", Bell],
] as const;
type ContextValue = {
  user: User;
  semester: Semester | null;
  summary: Summary | undefined;
  subjects: Subject[];
  classes: ClassRow[];
  timetable: any[];
  events: any[];
  documents: any[];
  reconciliation: any[];
  notifications: any[];
  profile: any;
  search: string;
  action: (work: () => Promise<any>, message?: string) => Promise<any>;
  go: (page: string) => void;
  open: (kind: string, item?: any) => void;
  busy: boolean;
};
export const AppContext = createContext<ContextValue>(null!);
export const useApp = () => useContext(AppContext);

function Auth({ login }: { login: (u: User) => void }) {
  const [mode, setMode] = useState("login"),
    [error, setError] = useState<any>(null),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      const u = await send("/auth/" + mode, {
        email: f.get("email"),
        password: f.get("password"),
        ...(mode === "signup" ? { name: f.get("name") } : {}),
      });
      setCsrf(u.csrf);
      login(u);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-screen">
      <Card className="auth-card">
        <div className="brand">
          <span className="logo">A</span>
          <div>
            <b>AttendTrend</b>
            <small>Attendance intelligence</small>
          </div>
        </div>
        <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p>Your attendance, your plan, your progress.</p>
        <form onSubmit={submit}>
          {mode === "signup" && (
            <label>
              Name
              <input required name="name" maxLength={100} autoComplete="name" />
            </label>
          )}
          <label>
            Email
            <input required type="email" name="email" autoComplete="email" />
          </label>
          <label>
            Password
            <input
              required
              type="password"
              name="password"
              minLength={10}
              maxLength={128}
              autoComplete={
                mode === "signup" ? "new-password" : "current-password"
              }
            />
            <small>At least 10 characters</small>
          </label>
          {error && <ErrorBox error={error} />}
          <Submit
            busy={busy}
            label={mode === "login" ? "Sign in" : "Create account"}
          />
        </form>
        <button
          className="link"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError(null);
          }}
        >
          {mode === "login"
            ? "New here? Create an account"
            : "Already registered? Sign in"}
        </button>
      </Card>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined),
    [startupError, setStartupError] = useState<any>(null);
  const client = useQueryClient();
  const check = () => {
    setStartupError(null);
    api<User>("/auth/me")
      .then((u) => {
        setCsrf(u.csrf);
        setUser(u);
      })
      .catch((err) => {
        if (err.status === 401) setUser(null);
        else setStartupError(err);
      });
  };
  useEffect(() => {
    check();
    const expired = () => {
      setUser(null);
      setCsrf("");
      client.clear();
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  if (user === undefined)
    return (
      <div className="auth-screen">
        {startupError ? (
          <ErrorBox error={startupError} retry={check} />
        ) : (
          <p>Loading AttendTrend…</p>
        )}
      </div>
    );
  if (!user) return <Auth login={setUser} />;
  return (
    <Workspace
      user={user}
      updateUser={setUser}
      logout={() => {
        setCsrf("");
        client.clear();
        setUser(null);
      }}
    />
  );
}

function Workspace({
  user,
  updateUser,
  logout,
}: {
  user: User;
  updateUser: (u: User) => void;
  logout: () => void;
}) {
  const client = useQueryClient();
  const [page, setPage] = useState(location.hash.slice(1) || "dashboard"),
    [semesterId, setSemesterId] = useState<number | null>(null),
    [search, setSearch] = useState(""),
    [menu, setMenu] = useState(false),
    [modal, setModal] = useState<{ kind: string; item?: any } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<any>(null),
    [notice, setNotice] = useState("");
  const semesters = useQuery({
    queryKey: ["semesters"],
    queryFn: () => api<Semester[]>("/semesters"),
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api("/profile"),
  });
  const semester =
    semesters.data?.find((s) => s.id === semesterId) ||
    semesters.data?.[0] ||
    null;
  const id = semester?.id;
  function query<T>(key: string, path: string) {
    return useQuery<T>({
      queryKey: [key, id],
      queryFn: () => api<T>(path),
      enabled: !!id,
      refetchInterval: key === "documents" ? 5000 : 30000,
    });
  }
  const summary = query<Summary>("summary", `/summary?semester_id=${id}`),
    subjects = query<Subject[]>("subjects", `/subjects?semester_id=${id}`),
    classes = query<ClassRow[]>("classes", `/classes?semester_id=${id}`),
    timetable = query<any[]>("timetable", `/timetable?semester_id=${id}`),
    events = query<any[]>("events", `/events?semester_id=${id}`),
    documents = query<any[]>("documents", `/documents?semester_id=${id}`),
    reconciliation = query<any[]>(
      "reconciliation",
      `/reconciliation?semester_id=${id}`,
    ),
    notifications = query<any[]>(
      "notifications",
      `/notifications?semester_id=${id}`,
    );
  const go = (p: string) => {
    location.hash = p;
    setPage(p);
    setMenu(false);
    setSearch("");
  };
  useEffect(() => {
    const handler = () => setPage(location.hash.slice(1) || "dashboard");
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  useEffect(() => {
    const mode = profile.data?.theme || "light";
    const dark =
      mode === "dark" ||
      (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [profile.data?.theme]);
  async function action(work: () => Promise<any>, message = "Changes saved") {
    setBusy(true);
    setError(null);
    try {
      const result = await work();
      await client.invalidateQueries();
      setNotice(message);
      setTimeout(() => setNotice(""), 4000);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setBusy(false);
    }
  }
  const context: ContextValue = {
    user,
    semester,
    summary: summary.data,
    subjects: subjects.data || [],
    classes: classes.data || [],
    timetable: timetable.data || [],
    events: events.data || [],
    documents: documents.data || [],
    reconciliation: reconciliation.data || [],
    notifications: notifications.data || [],
    profile: profile.data,
    search,
    action,
    go,
    open: (kind, item) => setModal({ kind, item }),
    busy,
  };
  const dataError = [
    semesters,
    profile,
    summary,
    subjects,
    classes,
    timetable,
    events,
    documents,
    reconciliation,
    notifications,
  ].find((q) => q.error)?.error;
  const currentTitle =
    pages.find((p) => p[0] === page)?.[1] || "Profile & Settings";
  const content = () => {
    if (page === "profile") return <ProfilePage updateUser={updateUser} />;
    if (page === "notifications") return <NotificationsPage />;
    if (!semester)
      return (
        <Card title="Welcome to AttendTrend">
          <Empty>
            Set up your academic term to begin. Your account starts with no
            sample data.
          </Empty>
          <div className="setup-steps">
            <span>1 · Profile</span>
            <span>2 · Create semester</span>
            <span>3 · Import attendance</span>
            <span>4 · Calendar & timetable</span>
            <span>5 · Review & confirm</span>
          </div>
          <button
            className="primary"
            onClick={() => setModal({ kind: "semester" })}
          >
            Create semester
          </button>{" "}
          <button onClick={() => go("profile")}>Complete profile</button>
        </Card>
      );
    if (summary.isPending || classes.isPending || subjects.isPending)
      return (
        <Card>
          <Empty>Loading academic data…</Empty>
        </Card>
      );
    switch (page) {
      case "attendance":
        return <AttendancePage />;
      case "calendar":
        return <CalendarPage />;
      case "analytics":
        return <AnalyticsPage />;
      case "planning":
        return <PlanningPage />;
      case "predictions":
        return <PredictionsPage />;
      case "data":
        return <DataPage />;
      default:
        return <Dashboard />;
    }
  };
  return (
    <AppContext.Provider value={context}>
      <div className="workspace">
        <aside className={menu ? "sidebar visible" : "sidebar"}>
          <div className="brand">
            <span className="logo">A</span>
            <div>
              <b>AttendTrend</b>
              <small>Attendance intelligence</small>
            </div>
          </div>
          <div className="workspace-label">WORKSPACE</div>
          <nav>
            {pages.map(([key, label, Icon]) => (
              <button
                key={key}
                className={page === key ? "nav active" : "nav"}
                onClick={() => go(key)}
              >
                <Icon size={21} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
          <button className="user-card" onClick={() => go("profile")}>
            <span className="avatar">
              {user.name.slice(0, 2).toUpperCase()}
            </span>
            <span>
              <b>{user.name}</b>
              <small>Student</small>
            </span>
          </button>
        </aside>
        <div className="main">
          <header className="topbar">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenu(!menu)}
            >
              <Menu />
            </button>
            <div className="search">
              <Search size={20} />
              <input
                aria-label="Search subjects or classes"
                placeholder="Search subjects or classes…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="top-actions">
              <button
                className="icon-button"
                aria-label="Notifications"
                onClick={() => go("notifications")}
              >
                <Bell size={21} />
                {notifications.data?.some((n) => !n.read) && (
                  <span className="notification-dot" />
                )}
              </button>
              <button
                className="avatar"
                aria-label="Profile"
                onClick={() => go("profile")}
              >
                {user.name[0].toUpperCase()}
              </button>
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={() =>
                  action(() => send("/auth/logout", {}), "Signed out")
                    .then(logout)
                    .catch(() => {})
                }
              >
                <LogOut size={18} />
              </button>
            </div>
          </header>
          <main className="content">
            <div className="page-heading">
              <div>
                <h1>
                  {page === "dashboard"
                    ? `Good ${new Date().getHours() < 12 ? "morning" : "day"}, ${user.name.split(" ")[0]}!`
                    : currentTitle}
                </h1>
                <p>
                  {page === "dashboard"
                    ? "Here’s your attendance overview for this term."
                    : "Keep your academic data accurate and your attendance on track."}
                </p>
              </div>
              <div className="heading-actions">
                <select
                  aria-label="Select semester"
                  value={id || ""}
                  onChange={(e) => setSemesterId(Number(e.target.value))}
                >
                  {!id && <option value="">No semester</option>}
                  {semesters.data?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button
                  className="icon-button"
                  title="New semester"
                  aria-label="New semester"
                  onClick={() => setModal({ kind: "semester" })}
                >
                  <Plus size={20} />
                </button>
                {page === "dashboard" && (
                  <>
                    <button onClick={() => go("calendar")}>
                      <CalendarDays size={17} /> Calendar
                    </button>
                    <button
                      className="primary"
                      onClick={() => go("attendance")}
                    >
                      <Plus size={17} /> Mark attendance
                    </button>
                  </>
                )}
                {page === "calendar" && (
                  <button
                    className="primary"
                    onClick={() => setModal({ kind: "event" })}
                  >
                    <Plus size={17} /> Event
                  </button>
                )}
                {page === "data" && id && (
                  <button
                    onClick={() =>
                      action(
                        () =>
                          download(
                            `/export?semester_id=${id}`,
                            "AttendTrend-data.json",
                          ),
                        "Export downloaded",
                      ).catch(() => {})
                    }
                  >
                    Export data
                  </button>
                )}
              </div>
            </div>
            {notice && (
              <div role="status" className="success">
                {notice}
              </div>
            )}
            {error && <ErrorBox error={error} />}{" "}
            {dataError && (
              <ErrorBox
                error={dataError}
                retry={() => client.invalidateQueries()}
              />
            )}{" "}
            {content()}
            <footer>
              Present ÷ conducted · Excused, cancelled, pending and future
              classes are excluded.
            </footer>
          </main>
        </div>
      </div>
      {modal && (
        <RecordModal
          kind={modal.kind}
          item={modal.item}
          close={() => setModal(null)}
        />
      )}
    </AppContext.Provider>
  );
}

export function RecordModal({
  kind,
  item,
  close,
}: {
  kind: string;
  item?: any;
  close: () => void;
}) {
  const { semester, subjects, action, busy } = useApp();
  const [error, setError] = useState<any>(null);
  const title =
    kind === "semester"
      ? item
        ? "Edit semester"
        : "Create semester"
      : kind === "subject"
        ? item
          ? "Edit subject"
          : "Add subject"
        : kind === "timetable"
          ? item
            ? "Edit timetable slot"
            : "Add timetable slot"
          : kind === "class"
            ? item
              ? "Edit / reschedule class"
              : "Add additional class"
            : "Add calendar event";
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const f = Object.fromEntries(new FormData(e.currentTarget));
    let body: any,
      path = "",
      method = "POST";
    if (kind === "semester") {
      body = f;
      path = "/semesters" + (item ? "/" + item.id : "");
      method = item ? "PUT" : "POST";
    }
    if (kind === "subject") {
      body = { ...f, semester_id: semester!.id, planned_lectures: f.planned_lectures === "" ? null : Number(f.planned_lectures) };
      path = "/subjects" + (item ? "/" + item.id : "");
      method = item ? "PUT" : "POST";
    }
    if (kind === "timetable") {
      body = {
        ...f,
        subject_id: Number(f.subject_id),
        weekday: Number(f.weekday),
      };
      path = "/timetable" + (item ? "/" + item.id : "");
      method = item ? "PUT" : "POST";
    }
    if (kind === "event") {
      body = { ...f, semester_id: semester!.id };
      path = "/events" + (item ? "/" + item.id : "");
      method = item ? "PUT" : "POST";
    }
    if (kind === "class") {
      body = {
        ...f,
        subject_id: Number(f.subject_id),
        cancelled: f.cancelled === "on",
      };
      path = "/classes" + (item ? "/" + item.id : "");
      method = item ? "PUT" : "POST";
    }
    try {
      await action(() => send(path, body, method));
      close();
    } catch (err) {
      setError(err);
    }
  }
  return (
    <Modal title={title} close={close}>
      <form onSubmit={submit}>
        {(kind === "semester" || kind === "subject") && (
          <label>
            Name
            <input
              required
              name="name"
              defaultValue={item?.name}
              maxLength={kind === "subject" ? 150 : 100}
            />
          </label>
        )}
        {kind === "subject" && (
          <>
            <label>
              Course code
              <input
                required
                name="code"
                defaultValue={item?.code}
                maxLength={40}
              />
            </label>
            <label>
              Instructor
              <input
                name="instructor"
                defaultValue={item?.instructor || ""}
                maxLength={100}
              />
            </label>
            <label>
              How many lectures are planned for this subject this semester?
              <input name="planned_lectures" type="number" min={0} max={10000} defaultValue={item?.planned_lectures ?? ""} />
              <small>Enter the full semester total, including lectures already conducted. Count each timetable session as one lecture; enter practical subjects separately. Leave blank if unknown.</small>
            </label>
            <label>
              Type
              <select name="kind" defaultValue={item?.kind || "theory"}>
                <option value="theory">Theory</option>
                <option value="practical">Practical</option>
              </select>
            </label>
          </>
        )}
        {(kind === "semester" || kind === "event") && (
          <>
            <div className="form-row">
              <label>
                Start date
                <input
                  required
                  type="date"
                  name="start_date"
                  defaultValue={item?.start_date || semester?.start_date}
                />
              </label>
              <label>
                End date
                <input
                  required
                  type="date"
                  name="end_date"
                  defaultValue={item?.end_date || semester?.end_date}
                />
              </label>
            </div>
          </>
        )}
        {(kind === "timetable" || kind === "class") && (
          <label>
            Subject
            <select
              name="subject_id"
              required
              defaultValue={item?.subject_id || subjects[0]?.id}
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {kind === "timetable" && (
          <>
            <label>
              Weekday
              <select name="weekday" defaultValue={item?.weekday || 0}>
                {[
                  "Monday",
                  "Tuesday",
                  "Wednesday",
                  "Thursday",
                  "Friday",
                  "Saturday",
                  "Sunday",
                ].map((d, i) => (
                  <option key={d} value={i}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <div className="form-row">
              <label>
                Start time
                <input
                  name="start_time"
                  type="time"
                  defaultValue={item?.start_time?.slice(0, 5)}
                  required
                />
              </label>
              <label>
                End time
                <input
                  name="end_time"
                  type="time"
                  defaultValue={item?.end_time?.slice(0, 5)}
                  required
                />
              </label>
            </div>
            <label>
              Room
              <input
                name="room"
                defaultValue={item?.room || ""}
                maxLength={100}
              />
            </label>
          </>
        )}
        {kind === "class" && (
          <>
            <div className="form-row">
              <label>
                Starts at
                <input
                  type="datetime-local"
                  name="starts_at"
                  defaultValue={item?.starts_at?.slice(0, 16)}
                  required
                />
              </label>
              <label>
                Ends at
                <input
                  type="datetime-local"
                  name="ends_at"
                  defaultValue={item?.ends_at?.slice(0, 16)}
                  required
                />
              </label>
            </div>
            <label>
              Room
              <input
                name="room"
                defaultValue={item?.room || ""}
                maxLength={100}
              />
            </label>
            <label className="check">
              <input
                name="cancelled"
                type="checkbox"
                defaultChecked={item?.cancelled}
              />{" "}
              Cancelled
            </label>
          </>
        )}
        {kind === "event" && (
          <>
            <label>
              Title
              <input
                name="title"
                defaultValue={item?.title || ""}
                required
                maxLength={150}
              />
            </label>
            <label>
              How many lectures are planned for this subject this semester?
              <input name="planned_lectures" type="number" min={0} max={10000} defaultValue={item?.planned_lectures ?? ""} />
              <small>Enter the full semester total, including lectures already conducted. Count each timetable session as one lecture; enter practical subjects separately. Leave blank if unknown.</small>
            </label>
            <label>
              Type
              <select name="kind" defaultValue={item?.kind || "holiday"}>
                <option value="holiday">
                  Holiday · cancel scheduled classes
                </option>
                <option value="exam">Exam</option>
                <option value="event">Event</option>
              </select>
            </label>
          </>
        )}
        {error && <ErrorBox error={error} />}
        <Submit busy={busy} label={item ? "Save changes" : "Create"} />
      </form>
    </Modal>
  );
}
