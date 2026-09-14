import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Job, Preparation, Stats } from "./types";
import "./style.css";

const statuses = [
  "new",
  "reviewed",
  "saved",
  "dismissed",
  "preparing",
  "ready_to_apply",
  "applied",
  "oa",
  "recruiter",
  "interview",
  "rejected",
  "offer",
];
const post = ["applied", "oa", "recruiter", "interview", "rejected", "offer"];
const label = (s: string) => s.replaceAll("_", " ");
const date = (s: string | null) =>
  s
    ? new Date(s).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
    : "Unknown";

function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("scout-token") || "",
  );
  const [needToken, setNeedToken] = useState(false);
  const [view, setView] = useState("ranked");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<Job | null>(null);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    statuses: {},
    feedback_count: 0,
    runs: [],
  });
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [decision, setDecision] = useState("");
  const [mode, setMode] = useState("");
  const [demo, setDemo] = useState("");
  const [location, setLocation] = useState("");
  const [family, setFamily] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [prefs, setPrefs] = useState("");
  const [profile, setProfile] = useState("");
  const [note, setNote] = useState("");
  const [nextStatus, setNextStatus] = useState("applied");
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(100);
  const refreshSequence = useRef(0);
  async function api<T>(
    path: string,
    method = "GET",
    body?: unknown,
  ): Promise<T> {
    const r = await fetch("/api" + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (r.status === 401) {
      setNeedToken(true);
      throw new Error("Enter your API token to unlock this workspace.");
    }
    if (!r.ok) {
      const data = await r.json();
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
      );
    }
    setNeedToken(false);
    return r.json();
  }
  async function refresh() {
    const sequence = ++refreshSequence.current;
    const params = new URLSearchParams({
      q,
      status,
      decision,
      work_mode: mode,
      view,
      location,
      family,
      source,
      limit: String(limit),
    });
    if (demo) params.set("demo", demo);
    const [r, s] = await Promise.all([
      api<{ jobs: Job[]; total: number }>("/jobs?" + params),
      api<Stats>("/stats"),
    ]);
    if (sequence !== refreshSequence.current) return;
    setJobs(r.jobs);
    setTotal(r.total);
    setStats(s);
  }
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      if (active) refresh().catch((e) => setError(String(e.message)));
    }, 180);
    return () => {
      active = false;
      refreshSequence.current++;
      clearTimeout(timer);
    };
  }, [
    view,
    q,
    status,
    decision,
    mode,
    demo,
    location,
    family,
    source,
    limit,
    token,
  ]);
  useEffect(() => {
    if (!selected) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trap = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelected(null);
      if (event.key !== "Tab") return;
      const nodes = Array.from(
        document.querySelectorAll<HTMLElement>(
          ".detail button:not(:disabled), .detail a, .detail input, .detail select, .detail textarea, .detail summary",
        ),
      ).filter((el) => el.getClientRects().length > 0);
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", trap);
    };
  }, [!!selected]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function inspect(id: number) {
    await act(async () => {
      setSelected(await api<Job>("/jobs/" + id));
      setNote("");
    });
  }
  async function update(value: string) {
    if (!selected) return;
    await act(async () => {
      await api(`/jobs/${selected.id}/status`, "POST", { status: value, note });
      setSelected(await api<Job>("/jobs/" + selected.id));
      setNote("");
      setNotice(
        "Application updated. Rankings now include the latest outcome.",
      );
    });
  }
  async function prepare() {
    if (!selected) return;
    await act(async () => {
      await api<Preparation>(`/jobs/${selected.id}/prepare`, "POST");
      setSelected(await api<Job>("/jobs/" + selected.id));
      setNotice(
        "Draft prepared from verified profile facts. Review before applying.",
      );
    });
  }
  async function preferences() {
    setView("preferences");
    await act(async () => {
      const [p, c] = await Promise.all([api("/preferences"), api("/profile")]);
      setPrefs(JSON.stringify(p, null, 2));
      setProfile(JSON.stringify(c, null, 2));
    });
  }
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => setView("ranked")}>
          <span className="brandmark">s</span> scout
          <span className="v1">V1</span>
        </a>
        <div className="workspace">
          <span className="avatar">CL</span>
          <div>
            Chengqian's workspace<small>Personal job intelligence</small>
          </div>
        </div>
        <p className="nav-label">YOUR WORKSPACE</p>
        <nav>
          {[
            ["ranked", "◈", "Opportunities"],
            ["today", "◷", "New in 24 hours"],
            ["pipeline", "▤", "Application pipeline"],
            ["sources", "◎", "Source health"],
          ].map(([key, icon, title]) => (
            <button
              key={key}
              className={view === key ? "nav active" : "nav"}
              onClick={() => {
                setView(key);
                setSelected(null);
              }}
            >
              <span>{icon}</span>
              {title}
              {key === "ranked" && <b>{stats.total}</b>}
            </button>
          ))}
          <button
            className={view === "preferences" ? "nav active" : "nav"}
            onClick={preferences}
          >
            <span>⚙</span>Preferences
          </button>
        </nav>
        <div className="sidebar-bottom">
          <span className="live-dot" /> Review mode is on
          <p>
            You choose what gets submitted.
            <br />
            Every answer stays grounded in your profile.
          </p>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            WORKSPACE{" "}
            <b>/ {view === "ranked" ? "Opportunities" : label(view)}</b>
          </span>
          <span className="today">
            {new Date().toLocaleDateString(undefined, {
              weekday: "short",
              month: "short",
              day: "numeric",
            })}
          </span>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <p className="eyebrow">
                A LITTLE MORE SIGNAL. A LOT LESS SEARCH.
              </p>
              <h1>
                {view === "ranked"
                  ? "Your next move."
                  : view === "today"
                    ? "Fresh opportunities."
                    : view === "pipeline"
                      ? "Keep things moving."
                      : view === "sources"
                        ? "Know your sources."
                        : "Make it yours."}
              </h1>
              <p className="subtitle">
                {view === "preferences"
                  ? "Verified facts and preferences shape every recommendation."
                  : "Find the work that fits your experience. Take the next step with context."}
              </p>
            </div>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await api<{ runs: { status: string }[] }>(
                    "/ingest",
                    "POST",
                    { demo: false },
                  );
                  setNotice(
                    `Discovery finished: ${r.runs.filter((x) => x.status === "ok").length}/${r.runs.length} sources healthy. See Source health for details.`,
                  );
                })
              }
            >
              {busy ? "Working…" : "↻ Discover jobs"}
            </button>
          </div>
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                ×
              </button>
            </div>
          )}
          {notice && (
            <div className="alert" role="status">
              {notice}
            </div>
          )}
          {needToken && (
            <form
              className="panel token"
              onSubmit={(e) => {
                e.preventDefault();
                sessionStorage.setItem("scout-token", token);
                act(refresh);
              }}
            >
              <label>
                Workspace API token
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  autoComplete="off"
                />
              </label>
              <button className="primary">Unlock workspace</button>
            </form>
          )}
          <div className="metrics">
            <div>
              <span>OPPORTUNITIES</span>
              <strong>
                {stats.total}
                <small>in your workspace</small>
              </strong>
            </div>
            <div>
              <span>SAVED FOR LATER</span>
              <strong>
                {stats.statuses.saved || 0}
                <small>worth a closer look</small>
              </strong>
            </div>
            <div>
              <span>IN THE PIPELINE</span>
              <strong>
                {post.reduce((n, s) => n + (stats.statuses[s] || 0), 0)}
                <small>applications & outcomes</small>
              </strong>
            </div>
            <div>
              <span>LEARNING FROM</span>
              <strong>
                {stats.feedback_count}
                <small>observed outcomes</small>
              </strong>
            </div>
          </div>
          {view === "preferences" ? (
            <div className="settings">
              <section className="panel">
                <h2>Search & preferences</h2>
                <p>
                  Configure search terms, locations, ATS board slugs and
                  optional sources. Changes rerank existing jobs.
                </p>
                <label>
                  Preferences JSON
                  <textarea
                    className="json-editor"
                    value={prefs}
                    onChange={(e) => setPrefs(e.target.value)}
                    spellCheck={false}
                  />
                </label>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api("/preferences", "PUT", JSON.parse(prefs));
                      setNotice("Preferences saved.");
                    })
                  }
                >
                  Save preferences
                </button>
              </section>
              <section className="panel">
                <h2>Candidate evidence</h2>
                <p>
                  Only add verified facts. Leave unknown answers as null. Saving
                  invalidates old application drafts.
                </p>
                <label>
                  Candidate JSON
                  <textarea
                    className="json-editor"
                    value={profile}
                    onChange={(e) => setProfile(e.target.value)}
                    spellCheck={false}
                  />
                </label>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api("/profile", "PUT", JSON.parse(profile));
                      setNotice("Candidate profile saved.");
                    })
                  }
                >
                  Save verified profile
                </button>
                <button
                  onClick={() => {
                    const blob = new Blob([profile], {
                      type: "application/json",
                    });
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(blob);
                    a.download = "candidate-profile.json";
                    a.click();
                    URL.revokeObjectURL(a.href);
                  }}
                >
                  Export profile
                </button>
              </section>
            </div>
          ) : view === "sources" ? (
            <section className="panel">
              <div className="section-heading">
                <h2>Recent discovery runs</h2>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api("/ingest", "POST", { demo: true });
                      setNotice("Synthetic demo jobs loaded.");
                    })
                  }
                >
                  Load demo jobs
                </button>
              </div>
              <p>
                Each provider runs independently. A failed source does not
                interrupt the others.
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Health</th>
                      <th>New</th>
                      <th>Duplicates</th>
                      <th>Ranked</th>
                      <th>Errors</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.runs.map((r) => (
                      <tr key={r.id}>
                        <td>
                          {r.source}
                          {r.message && (
                            <small className="run-error">{r.message}</small>
                          )}
                        </td>
                        <td>
                          <span
                            className={
                              "badge " +
                              (r.status === "ok" ? "apply" : "review")
                            }
                          >
                            {r.status}
                          </span>
                        </td>
                        <td>{r.discovered}</td>
                        <td>{r.deduplicated}</td>
                        <td>{r.ranked}</td>
                        <td>{r.errors}</td>
                        <td>{(r.duration_ms / 1000).toFixed(1)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!stats.runs.length && (
                <p>No runs yet. Discover jobs or load the demo.</p>
              )}
            </section>
          ) : (
            <>
              <div className="list-heading">
                <h2>
                  {view === "pipeline"
                    ? "Your applications"
                    : view === "today"
                      ? "Discovered in the last 24 hours"
                      : "Ranked for you"}{" "}
                  <span>{total}</span>
                </h2>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api("/rerank", "POST");
                      setNotice(
                        "Scores refreshed with current preferences and outcomes.",
                      );
                    })
                  }
                >
                  ↗ Refresh ranking
                </button>
              </div>
              <div className="filters">
                <label className="search">
                  <span>⌕</span>
                  <input
                    aria-label="Search jobs"
                    placeholder="Search roles, companies or skills…"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                  />
                </label>
                <select
                  aria-label="Recommendation filter"
                  value={decision}
                  onChange={(e) => setDecision(e.target.value)}
                >
                  <option value="">All recommendations</option>
                  {["APPLY", "REVIEW", "LOW PRIORITY", "SKIP"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
                <select
                  aria-label="Work mode filter"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="">All work modes</option>
                  {["remote", "hybrid", "on-site", "unknown"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
                <select
                  aria-label="Status filter"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="">All statuses</option>
                  {statuses.map((x) => (
                    <option key={x} value={x}>
                      {label(x)}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Data filter"
                  value={demo}
                  onChange={(e) => setDemo(e.target.value)}
                >
                  <option value="">Real + demo</option>
                  <option value="false">Real jobs only</option>
                  <option value="true">Demo only</option>
                </select>
                <input
                  aria-label="Location filter"
                  placeholder="Location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
                <select
                  aria-label="Role family filter"
                  value={family}
                  onChange={(e) => setFamily(e.target.value)}
                >
                  <option value="">All role families</option>
                  {[
                    "agentic_ai",
                    "ml_infrastructure",
                    "ml_engineering",
                    "research",
                    "ai_software",
                    "data_science",
                    "other",
                  ].map((x) => (
                    <option key={x} value={x}>
                      {label(x)}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Source filter"
                  placeholder="Source, e.g. ashby"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                />
              </div>
              <div className="job-list">
                {jobs.map((job) => (
                  <button
                    key={job.id}
                    className="job-card"
                    onClick={() => inspect(job.id)}
                  >
                    <span className="company-avatar">
                      {job.company.slice(0, 2).toUpperCase()}
                    </span>
                    <div className="job-main">
                      <div className="company-line">
                        {job.company}
                        {job.is_demo && <span className="demo-tag">DEMO</span>}
                        <span>· Discovered {date(job.discovered_at)}</span>
                      </div>
                      <h3>{job.title}</h3>
                      <p>
                        {job.location}
                        <span>·</span>
                        {label(job.work_mode)}
                        <span>·</span>
                        {job.salary_min
                          ? `${job.salary_currency || ""} ${Math.round(job.salary_min / 1000)}k–${job.salary_max ? Math.round(job.salary_max / 1000) + "k" : "?"} ${job.salary_interval || "(period unknown)"}`
                          : "Salary not listed"}
                      </p>
                      <div className="skill-row">
                        {job.analysis.skills.slice(0, 5).map((x) => (
                          <span key={x}>{x}</span>
                        ))}
                      </div>
                    </div>
                    <div className="job-score">
                      <div className="score-number">
                        {Math.round(job.ranking.score)}
                        <small>/ 100</small>
                      </div>
                      <span
                        className={
                          "badge " +
                          job.ranking.decision.toLowerCase().replace(" ", "-")
                        }
                      >
                        {job.ranking.decision}
                      </span>
                      <span className="job-status">{label(job.status)} →</span>
                    </div>
                  </button>
                ))}
                {jobs.length === 0 && (
                  <div className="empty">
                    <h2>No opportunities here yet.</h2>
                    <p>
                      Adjust the filters, discover live jobs, or load demo data
                      in Source health.
                    </p>
                  </div>
                )}
              </div>
              {jobs.length < total && limit < 500 && (
                <button onClick={() => setLimit((x) => Math.min(500, x + 100))}>
                  Show more opportunities
                </button>
              )}
              <p className="footnote">
                Scores guide your review. Verify the original posting before
                applying. Demo companies and jobs are synthetic.
              </p>
            </>
          )}
        </div>
      </main>
      {selected && (
        <div className="overlay" onClick={() => setSelected(null)}>
          <section
            className="detail"
            role="dialog"
            aria-modal="true"
            aria-label="Job details"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Escape") setSelected(null);
            }}
          >
            <div className="detail-top">
              <span>
                {selected.company}
                {selected.is_demo ? " · SYNTHETIC DEMO" : ""}
              </span>
              <button
                autoFocus
                aria-label="Close job details"
                onClick={() => setSelected(null)}
              >
                ×
              </button>
            </div>
            <h2>{selected.title}</h2>
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            <p>
              {selected.location} · {selected.work_mode} · Posted{" "}
              {date(selected.posted_at)}
            </p>
            <div className="detail-score">
              <strong>
                {selected.ranking.score}
                <small>/100</small>
              </strong>
              <div>
                <span
                  className={
                    "badge " +
                    selected.ranking.decision.toLowerCase().replace(" ", "-")
                  }
                >
                  {selected.ranking.decision}
                </span>
                <p>
                  {label(selected.analysis.role_family)} ·{" "}
                  {selected.analysis.seniority} scope
                </p>
              </div>
            </div>
            <div className="actions">
              <button
                disabled={busy || post.includes(selected.status)}
                onClick={() => update("saved")}
              >
                Save
              </button>
              <button
                disabled={busy || post.includes(selected.status)}
                onClick={() => update("dismissed")}
              >
                Dismiss
              </button>
              <button className="primary" disabled={busy} onClick={prepare}>
                Prepare application
              </button>
              {!selected.is_demo && (
                <a
                  className="button"
                  href={selected.apply_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open application ↗
                </a>
              )}
            </div>
            <h3>Why this opportunity</h3>
            <ul>
              {selected.ranking.reasons.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <div className="fit-columns">
              <div>
                <h3>Strengths</h3>
                <ul>
                  {selected.ranking.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>Gaps & things to verify</h3>
                <ul>
                  {selected.ranking.gaps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
            <h3>Score breakdown</h3>
            <div className="score-breakdown">
              {Object.entries(selected.ranking.components).map(([key, c]) => (
                <div key={key}>
                  <div>
                    <span>{label(key)}</span>
                    <b>{c.score}</b>
                  </div>
                  <meter min="0" max="100" value={c.score} />
                  <small>{c.explanation}</small>
                </div>
              ))}
            </div>
            <div className="learning">
              <h3>How feedback changed this score</h3>
              <p>
                Base {selected.ranking.base_score} + adjustment{" "}
                {selected.ranking.feedback_adjustment} ={" "}
                {selected.ranking.score}
              </p>
              {selected.ranking.feedback_explanation.length ? (
                selected.ranking.feedback_explanation.map((x, i) => (
                  <p key={i}>
                    {label(x.feature)}: {label(x.value)} · {x.observations}{" "}
                    outcomes ({x.outcomes.join(", ")}) →{" "}
                    {x.delta > 0 ? "+" : ""}
                    {x.delta} points
                  </p>
                ))
              ) : (
                <p>
                  No matching outcomes yet. Demo feedback stays separate from
                  real opportunities.
                </p>
              )}
            </div>
            {selected.preparation && (
              <section className="preparation">
                <h3>Application preparation</h3>
                <span className="badge apply">
                  {selected.preparation.resume_variant}
                </span>
                <p>{selected.preparation.company_notes}</p>
                <h4>Screening answers</h4>
                {Object.entries(selected.preparation.screening_answers).map(
                  ([key, value]) => (
                    <div className="answer" key={key}>
                      <b>{label(key)}</b>
                      <span>
                        {value.needs_review ? (
                          <em>Unknown — your review required</em>
                        ) : Array.isArray(value.answer) ? (
                          value.answer.join("; ")
                        ) : (
                          String(value.answer)
                        )}
                      </span>
                    </div>
                  ),
                )}
                <h4>Cover letter draft</h4>
                <textarea
                  aria-label="Cover letter draft"
                  readOnly
                  value={selected.preparation.cover_letter}
                />
                <button
                  onClick={() =>
                    act(async () => {
                      await navigator.clipboard.writeText(
                        selected.preparation!.cover_letter,
                      );
                      setNotice("Draft copied.");
                    })
                  }
                >
                  Copy draft
                </button>
                <ul>
                  {selected.preparation.review_checklist.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
                <p>
                  Browser assistance: use the local Playwright helper documented
                  in README. Unknown and legal questions remain for manual
                  review.
                </p>
              </section>
            )}
            <section className="tracking">
              <h3>Application tracking</h3>
              <p>
                Current stage: <b>{label(selected.status)}</b>. “Applied”
                records your manual submission.
              </p>
              <label>
                Application note
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Add context, dates, or next steps…"
                />
              </label>
              <div className="actions">
                <select
                  aria-label="Next application status"
                  value={nextStatus}
                  onChange={(e) => setNextStatus(e.target.value)}
                >
                  {statuses.map((s) => (
                    <option value={s} key={s}>
                      {label(s)}
                    </option>
                  ))}
                </select>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => update(nextStatus)}
                >
                  Update stage
                </button>
              </div>
              {selected.history?.map((e) => (
                <div className="history" key={e.id}>
                  <b>{label(e.status)}</b>
                  <span>{date(e.created_at)}</span>
                  <p>{e.note || "No note"}</p>
                </div>
              ))}
            </section>
            <details>
              <summary>Full job description & qualifications</summary>
              <pre>{selected.description}</pre>
            </details>
            <details>
              <summary>
                Source provenance ({selected.sources?.length || 0})
              </summary>
              {selected.sources?.map((s) => (
                <div key={s.id}>
                  <p>
                    <a href={s.source_url} target="_blank" rel="noreferrer">
                      {s.source}
                    </a>{" "}
                    · {s.external_id}
                  </p>
                  <pre>{JSON.stringify(s.raw, null, 2)}</pre>
                </div>
              ))}
            </details>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
