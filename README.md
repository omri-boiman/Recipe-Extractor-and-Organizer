# Recipe Organizer

A full‑stack app that extracts structured recipes from web pages using BeautifulSoup and GitHub Models (Azure AI Inference), stores them in SQLite, and serves a React/Tailwind frontend.

## Demo Video
### Main Page
https://github.com/user-attachments/assets/e0bcfaa0-bc83-4208-9e78-7fd02438990c

### Extraction
https://github.com/user-attachments/assets/f5133b98-01fd-4c84-9751-abb5b01300c4

### AI ChatBot
https://github.com/user-attachments/assets/d8b7bad6-7873-4c37-802a-8f6b20492d41

### Edit
https://github.com/user-attachments/assets/e1f3873d-1b5e-4dc8-aea5-43a420711fd5

## Tech stack
- Backend: FastAPI, Pydantic, SQLite, BeautifulSoup, Requests
- AI: Azure AI Inference (GitHub Models) via `azure-ai-inference`
- Frontend: Vite + React + TailwindCSS

## Prerequisites
- Python 3.10+
- Node.js 18+
- A GitHub Models token for Azure AI Inference

## Setup

1) Clone and enter the project folder

2) Create your environment file
- Copy `.env.example` to `.env` and set `GITHUB_TOKEN`.
- Alternatively, create an `apikey.txt` file in the project root that contains your token (one line). `.gitignore` prevents this file from being committed.

3) Install Python dependencies
```
pip install -r requirements.txt
```

4) Run the backend
- Dev mode:
```
py -Xutf8 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
- Or use the VS Code task: "Run FastAPI app (py)"

5) Run the frontend (optional)
```
cd frontend
npm install
npm run dev
```
Visit http://127.0.0.1:5173 (Vite dev) or use the built assets after `npm run build` which the backend can serve from `frontend/dist`.

## Environment variables
- `GITHUB_TOKEN` (required): Your token for GitHub Models (Azure AI Inference)
- `AZURE_ENDPOINT` (optional): Defaults to `https://models.github.ai/inference`
- `MODEL_NAME` (optional): Defaults to `openai/gpt-4.1`

### Troubleshooting tokens
- Use a GitHub token (classic `ghp_...` or fine-grained `github_pat_...`). OpenAI keys starting with `sk-` will NOT work for `https://models.github.ai/inference`.
- Put only ONE token in `.env` (e.g., `GITHUB_TOKEN=ghp_...`) or in `apikey.txt` (one line). Do not paste notes or multiple keys.
- If you accidentally pasted multiple lines into `apikey.txt`, the app will try to pick the first valid GitHub token and otherwise fail with a clear error.

## Data storage
- SQLite DB at `recipes.db` (ignored by git)
- Uploaded images in `uploads/` (ignored by git). A `.gitkeep` is included to keep the folder.

## Security notes
- Secrets are NOT stored in the repo. Use `.env` or `apikey.txt` locally. Never commit real tokens.
- If a token was previously committed, rotate it immediately.

## API quick reference
- `POST /extract-recipe?url=...` → Extracts and saves a recipe
- `GET /recipes` → Lists saved recipes (structured for UI)
- `DELETE /recipes?source_url=...` → Deletes a recipe
- `POST /recipes/upload-image` (multipart form) → Associates an image with a recipe
- `GET /db-health` → Basic DB integrity and counts

## License
MIT — see `LICENSE`.
