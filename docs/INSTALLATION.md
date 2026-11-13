# Installation & Local Setup — Quality Intelligence

This guide walks you through setting up Quality Intelligence on your local environment.

---

## 1. System Requirements

- **Operating System**: Linux, macOS, or Windows 10/11
- **Python**: Version 3.10, 3.11, 3.12, or 3.13
- **Node.js**: Version 18.0.0 or higher (`npm` 9.0+)
- **Git**: Git 2.30+ installed and available in system PATH

---

## 2. Clone the Repository

```bash
git clone https://github.com/Sanjayt215/Quality-Intelligence.git
cd Quality-Intelligence
```

---

## 3. Backend Setup (FastAPI & ML Engine)

1. **Create and Activate Python Virtual Environment**:
   ```bash
   # Linux / macOS
   python -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Python Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   ```bash
   # Copy sample configuration
   cp .env.example .env
   ```

4. **Start the FastAPI Backend**:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *The backend will be live at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.*

---

## 4. Frontend Setup (React 18 + Vite)

1. **Navigate to Frontend Directory**:
   ```bash
   cd frontend
   ```

2. **Install Node Dependencies**:
   ```bash
   npm install
   ```

3. **Start the Vite Development Server**:
   ```bash
   npm run dev -- --host 0.0.0.0 --port 5173
   ```
   *The frontend dashboard will be available at `http://localhost:5173`.*

4. **Build for Production (Optional)**:
   ```bash
   npm run build
   ```

---

## 5. Standalone Streamlit Dashboard (Optional)

If you prefer the executive Streamlit interface:
```bash
python -m streamlit run app.py --server.port 8501
```
*Accessible at `http://localhost:8501`.*

---

## 6. Docker Deployment (Alternative)

Run the full stack containerized with Docker Compose:
```bash
docker-compose up --build
```
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Streamlit: `http://localhost:8501`
