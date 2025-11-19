# from firebase_functions import https_fn
# from firebase_functions.options import set_global_options
# from firebase_admin import initialize_app

# # For cost control, you can set the maximum number of containers that can be
# # running at the same time. This helps mitigate the impact of unexpected
# # traffic spikes by instead downgrading performance. This limit is a per-function
# # limit. You can override the limit for each function using the max_instances
# # parameter in the decorator, e.g. @https_fn.on_request(max_instances=5).
# set_global_options(max_instances=10)

# initialize_app()


# @https_fn.on_request()
# def on_request_example(req: https_fn.Request) -> https_fn.Response:
#     return https_fn.Response("Hello world!")




from firebase_admin import initialize_app, firestore, auth
from firebase_functions import https_fn, options
from flask import Flask, request, jsonify
# from auth_decorator import login_required, group_admin_login_required,\
#     admin_login_required, login_or_anonymous_required, group_member_login_required
import google.cloud.firestore
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
import os
# from utility import generate_invite_code, generate_default_profile_image, upload_to_storage, update_option_selection_count,\
#     enrich_members_data
from logger import logger
from datetime import datetime, UTC, timezone
from google.cloud.firestore_v1.field_path import FieldPath
from firebase_functions.params import PROJECT_ID


initialize_app(options={"storageBucket": f"{PROJECT_ID.value}.firebasestorage.app"})
app = Flask(__name__)


# Expose Flask app as a single Cloud Function:
@https_fn.on_request(
        cors=options.CorsOptions(
        cors_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",")],
        cors_methods=["get", "post", "put", "delete"],
    ),
    secrets=[],
    timeout_sec=120
)
def api(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()

# Create all functions below this line ===========================================================================================

@app.get("/hello-world")
def get_hello_world():
    try:
        return jsonify({"message": "Hello World"}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500
