"""Recompute the usage KPIs quoted in showcase/README.md.

    python -I showcase/kpi.py <repo>/.longshot/state.db [<other>/.longshot/state.db ...]

Every database is opened read-only. Token usage is read from what each
participant left on disk:

- a Claude Code job: the final `result` event in `jobs.log_dir`, per model;
- a Codex job: the rollout named by the `session id` in its stderr, under any
  ~/.codex* home or its `codexHome`; without one, "tokens used" (a total only);
- a Copilot job: `session.shutdown` in ~/.copilot/session-state/<id>, the id
  taken from its `--share` transcript;
- a full-history coordinator thread: its Codex rollout or its Claude SDK
  session file. A historyless thread leaves neither and stays unmeasured.

opencode, qoder and shell jobs report none. The runner account count comes
from ~/.longshot/app.db.
"""
import glob, json, os, re, sqlite3, statistics as st, sys
from collections import Counter
from datetime import datetime, timezone


def ro(path):
    return sqlite3.connect("file:" + os.path.abspath(path) + "?mode=ro", uri=True)


def ts(s):
    if not s:
        return None
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?", s)
    return datetime.fromisoformat(m.group(1) + (m.group(2) or ".0")[:7]).replace(tzinfo=timezone.utc)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def hm(sec):
    return f"{sec / 3600:.1f} h" if sec >= 3600 else f"{sec / 60:.0f} min"


jobs, threads, leases, deliv, mbox = [], [], [], [], []
for i, path in enumerate(sys.argv[1:]):
    c = ro(path)
    c.row_factory = sqlite3.Row
    rows = lambda q: [dict(r, db=i) for r in c.execute(q)]
    jobs += rows("select * from jobs")
    threads += rows("select * from threads")
    leases += rows("select * from mission_lease")
    deliv += rows("select status from deliveries")
    mbox += rows("select status from mailbox_events")


def put(k, v):
    print(f"{k:34} {v}")


put("jobs", len(jobs))
put("jobs per database", {sys.argv[1 + i]: n for i, n in sorted(Counter(j["db"] for j in jobs).items())})
put("jobs by runtime", dict(Counter(j["runtime"] for j in jobs).most_common()))
put("jobs by status", dict(Counter(j["status"] for j in jobs).most_common()))
done = [j for j in jobs if j["status"] in ("completed", "failed", "lost", "cancelled")]
put("success rate %", round(100 * sum(j["status"] == "completed" for j in done) / len(done), 1))
put("worktree-isolated jobs", sum(j["isolation"] == "worktree" for j in jobs))
models = Counter(re.sub(r"(:cloud|@\w+)$", "", j["model"].split("/")[-1]) for j in jobs if j["model"])
put("distinct worker models", len(models))
put("top models", dict(models.most_common(8)))

# lost jobs have no real end: their ended_at is when recovery noticed them
spans = [(ts(j["started_at"]), ts(j["ended_at"])) for j in jobs if j["status"] != "lost" and j["started_at"] and j["ended_at"]]
dur = [(b - a).total_seconds() for a, b in spans if b > a]
put("job duration median/p90/max", f"{hm(st.median(dur))} / {hm(pct(dur, .9))} / {hm(max(dur))}")
put("worker hours", round(sum(dur) / 3600, 1))
cur = peak = 0
for _, d in sorted([(a, 1) for a, b in spans] + [(b, -1) for a, b in spans]):
    cur += d
    peak = max(peak, cur)
put("peak parallel workers", peak)
days = Counter(ts(j["created_at"]).date().isoformat() for j in jobs)
put("active days / peak jobs per day", f"{len(days)} / {max(days.values())}")
put("first / last job", f"{min(days)} / {max(days)}")
put("jobs per day", dict(sorted(days.items())))
put("max jobs from one thread", max(Counter((j["db"], j["owner_thread_id"]) for j in jobs).values()))

put("coordinator threads", f"{len(threads)} {dict(Counter(t['backend'] for t in threads))}")
life = [((ts(t["closed_at"]) or ts(t["updated_at"])) - ts(t["created_at"])).total_seconds() for t in threads]
put("thread lifetime median/max", f"{hm(st.median(life))} / {hm(max(life))}")
put("wake-ups confirmed / attempted", f"{sum(d['status'] == 'confirmed' for d in deliv)} / {len(deliv)}")
put("mailbox events", f"{len(mbox)} {dict(Counter(m['status'] for m in mbox))}")
lease = [(ts(l["closed_at"]) - ts(l["started_at"])).total_seconds() for l in leases if l["closed_at"]]
put("engine sessions (leases)", f"{len(leases)} {dict(Counter(l['close_reason'] or 'open/crashed' for l in leases))}")
put("session median/max/total", f"{hm(st.median(lease))} / {hm(max(lease))} / {sum(lease) / 3600:.0f} h")

app = os.path.expanduser("~/.longshot/app.db")
if os.path.exists(app):
    put("runner accounts", dict(ro(app).execute("select runtime, count(*) from runtime_accounts group by 1").fetchall()))

