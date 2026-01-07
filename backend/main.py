import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import FRONTEND_DIR, DIST_DIR, UPLOAD_DIR
from .db import init_db
from .routes.recipes import router as recipes_router
from .routes.ask import router as ask_router
from .routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    def _startup():
        init_db()
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Static and frontend routing
    if os.path.isdir(DIST_DIR):
        if os.path.isdir(os.path.join(DIST_DIR, "assets")):
            app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
        if os.path.isdir(UPLOAD_DIR):
            app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

        @app.get("/")
        def serve_built_index():
            index_path = os.path.join(DIST_DIR, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "Built frontend not found. Run 'npm run build' in frontend/."}
    elif os.path.isdir(FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
        if os.path.isdir(UPLOAD_DIR):
            app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

        @app.get("/")
        def root_index():
            index_path = os.path.join(FRONTEND_DIR, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "Frontend not found. Build the app or add 'frontend/index.html'."}

    # API routers
    app.include_router(recipes_router)
    app.include_router(ask_router)
    app.include_router(health_router)

    return app
