import argparse
import os

import pandas as pd
import plotly.graph_objects as go
import requests

GOOGLE_SHEET_ID = "1lsujljioMTZ6yPSuZV3ddWvFWKfbytl9A2K4AWJ9DsE"

# Default/fallback database, used only when no id is passed in. Override per run
# via the NOTION_DATABASE_ID env var or a CLI arg (`uv run sankey <database_id>`).
# The Notion integration behind NOTION_TOKEN must be connected to whichever
# database you point at, or the API returns 404.
NOTION_DATABASE_ID = "3a6f62e9446280ef9305c136f374523f"  # the original "Stakeholders" DB
NOTION_VERSION = "2022-06-28"


def from_sheets(gid: int = 0) -> pd.DataFrame:
    # Public sheet exported as CSV. Columns: Source, Target, Weight.
    sheet = fr"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={gid}"
    return pd.read_csv(sheet)


def _plain(prop: dict):
    """Extract a scalar value from a Notion property, whatever its type."""
    kind = prop["type"]
    value = prop[kind]
    if kind in ("title", "rich_text"):
        return value[0]["plain_text"] if value else None
    if kind == "select":
        return value["name"] if value else None
    if kind in ("number", "checkbox", "url", "email", "phone_number"):
        return value
    if kind == "formula":
        return value.get(value["type"])
    return value


def from_notion(database_id: str = None) -> pd.DataFrame:
    """Query a Notion database into a Source/Target/Weight DataFrame.

    Requires NOTION_TOKEN in the environment and the database shared with the
    integration. Expects Source, Target, and Weight properties on each row.
    """
    database_id = database_id or NOTION_DATABASE_ID
    token = os.environ["NOTION_TOKEN"]
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    rows, payload = [], {}
    while True:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        for page in data["results"]:
            props = page["properties"]
            rows.append({
                "Source": _plain(props["Source"]),
                "Target": _plain(props["Target"]),
                "Weight": _plain(props["Weight"]),
            })
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    return pd.DataFrame(rows)


def make_figure(source: str = "notion", gid: int = 0, database_id: str = None):
    if source == "notion":
        df = from_notion(database_id)
    else:
        df = from_sheets(gid)

    # Build the node list from every label that appears as a source or target,
    # then map each label to its index in that list.
    labels = pd.unique(df[["Source", "Target"]].values.ravel()).tolist()
    index = {label: i for i, label in enumerate(labels)}

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            label=labels,
            pad=15,
            thickness=20
        ),
        link=dict(
            source=df["Source"].map(index),
            target=df["Target"].map(index),
            value=df["Weight"].fillna(1)
        )
    )])

    fig.update_layout(
        title="Sankey",
        font=dict(size=16, family="Arial Black", color="black"),
        width=900,
        height=600
    )

    # Export options
    fig.write_html("value_sankey.html", include_plotlyjs="cdn")  # small HTML (plotly from CDN)
    fig.write_image("value_sankey.png")  # Static image


def main() -> None:
    """Entry point (`uv run sankey [database_id] [--source ...] [--gid ...]`).

    The database id resolves as: CLI arg -> $NOTION_DATABASE_ID -> the module
    default (in from_notion). This is how the GitHub Action passes the id
    through from the Notion link -> Worker -> repository_dispatch payload.
    """
    parser = argparse.ArgumentParser(
        prog="sankey",
        description="Build a Sankey diagram from a Notion database (or a Google Sheet).",
    )
    parser.add_argument(
        "database_id",
        nargs="?",
        default=os.environ.get("NOTION_DATABASE_ID"),
        help="Notion database id to render. Defaults to $NOTION_DATABASE_ID, "
             "then the module default. Ignored when --source=sheets.",
    )
    parser.add_argument(
        "--source",
        choices=("notion", "sheets"),
        default="notion",
        help="Where to read Source/Target/Weight rows from (default: notion).",
    )
    parser.add_argument(
        "--gid",
        type=int,
        default=0,
        help="Google Sheet tab gid, used when --source=sheets (default: 0).",
    )
    args = parser.parse_args()
    make_figure(source=args.source, gid=args.gid, database_id=args.database_id)