# Token usage. Every source is normalized to the same classes: input without
# cache, cache read, cache write, output (reasoning is part of output and is
# shown, never added). A participant with no usage source is counted as
# unmeasured, never as zero.
def jsonl(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                pass


def index(dirs, pattern):
    found = {}
    for d in dirs:
        for f in glob.glob(os.path.join(d, pattern), recursive=True):
            m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27})\.jsonl$", f)
            if m:
                found[m.group(1)] = f
    return found


home = os.path.expanduser("~")
codex_homes = set(glob.glob(os.path.join(home, ".codex*"))) | {os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")}
codex_homes |= {json.loads(j["options_json"] or "{}").get("codexHome") or "" for j in jobs} - {""}
rollouts = index([os.path.join(h, s) for h in codex_homes for s in ("sessions", "archived_sessions")], "**/rollout-*.jsonl")
claude_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude")
claude_sessions = index([os.path.join(claude_dir, "projects")], "*/*.jsonl")
copilot_state = os.path.join(os.environ.get("COPILOT_HOME") or os.path.join(home, ".copilot"), "session-state")


def codex_rollout(path):
    # Codex counts cached tokens inside input_tokens, and the last token_count
    # holds the running total of the whole thread.
    total, model = None, ""
    for e in jsonl(path):
        p = e.get("payload") or {}
        if e.get("type") == "turn_context":
            model = p.get("model") or model
        elif e.get("type") == "event_msg" and p.get("type") == "token_count" and p.get("info"):
            total = p["info"]["total_token_usage"]
    if not total:
        return []
    return [(model, dict(input=total["input_tokens"] - total["cached_input_tokens"], cache_read=total["cached_input_tokens"],
                         cache_write=total.get("cache_write_input_tokens", 0), output=total["output_tokens"],
                         reasoning=total.get("reasoning_output_tokens", 0)))]


def claude_session(path):
    # The SDK writes one line per content block and repeats the message's usage
    # on each, so a message is counted once, by its id.
    seen, out = set(), {}
    for e in jsonl(path):
        m = e.get("message") or {}
        if e.get("type") != "assistant" or not m.get("usage") or m.get("id") in seen or m.get("model") == "<synthetic>":
            continue
        seen.add(m.get("id"))
        u = m["usage"]
        out.setdefault(m.get("model", ""), Counter()).update(
            input=u.get("input_tokens", 0), cache_read=u.get("cache_read_input_tokens", 0),
            cache_write=u.get("cache_creation_input_tokens", 0), output=u.get("output_tokens", 0), requests=1)
    return [(model, dict(c)) for model, c in out.items()]


def claude_result(j, res):
    # Claude Code prices every model as if Anthropic served it, so its figure
    # for a model behind another baseUrl is kept apart from the list price.
    if res.get("modelUsage"):
        return [(m, dict(input=u.get("inputTokens", 0), cache_read=u.get("cacheReadInputTokens", 0),
                         cache_write=u.get("cacheCreationInputTokens", 0), output=u.get("outputTokens", 0),
                         turns=res.get("num_turns", 0) if k == 0 else 0, cents=round(100 * (u.get("costUSD") or 0))))
                for k, (m, u) in enumerate(res["modelUsage"].items())]
    u = res["usage"]
    return [(j["model"] or "", dict(input=u.get("input_tokens", 0), cache_read=u.get("cache_read_input_tokens", 0),
                                    cache_write=u.get("cache_creation_input_tokens", 0), output=u.get("output_tokens", 0),
                                    turns=res.get("num_turns", 0), cents=round(100 * (res.get("total_cost_usd") or 0))))]


def copilot_shutdown(data):
    # Copilot counts cache reads and writes inside inputTokens.
    out = [(m, dict(input=u["inputTokens"] - u.get("cacheReadTokens", 0) - u.get("cacheWriteTokens", 0),
                    cache_read=u.get("cacheReadTokens", 0), cache_write=u.get("cacheWriteTokens", 0),
                    output=u.get("outputTokens", 0), reasoning=u.get("reasoningTokens", 0),
                    requests=v.get("requests", {}).get("count", 0)))
           for m, v in data.get("modelMetrics", {}).items() for u in [v["usage"]]]
    if out:
        out[0][1]["premium"] = data.get("totalPremiumRequests", 0)
    return out


def read(path):
    return open(path, encoding="utf-8", errors="replace").read() if os.path.isfile(path) else ""


def job_usage(j):
    """[(model, classes)] for one job; [] when it left no usage anyone can read."""
    ld, rt = j["log_dir"], j["runtime"]
    if rt == "claude-code" and os.path.isfile(os.path.join(ld, "stdout.log")):
        res = None
        for e in jsonl(os.path.join(ld, "stdout.log")):
            if e.get("type") == "result":
                res = e
        if res and (res.get("modelUsage") or res.get("usage")):
            return claude_result(j, res)
    elif rt == "codex":
        err = read(os.path.join(ld, "stderr.log"))
        sid = re.search(r"session id: ([0-9a-f-]{36})", err)
        if sid and sid.group(1) in rollouts:
            return codex_rollout(rollouts[sid.group(1)])
        m = re.findall(r"tokens used\s*\n\s*([\d,]+)", err)
        if m:
            return [(j["model"] or "", dict(total_only=int(m[-1].replace(",", ""))))]
    elif rt == "copilot":
        sid = re.search(r"Session ID:\*\*\s*`([0-9a-f-]{36})`", read(os.path.join(ld, "transcript.md")))
        ev = os.path.join(copilot_state, sid.group(1), "events.jsonl") if sid else ""
        if ev and os.path.isfile(ev):
            for e in jsonl(ev):
                if e.get("type") == "session.shutdown":
                    return copilot_shutdown(e["data"])
    return []


def thread_usage(t):
    # Only a full-history thread keeps one backend thread for its whole life. A
    # historyless thread runs each turn on a step carrier that Codex never
    # persists and whose Claude session id Longshot does not keep.
    if t["execution_mode"]:
        return []
    if t["backend"] == "codex":
        tid = t["backend_thread_id"] or t["thread_id"]
        return codex_rollout(rollouts[tid]) if tid in rollouts else []
    sid = t["backend_session_id"]
    return claude_session(claude_sessions[sid]) if sid in claude_sessions else []


def options(j):
    return json.loads(j["options_json"] or "{}")


def account(j):
    o = options(j)
    # A job spawned before the account axis existed ran on its runtime's default account.
    default = {"claude-code": "claude"}.get(j["runtime"], j["runtime"]) + ":default"
    return o.get("target") or ("baseUrl " + o["baseUrl"] if o.get("baseUrl") else default)


CLASSES = ("input", "cache_read", "cache_write", "output")
groups, coverage, cl = {}, Counter(), Counter()
participants = [("job", j["runtime"], account(j), j, job_usage(j)) for j in jobs]
participants += [("coordinator", t["backend"], t["account"] or "default", t, thread_usage(t)) for t in threads]
for role, rt, acc, row, usage in participants:
    coverage[(role, rt)] += 0
    if not usage:
        continue
    coverage[(role, rt)] += 1
    tokens = turns = 0
    for model, u in usage:
        if "total_only" in u:
            cl.update(codex_total_only=1, codex_total_only_tokens=u["total_only"])
            continue
        g = groups.setdefault((role, rt, acc, model), Counter())
        g.update({k: v for k, v in u.items() if k not in ("cents", "turns")}, participants=1)
        tokens += sum(u[k] for k in CLASSES)
        turns += u.get("turns", 0)
        if role == "job" and rt == "claude-code":
            cl["list_cents" if not options(row).get("baseUrl") else "other_cents"] += u.get("cents", 0)
    if role == "job" and rt == "claude-code":
        cl.update(jobs=1, tokens=tokens, turns=turns)
        cl["max_tokens"] = max(cl["max_tokens"], tokens)
        cl["max_turns"] = max(cl["max_turns"], turns)
totals = Counter((role, rt) for role, rt, *_ in participants)


def classes(c):
    return (f"{sum(c[k] for k in CLASSES) / 1e6:.1f}M tokens (input {c['input'] / 1e6:.2f}M, cache read {c['cache_read'] / 1e6:.1f}M, "
            f"cache write {c['cache_write'] / 1e6:.2f}M, output {c['output'] / 1e6:.2f}M incl. reasoning {c['reasoning'] / 1e6:.2f}M)")


put("usage coverage (measured/all)", ", ".join(f"{role} {rt} {coverage[(role, rt)]}/{n}" for (role, rt), n in sorted(totals.items())))
for role, rt in sorted(totals):
    s = sum((g for (r, t, _, _), g in groups.items() if (r, t) == (role, rt)), Counter())
    if s:
        share = 100 * s["cache_read"] / sum(s[k] for k in CLASSES)
        premium = f", {s['premium']} premium requests" if s["premium"] else ""
        put(f"usage {role} {rt}", f"{classes(s)}, {share:.0f} % cache reads{premium}")
cc = sum((g for (role, rt, _, _), g in groups.items() if role == "job" and rt == "claude-code"), Counter())
put("claude-code usage", f"{cl['jobs']} jobs, {classes(cc)}, {cl['turns']} turns, max {cl['max_turns']} turns / "
    f"{cl['max_tokens'] / 1e6:.0f}M tokens in one job")
put("claude-code list price", f"${cl['list_cents'] / 100:.0f} on Anthropic accounts; the ${cl['other_cents'] / 100:.0f} "
    f"Claude Code reports for models served elsewhere is not a price")
if cl["codex_total_only"]:
    put("codex jobs without rollout", f"{cl['codex_total_only']} jobs, {cl['codex_total_only_tokens'] / 1e6:.1f}M tokens, classes unknown")
for (role, rt, acc, model), g in sorted(groups.items(), key=lambda kv: -sum(kv[1][k] for k in CLASSES)):
    premium = f", {g['premium']} premium requests" if g["premium"] else ""
    put(f"usage {role} {rt} {acc}", f"{model or '?'} x{g['participants']}: {classes(g)}{premium}")
