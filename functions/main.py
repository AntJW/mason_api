import os

from firebase_admin import initialize_app
from firebase_functions import https_fn, options
from firebase_functions.params import PROJECT_ID
from flask import Flask

from routes import register_routes

initialize_app(
    options={"storageBucket": f"{PROJECT_ID.value}.firebasestorage.app"})
app = Flask(__name__)
register_routes(app)


@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=[origin.strip()
                      for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
        cors_methods=["get", "post", "put", "delete"],
    ),
    secrets=[],
    timeout_sec=540
)
def api(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()
