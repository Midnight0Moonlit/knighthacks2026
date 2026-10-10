# Budget Buddies

This project is a React + TypeScript frontend with a Python Flask backend and a local brain store for budget and nutrition tracking.

## Local setup

### 1) Install Node dependencies

From the project root:

```bash
npm install
```

### 2) Set up the Python virtual environment

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If `pip` is not available in the environment, install it first:

```bash
python3 -m ensurepip --upgrade
```

Then install the Python requirements:

```bash
pip install -r requirements.txt
```

### 3) Create a local environment file for Gemini

Create a `.env` file in the project root with your API key:

```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 4) Start the backend

```bash
source .venv/bin/activate
python3 app.py
```

The backend runs on port `5001`.

### 5) Start the frontend

In a second terminal:

```bash
npm run dev
```

The frontend runs on the Vite dev server, typically on port `5175` or another available port if the default is occupied.

## Useful commands

```bash
# activate env
source .venv/bin/activate

# install python deps
pip install -r requirements.txt

# build frontend
npm run build
```

## Notes

- The app keeps shopping and budget state in `brain.json`.
- The backend uses the local brain store and only calls Gemini when a new item needs macro metadata.
- The frontend uses the Flask backend through the Vite proxy configuration.
