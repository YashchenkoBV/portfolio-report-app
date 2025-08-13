# portfolio-report-app
Application that extracts the data from different brokers reports belonging to one investor and assembles a consolidated portfolio report.

## How to Run

```bash
# 1) Clone
git clone https://github.com/YashchenkoBV/portfolio-report-app.git
cd portfolio-report-app

# 2) (Recommended) Create venv
python -m venv .venv
# Windows PowerShell:
. .venv\\Scripts\\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Put PDFs into ./data/
# (e.g. Copy of Executive Summary.pdf, Account broker report ....pdf, etc.)

# 5) Launch
python -m src.app
# Then open:
# http://127.0.0.1:5000/
