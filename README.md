# 💸 Money Muling Detection & Financial Forensics Dashboard

A **production-style financial forensics tool** that detects money mule networks from raw transaction data using graph theory. Upload a CSV, get instant fraud ring analysis with interactive network visualizations.

---

## 📸 Features

- 🔍 **Fraud Pattern Detection** — Cycles, Smurfing (fan-in/fan-out), Shell Chains
- 🕸️ **Interactive Network Graph** — Focus, Suspicious Only, Full Network views
- ⭐ **Smurfing Star Layout** — Aggregator nodes visualized at the center of radial graphs
- 📊 **Pattern Distribution Charts** — Animated bar charts per detected fraud type
- 🧠 **Ring Intelligence Panel** — Per-ring explanation, risk score, member list
- ⚡ **Optimized Engine** — Vectorized detection pipeline (handles 5k+ rows)
- 📥 **JSON Export** — Download full analysis results

---

## 🗂️ Project Structure

```
Money Muling Detection system/
├── app/
│   ├── main.py                  # FastAPI app — routes & file upload
│   ├── detection/
│   │   ├── scoring.py           # Main orchestrator — FraudDetector class
│   │   ├── cycles.py            # Cycle detection (length 3–5)
│   │   ├── smurfing.py          # Fan-in / fan-out detection (vectorized)
│   │   └── shell.py             # Layered shell chain detection
│   ├── templates/
│   │   ├── index.html           # Upload page
│   │   └── results.html         # Dashboard results page
│   └── static/
│       ├── graph.js             # Cytoscape.js graph logic & interactions
│       └── styles.css           # Dashboard styling
├── Documentation/
│   └── PS2_MoneyMuling_GraphTheory.docx
├── requirements.txt
├── run_app.bat                  # Windows quick-start script
└── .gitignore
```

---



## 🖥️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python, FastAPI, Uvicorn |
| **Graph Analysis** | NetworkX |
| **Data Processing** | Pandas, NumPy |
| **Frontend** | Vanilla JS, HTML5, CSS3 |
| **Graph Visualization** | Cytoscape.js |
| **Templating** | Jinja2 |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/money-muling-detection.git
cd money-muling-detection

# 2. Create & activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

> **Windows users**: Double-click `run_app.bat` to start directly.

---

## 📂 Input Format

Upload a `.csv` file with the following required columns:

| Column | Type | Description |
|---|---|---|
| `transaction_id` | string | Unique transaction identifier |
| `sender_id` | string | Source account ID |
| `receiver_id` | string | Destination account ID |
| `amount` | float | Transaction amount |
| `timestamp` | datetime | Transaction timestamp (any standard format) |

---

## 🧠 Detection Engine

### Patterns Detected

| Pattern | Algorithm | Risk |
|---|---|---|
| **Cycle** | DFS cycle detection on DiGraph (length 3–5) | 🔴 HIGH |
| **Smurfing** | Two-pointer sliding window, O(n), detect ≥10 unique accounts in 72h | 🔴 HIGH (aggregator) / 🟡 MEDIUM (neighbors) |
| **Shell Chain** | Long-path detection through low-degree intermediary nodes | 🔴 HIGH (intermediates) |

### Performance Optimizations
- Graph built via `nx.from_pandas_edgelist()` (no `iterrows`)
- Merchant detection via vectorized `pandas.groupby().nunique()`
- Smurfing O(n²) loop replaced with O(n) two-pointer sliding window
- Frontend layouts cached after first render — repeat clicks are instant

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Upload page |
| `POST` | `/api/upload` | Upload CSV, run analysis |
| `GET` | `/results` | Dashboard results page |
| `GET` | `/api/results` | Fetch latest analysis JSON |
| `GET` | `/api/download` | Download results as `results.json` |

---

## 👤 Author

Built for the **Financial Forensics & AML Detection Hackathon**.
