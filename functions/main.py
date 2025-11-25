# # For cost control, you can set the maximum number of containers that can be
# # running at the same time. This helps mitigate the impact of unexpected
# # traffic spikes by instead downgrading performance. This limit is a per-function
# # limit. You can override the limit for each function using the max_instances
# # parameter in the decorator, e.g. @https_fn.on_request(max_instances=5).
# set_global_options(max_instances=10)

from firebase_admin import initialize_app, firestore, auth
from firebase_functions import https_fn, options
from flask import Flask, request, jsonify
from auth_decorator import login_required, login_or_anonymous_required
import google.cloud.firestore
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
import os
# from utility import generate_invite_code, generate_default_profile_image, upload_to_storage, update_option_selection_count,\
#     enrich_members_data
from logger import logger
from datetime import datetime, UTC, timezone
from google.cloud.firestore_v1.field_path import FieldPath
from firebase_functions.params import PROJECT_ID
from utility import is_valid_email, convert_audio_sample_rate, create_tmp_file, upload_to_storage, delete_tmp_file
from enum import Enum
import uuid
import requests


initialize_app(
    options={"storageBucket": f"{PROJECT_ID.value}.firebasestorage.app"})
app = Flask(__name__)


# Expose Flask app as a single Cloud Function:
@https_fn.on_request(
    cors=options.CorsOptions(
        cors_origins=[origin.strip()
                      for origin in os.getenv("CORS_ORIGINS", "").split(",")],
        cors_methods=["get", "post", "put", "delete"],
    ),
    secrets=[],
    timeout_sec=120
)
def api(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()

# Create all functions below this line ===========================================================================================


class CustomerStatus(Enum):
    ACTIVE = "active"
    PROSPECT = "prospect"
    INACTIVE = "inactive"
    UNDEFINED = "undefined"


@app.get("/hello-world")
def get_hello_world():
    try:
        return jsonify({"message": "Hello World"}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/customer/create")
@login_required
def create_customer():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        email = request_data.get("email")
        if email != None and not is_valid_email(email):
            raise ValueError("Invalid email address")

        status = request_data["status"]
        if status not in [status.value for status in CustomerStatus]:
            raise ValueError("Invalid status")

        customer_json = {
            "displayName": request_data["displayName"].strip(),
            "firstName": request_data.get("firstName"),
            "lastName": request_data.get("lastName"),
            "email": email,
            "phone": request_data["phone"],
            "address": {
                "street": request_data.get("street"),
                "street2": request_data.get("street2"),
                "city": request_data.get("city"),
                "state": request_data.get("state"),
                "postalCode": request_data.get("postalCode"),
                "country": request_data.get("country"),
            },
            "status": request_data["status"].lower(),
            "userId": user_uid,
            "createdAt": SERVER_TIMESTAMP
        }

        firestore_client: google.cloud.firestore.Client = firestore.client()

        # creates a reference with an auto-generated ID
        customers_doc_ref = firestore_client.collection("customers").document()
        customer_id = customers_doc_ref.id  # get the auto-generated document ID

        customers_doc_ref.set(customer_json)

        customer_created_at_value = firestore_client.collection(
            "customers").document(customer_id).get().get("createdAt")
        customer_json["createdAt"] = customer_created_at_value.isoformat()

        customer_json["id"] = customer_id
        return jsonify(customer_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@app.post("/conversation/create")
# @login_required
def create_conversation():
    try:
        # user = request.user
        # user_uid = user.get("uid")
        request_form = request.form
        customer_id = request_form.get("customerId")

        # Receive audio file from request (multipart/form-data)
        if "audio" not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        audio_file = request.files["audio"]

        firestore_client: google.cloud.firestore.Client = firestore.client()

        # ✅ Upload audio file to storage
        # ✅ Create conversation document in Firestore
        # ✅ Convert audio file to be 16,000 Hz. Needed for pyAnnote speaker diarization.
        # Send audio file to transcribe API
        # Save raw transcription text to Firestore
        # Save whisper start and end timestamps to Firestore
        # Save pyannote speaker diarization start and end timestamps to Firestore
        # Overlap whisper and pyannote timestamps to get the start and end of each speaker's turn
        # Send transcription text to Ollama/LLM api for summary, action items, and header
        # Update conversation summary, action items, and header in Firestore

        local_tmp_file_path = create_tmp_file(audio_file)

        storage_file_path = f"audio/customers/{customer_id}/{uuid.uuid4()}.m4a"
        upload_to_storage(local_tmp_file_path, storage_file_path)

        conversation_doc_ref = firestore_client.collection(
            "conversations").document()
        conversation_id = conversation_doc_ref.id

        conversation_json = {
            "customerId": customer_id,
            "audioStoragePath": storage_file_path,
            "createdAt": SERVER_TIMESTAMP,
            "duration": 123,  # TODO: Calculate duration of audio file, or get it from client
            "header": None,
            "summary": None,  # raw summary text
            "summaryFormatted": None,  # formatted summary text
            "transcript": None,  # raw transcript text
            # list of transcript segments (start, end, text)
            "transcriptSegments": None,
            # list of speaker segments (start, end, speaker)
            "speakerSegments": None,
            # merged  transcript and speaker segments (start, end, text, speaker)
            "mergedSegments": None
        }

        conversation_doc_ref.set(conversation_json)

        transcribe_api_url = f"{os.getenv("TRANSCRIBE_API_URL")}/transcribe"
        transcribe_api_response = requests.post(
            transcribe_api_url, files={"file": audio_file})
        transcribe_api_response.raise_for_status()
        transcribe_api_data = transcribe_api_response.json()

        print("================================================",
              transcribe_api_data)

        wav_file = convert_audio_sample_rate(local_tmp_file_path)

        delete_tmp_file(local_tmp_file_path)

        return jsonify({"message": "Audio file received", "filename": audio_file.filename}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500
