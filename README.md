# WebGraph Analytics: Graph-Based Clickstream Analysis for Web Navigation and User Behavior

## 📌 Project Overview

**WebGraph Analytics** is an interactive web dashboard developed using Streamlit to analyze website navigation patterns and user behavior through clickstream data.

Clickstream data records users' activities on a website, including the pages they visit and the sequence of their interactions. This project transforms clickstream records into a directed graph to understand how users move between webpages, identify important pages, discover navigation paths, and analyze relationships between pages.

The dashboard combines **Graph Analytics** and **Web Analytics** to provide meaningful insights through interactive visualizations and downloadable reports.

## 🎯 Objectives

- Analyze user navigation patterns using clickstream data.
- Represent webpages and their transitions as a directed graph.
- Identify frequently visited navigation paths.
- Find important webpages using centrality measures and PageRank.
- Calculate shortest paths between webpages.
- Discover groups of related webpages using community detection.
- Visualize user behavior and website analytics through an interactive dashboard.
- Allow users to upload their own clickstream datasets.
- Export analysis results for further investigation.

## ✨ Key Features

### 1. Clickstream Data Processing
- Automatically load the bundled dataset.
- Upload custom datasets in CSV or Excel format.
- Organize page views into user journeys.
- Sort user activities using event timestamps.
- Identify consecutive page-to-page transitions.

### 2. Graph Construction

The project represents website navigation as a directed graph:

- **Nodes:** Individual webpages.
- **Directed edges:** Movement from one webpage to another.
- **Edge weights:** Frequency of transitions between webpages.

### 3. Graph Algorithms and Analytics

- **Dijkstra's Algorithm:** Finds shortest navigation paths using configured edge costs.
- **Degree Centrality:** Measures the number of direct connections a webpage has.
- **Closeness Centrality:** Measures how close a webpage is to other reachable webpages.
- **Betweenness Centrality:** Identifies webpages that act as bridges between other pages.
- **Eigenvector Centrality:** Identifies webpages connected to other important webpages.
- **PageRank:** Estimates webpage importance based on the structure of incoming links.
- **Community Detection:** Identifies groups of webpages with strong connections.

### 4. Web Analytics and User Behavior

- Explore page navigation and transition patterns.
- Analyze user activity and browsing behavior.
- View web analytics charts and graph statistics.
- Examine webpage relationships through visualizations.

### 5. Results and Insights

- View graph analysis results through the dashboard.
- Download supported analysis outputs as CSV files.
- Upload different datasets to explore navigation patterns.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Interactive dashboard development |
| Pandas | Data loading, cleaning, and manipulation |
| NumPy | Numerical operations |
| NetworkX | Graph construction and graph algorithms |
| Plotly | Interactive data visualizations |
| Matplotlib | Data visualization |
| Seaborn | Statistical visualizations |
| OpenPyXL | Excel file reading support |

## 🏗️ System Workflow

1. **Data Input:** Load the bundled clickstream dataset or upload a custom CSV/Excel file.
2. **Data Preprocessing:** Inspect and prepare the data, including timestamps and relevant user or session identifiers.
3. **Journey Formation:** Arrange page views chronologically to identify consecutive webpage visits.
4. **Graph Construction:** Create a directed graph with webpages as nodes and transitions as weighted edges.
5. **Graph Analysis:** Apply shortest-path algorithms, centrality measures, PageRank, and community detection.
6. **Web Analytics:** Explore user behavior and website activity using charts and summary statistics.
7. **Results and Export:** Display insights in Streamlit and download supported results as CSV files.

## 📂 Project Structure

A typical project structure may look like this:

```text
WebGraph-Analytics/
│
├── app.py
├── requirements.txt
├── README.md
├── data/
│   └── web_clickstream_dataset.xlsx
└── assets/
    └── dashboard_screenshot.png
```

*Note: Update this structure to match the actual filenames and folders in your repository.*

## ⚙️ Installation and Setup

### Prerequisites

- Python 3.10 or a compatible version supported by your dependencies.
- pip package manager.
- Git (optional, for cloning the repository).

### Step 1: Clone the Repository

```bash
git clone https://github.com/sheetal-092/GWA_Graph-Based-Clickstream-Analysis-for-Web-Navigation-and-User-Behavior.git
```

Navigate to the project directory:

```bash
cd GWA_Graph-Based-Clickstream-Analysis-for-Web-Navigation-and-User-Behavior
```

Replace the repository URL with your actual GitHub repository URL.

### Step 2: Create a Virtual Environment (Optional)

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### Step 3: Install Dependencies

If the repository contains `requirements.txt`, run:

```bash
pip install -r requirements.txt
```

Otherwise, install the required libraries used by your application:

```bash
pip install streamlit pandas numpy networkx plotly matplotlib seaborn openpyxl
```

### Step 4: Run the Dashboard

Run the following command from the project directory:

```bash
streamlit run app.py
```

Open the local URL displayed in your terminal, usually:

```text
http://localhost:8501
```

*If your main Python file has a different name, replace `app.py` with the correct filename.*

## 📊 Input Dataset

The application works with clickstream data containing records of webpage visits and user activities.

Depending on the dataset, useful fields may include:

- User ID
- Session ID
- Event timestamp
- Webpage name or URL
- Event type
- Traffic source
- Device information
- Country
- Conversion information

The exact required columns depend on the application's data-processing logic. Ensure that uploaded datasets contain the fields expected by the dashboard.

## 📈 Expected Output

The dashboard is designed to provide:

- A visual representation of website navigation.
- Page-to-page transition frequencies.
- Graph statistics and connectivity measures.
- Shortest paths between selected webpages.
- Webpage centrality and PageRank results.
- Community detection results.
- Web analytics charts and user behavior insights.
- Downloadable CSV analysis outputs.

Actual results depend on the dataset and the graph structure generated from it.

## 🎓 Applications

- Website navigation analysis.
- User behavior analysis.
- Identification of important webpages.
- Website structure and navigation optimization.
- Exploration of user browsing journeys.
- Web analytics and research projects.

## 🔮 Future Enhancements

- Real-time clickstream data processing.
- Personalized webpage recommendations.
- User journey prediction using machine learning.
- Detection of unusual navigation patterns.
- Advanced session-based behavior analysis.
- Integration with cloud-based analytics platforms.

## 👩‍💻 Project Information

**Project Name:** Web And Graph Analytics

**Project Title:** Graph-Based Clickstream Analysis for Web Navigation and User Behavior

**Project Type:** Graph Analytics and Web Analytics

**Interface:** Streamlit Web Dashboard

## 📜 License

This project is intended for academic and educational purposes. Add a suitable open-source license, such as the MIT License, if you want others to reuse and modify the code under its terms.

## 🙌 Acknowledgment

This project demonstrates the application of graph theory, data processing, and interactive visualization techniques to understand website navigation and user behavior.
