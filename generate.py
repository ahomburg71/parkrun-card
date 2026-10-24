"""Builds docs/parkrun.svg from your Strava parkruns. Standard library only."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

TITLE = os.environ.get("CARD_TITLE", "My parkrun stats")
CHART_RUNS = int(os.environ.get("CHART_RUNS", "30"))


def api(url, data=None, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_runs():
    tok = api("https://www.strava.com/oauth/token", {
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
    })["access_token"]
    runs = []
    for page in range(1, 16):
        items = api(f"https://www.strava.com/api/v3/athlete/activities?per_page=200&page={page}", token=tok)
        for a in items:
            kind = a.get("sport_type") or a.get("type")
            if "parkrun" in a.get("name", "").lower() and kind in ("Run", "TrailRun"):
                runs.append({"date": a["start_date_local"][:10],
                             "time": int(a["elapsed_time"]),
                             "dist": float(a["distance"])})
        if len(items) < 200:
            break
    runs.sort(key=lambda r: r["date"])
    return runs


def fmt(s):
    s = int(round(s))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def day(d, with_day=True):
    dt = datetime.strptime(d, "%Y-%m-%d")
    return f"{dt.day} {dt:%b %Y}" if with_day else f"{dt:%b %Y}"


def render(runs):
    W, H = 680, 480
    FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" fill="#ffffff" stroke="#e5e7eb"/>',
           f'<text x="24" y="42" font-size="22" font-weight="700" fill="#111827">{escape(TITLE)}</text>']

    if not runs:
        out.append('<text x="24" y="90" font-size="15" fill="#6b7280">No parkruns found yet.</text></svg>')
        return "\n".join(out)

    times = [r["time"] for r in runs]
    n = len(runs)
    pb = min(times)
    pb_run = next(r for r in runs if r["time"] == pb)
    last5 = times[-5:]
    tiles = [
        ("PARKRUNS", f"{n}", "since " + day(runs[0]["date"], False)),
        ("PERSONAL BEST", fmt(pb), day(pb_run["date"])),
        ("AVERAGE", fmt(sum(times) / n), "all time"),
        ("LATEST", fmt(runs[-1]["time"]), day(runs[-1]["date"])),
        ("LAST 5 AVERAGE", fmt(sum(last5) / len(last5)), "recent form"),
        ("DISTANCE", f"{sum(r['dist'] for r in runs)/1000:,.0f} km", "total parkrun km"),
    ]
    tw, th, gap, x0, y0 = 200, 78, 16, 24, 62
    for i, (label, value, sub) in enumerate(tiles):
        x = x0 + (i % 3) * (tw + gap)
        y = y0 + (i // 3) * (th + gap)
        out.append(f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="10" fill="#f9fafb" stroke="#e5e7eb"/>')
        out.append(f'<text x="{x+14}" y="{y+22}" font-size="11" letter-spacing="0.8" fill="#6b7280">{label}</text>')
        out.append(f'<text x="{x+14}" y="{y+50}" font-size="26" font-weight="700" fill="#111827">{escape(value)}</text>')
        out.append(f'<text x="{x+14}" y="{y+67}" font-size="12" fill="#6b7280">{escape(sub)}</text>')

    # Trend chart
    recent = runs[-max(2, CHART_RUNS):]
    m = len(recent)
    cx0, cx1, cy0, cy1 = 68, W - 28, 276, 418
    rt = [r["time"] for r in recent]
    lo, hi = min(rt), max(rt)
    if hi == lo:
        hi = lo + 30
    pad = (hi - lo) * 0.12
    lo_p, hi_p = lo - pad, hi + pad
    X = lambda i: cx0 + (cx1 - cx0) * (i / (m - 1 if m > 1 else 1))
    Y = lambda t: cy0 + (cy1 - cy0) * ((t - lo_p) / (hi_p - lo_p))  # faster = higher

    for t in (lo, (lo + hi) / 2, hi):
        y = round(Y(t), 1)
        out.append(f'<line x1="{cx0}" x2="{cx1}" y1="{y}" y2="{y}" stroke="#eef0f3"/>')
        out.append(f'<text x="{cx0-8}" y="{y+4}" font-size="11" text-anchor="end" fill="#6b7280">{fmt(t)}</text>')
    pts = " ".join(f"{X(i):.1f},{Y(r['time']):.1f}" for i, r in enumerate(recent))
    out.append(f'<polyline points="{pts}" fill="none" stroke="#0f766e" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, r in enumerate(recent):
        is_pb = r["time"] == pb
        out.append(f'<circle cx="{X(i):.1f}" cy="{Y(r["time"]):.1f}" r="{6 if is_pb else 3.5}" fill="{"#f59e0b" if is_pb else "#0f766e"}" stroke="#ffffff" stroke-width="1.5"/>')
    out.append(f'<text x="{cx0}" y="{cy1+22}" font-size="11" fill="#6b7280">{day(recent[0]["date"], False)}</text>')
    out.append(f'<text x="{cx1}" y="{cy1+22}" font-size="11" text-anchor="end" fill="#6b7280">{day(recent[-1]["date"], False)}</text>')
    out.append(f'<text x="24" y="{H-14}" font-size="11" fill="#9ca3af">Last {m} parkruns · gold dot = PB · updated {datetime.now(timezone.utc):%-d %b %Y}</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    svg = render(get_runs())
    os.makedirs("docs", exist_ok=True)
    with open("docs/parkrun.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote docs/parkrun.svg")
