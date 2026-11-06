#!/usr/bin/env python3
"""Generate animated profile cards (stats + top languages) as local SVG files.

The SVGs are committed to the repo, so the README never depends on a
third-party image server that can be rate-limited or go down.

Environment variables:
  GH_LOGIN  GitHub username (defaults to "sntiago05")
  GH_TOKEN  Token used for the GraphQL API (GITHUB_TOKEN works for public data)
"""
import json
import os
import urllib.request
from html import escape
from pathlib import Path

API_URL = "https://api.github.com/graphql"
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

WIDTH, HEIGHT = 420, 250

STYLE = """
  .card { fill: #0d1117; stroke: #30363d; stroke-width: 1; }
  text  { font-family: 'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif; }
  .title { font-size: 17px; font-weight: 600; fill: #58a6ff; }
  .label { font-size: 13px; fill: #c9d1d9; }
  .value { font-size: 13px; font-weight: 600; fill: #f0f6fc; }
  .track { fill: #21262d; }
  .divider { stroke: #21262d; stroke-width: 1; }
  .accent { fill: url(#accent); transform-box: fill-box; transform-origin: left center;
            transform: scaleX(0); animation: grow 1.1s cubic-bezier(.22, 1, .36, 1) .1s forwards; }
  .fade { opacity: 0; animation: fadeIn .6s ease-out forwards; }
  .bar  { transform-box: fill-box; transform-origin: left center; transform: scaleX(0);
          animation: grow 1.1s cubic-bezier(.22, 1, .36, 1) forwards; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); }
                      to   { opacity: 1; transform: translateY(0); } }
  @keyframes grow   { to { transform: scaleX(1); } }
  @media (prefers-reduced-motion: reduce) {
    .fade, .bar, .accent { animation: none; opacity: 1; transform: none; }
  }
"""


def fetch_user(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards-generator",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    return payload["data"]["user"]


def summarize(user: dict):
    repos = user["repositories"]["nodes"]

    languages: dict[str, dict] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            node = edge["node"]
            entry = languages.setdefault(
                node["name"], {"size": 0, "color": node["color"] or "#8b949e"}
            )
            entry["size"] += edge["size"]

    total = sum(v["size"] for v in languages.values()) or 1
    ranked = sorted(languages.items(), key=lambda kv: kv[1]["size"], reverse=True)[:6]
    top_languages = [(name, v["size"] / total * 100, v["color"]) for name, v in ranked]

    contributions = user["contributionsCollection"]
    stats = [
        ("Contributions (last year)", contributions["contributionCalendar"]["totalContributions"]),
        ("Commits (last year)", contributions["totalCommitContributions"]),
        ("Pull requests", user["pullRequests"]["totalCount"]),
        ("Issues", user["issues"]["totalCount"]),
        ("Public repositories", user["repositories"]["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos)),
    ]
    return stats, top_languages


def card(title: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(title)}">
  <title>{escape(title)}</title>
  <defs>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#58a6ff"/><stop offset="1" stop-color="#bc8cff"/>
    </linearGradient>
  </defs>
  <style>{STYLE}</style>
  <rect class="card" x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="10"/>
  <text class="title fade" x="24" y="38">{escape(title)}</text>
  <rect class="accent" x="24" y="48" width="120" height="3" rx="1.5"/>
{body}
</svg>
"""


def stats_card(stats) -> str:
    rows = []
    for i, (label, value) in enumerate(stats):
        y = 84 + i * 28
        delay = 0.15 + i * 0.1
        rows.append(
            f'  <g class="fade" style="animation-delay:{delay:.2f}s">'
            f'<text class="label" x="24" y="{y}">{escape(label)}</text>'
            f'<text class="value" x="{WIDTH - 24}" y="{y}" text-anchor="end">{value:,}</text>'
            f'<line class="divider" x1="24" x2="{WIDTH - 24}" y1="{y + 10}" y2="{y + 10}"/></g>'
        )
    return card("GitHub stats", "\n".join(rows))


def languages_card(languages) -> str:
    bar_x, bar_w = 24, WIDTH - 48
    rows = []
    for i, (name, percent, color) in enumerate(languages):
        y = 82 + i * 28
        delay = 0.15 + i * 0.1
        fill_w = max(bar_w * percent / 100, 4)
        rows.append(
            f'  <g class="fade" style="animation-delay:{delay:.2f}s">'
            f'<text class="label" x="{bar_x}" y="{y}">{escape(name)}</text>'
            f'<text class="value" x="{WIDTH - 24}" y="{y}" text-anchor="end">{percent:.1f}%</text>'
            f'<rect class="track" x="{bar_x}" y="{y + 7}" width="{bar_w}" height="6" rx="3"/></g>'
            f'  <rect class="bar" x="{bar_x}" y="{y + 7}" width="{fill_w:.1f}" height="6" rx="3" '
            f'fill="{escape(color)}" style="animation-delay:{delay + 0.25:.2f}s"/>'
        )
    return card("Top languages", "\n".join(rows))


def write_cards(stats, languages) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "stats.svg").write_text(stats_card(stats), encoding="utf-8")
    (OUT_DIR / "top-langs.svg").write_text(languages_card(languages), encoding="utf-8")


def main() -> None:
    login = os.environ.get("GH_LOGIN", "sntiago05")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_TOKEN (or GITHUB_TOKEN) before running this script.")
    stats, languages = summarize(fetch_user(login, token))
    write_cards(stats, languages)
    print(f"Cards written to {OUT_DIR}")


if __name__ == "__main__":
    main()
