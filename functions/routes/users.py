from datetime import datetime

from firebase_admin import auth, firestore
import google.cloud.firestore
from flask import Blueprint, jsonify, request

from auth_decorator import login_required
from google.cloud.firestore import SERVER_TIMESTAMP
from logger import logger

bp = Blueprint("users", __name__)


@bp.post("/users/me/properties")
@login_required
def create_new_user_properties_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        user_record = auth.get_user(user_uid)
        request_data = request.get_json()
        firstName = request_data.get("firstName")
        lastName = request_data.get("lastName")
        firestore_client: google.cloud.firestore.Client = firestore.client()

        # outputs epoch time in milliseconds
        created_at_epoch_time = user_record.user_metadata.creation_timestamp
        # convert milliseconds to seconds before conversion
        created_at_timestamp = datetime.fromtimestamp(
            created_at_epoch_time / 1000.0)

        display_name = f"{firstName} {lastName}"

        auth.update_user(user_uid, display_name=display_name)

        firestore_client.collection("users").document(user_uid).set(
            {
                "email": user_record.email,
                "displayName": display_name,
                "firstName": firstName,
                "lastName": lastName,
                "createdAt": created_at_timestamp
            })

        updated_user_doc = firestore_client.collection(
            "users").document(user_uid).get()
        updated_user_json = updated_user_doc.to_dict()
        updated_user_json["createdAt"] = updated_user_doc.get(
            "createdAt").isoformat()
        updated_user_json["id"] = user_uid

        return jsonify(updated_user_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/users/me")
@login_required
def get_user_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        user_doc = firestore_client.collection(
            "users").document(user_uid).get()
        user_json = user_doc.to_dict()
        user_json["createdAt"] = user_doc.get("createdAt").isoformat()
        user_json["id"] = user_uid
        return jsonify(user_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/users/me")
@login_required
def update_user_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        firstName = request_data.get("firstName")
        lastName = request_data.get("lastName")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        user_doc = firestore_client.collection(
            "users").document(user_uid)
        user_doc.update({
            "firstName": firstName,
            "lastName": lastName
        })

        display_name = f"{firstName} {lastName}"
        auth.update_user(user_uid, display_name=display_name)

        user_snapshot = user_doc.get(field_paths=["displayName", "email",
                                                  "firstName", "lastName", "createdAt"])
        user_json = user_snapshot.to_dict()
        user_json["createdAt"] = user_json.get("createdAt").isoformat()
        user_json["id"] = user_doc.id
        return jsonify(user_json), 200
    except Exception as e:
        logger.error(f"error: {e}")

@bp.put("/users/me/deactivate")
@login_required
def deactivate_user_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        user_doc_ref = firestore_client.collection(
            "users").document(user_uid)

        user_doc_ref.update({
            "deactivated": True,
            # timestamp used to track when the user was deactivated, and determine when to schedule deletion (i.e. 30 days after deactivation)
            "deactivatedAt": SERVER_TIMESTAMP
        })
        # Deactivate the user in Firebase Authentication
        auth.update_user(user_uid, disabled=True)
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500
