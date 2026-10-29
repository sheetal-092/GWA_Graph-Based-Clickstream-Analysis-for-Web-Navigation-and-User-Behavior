# WebGraph Analytics

**Graph-Based Clickstream Analysis for Web Navigation and User Behavior**
Clickstream Navigation • Graph Analysis • Centrality Insights

A Streamlit dashboard that turns website clickstream data into a directed graph
(webpages = nodes, navigations = directed edges, edge weight = number of navigations)
and analyses it with NetworkX: Dijkstra's shortest path, degree, closeness, betweenness and
eigenvector centrality, PageRank, and community detection. It also includes web-analytics charts.

## Run

```powershell
# from this folder
.\.venv\Scripts\activate          # or create one: python -m venv .venv
pip install -r requirements.txt
streamlit run app.py
```

The bundled dataset `data/web_clickstream_25000_rows.xlsx` loads automatically.
To analyse another file, use **Upload** in the sidebar (CSV or Excel). Every section is
recalculated from the uploaded data. Columns are detected by name (`page_name`, `user_id`,
`user_session`, `event_time`, …) and can be remapped under **Column mapping**.

## How the navigation graph is built

1. Page views are grouped into journeys and sorted by `event_time`.
2. Consecutive pages in a journey form a directed edge `A → B`; repeated consecutive
   pages (reloads) are collapsed.
3. Edge weight = number of times `A → B` occurred. P(B | A) = weight ÷ all moves leaving A.

**Grouping.** *Auto* uses sessions (`user_id` + `user_session`) when they produce enough
transitions, and otherwise falls back to each user's events ordered by time. In the
bundled dataset, 24,339 of 24,656 sessions contain a single page view, so session-level
grouping yields only a few hundred transitions. The dashboard therefore uses user journeys
(19,094 transitions) and says so on screen. You can change this in the sidebar.

**Dijkstra cost.** A frequent link must be *cheap*, so the raw count is not used as a distance.
The default cost is `−log P(B | A)`: summing costs multiplies probabilities, so the shortest
path is the most likely navigation route. `1 / count` is available as an alternative.
Closeness and betweenness use the same cost.

## Sections

Overview · Dataset · Navigation Graph · Dijkstra / Navigation Path · Centrality Analysis ·
PageRank · Community Detection · Web Analytics · User Behavior · Results / Insights

Results (edges, centrality, communities, ordered journeys) can be downloaded as CSV from
**Results / Insights**.
