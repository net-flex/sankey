import pandas as pd
import plotly.graph_objects as go

SHEET_ID = "1lsujljioMTZ6yPSuZV3ddWvFWKfbytl9A2K4AWJ9DsE"


def make_figure(gid: int = 0):
    # Sheet columns: Source, Target, Weight
    sheet = fr"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

    df = pd.read_csv(sheet)

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
    fig.write_html("value_sankey.html")  # Interactive web version
    fig.write_image("value_sankey.png")  # Static image
