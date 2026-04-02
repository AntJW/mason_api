from datetime import datetime

from firebase_admin import auth, firestore
import google.cloud.firestore
from flask import Blueprint, jsonify, request

from auth_decorator import login_required, new_user_auth
from google.cloud.firestore import SERVER_TIMESTAMP
from logger import logger
from google.cloud.firestore import DocumentReference
from models.user import User, UserStatus, UserRole
from models.company import Company, CompanyStatus

bp = Blueprint("users", __name__)


@bp.post("/users/me/properties")
@new_user_auth
def create_new_user_properties_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        user_record = auth.get_user(user_uid)
        request_data = request.get_json()
        firstName = request_data.get("firstName")
        lastName = request_data.get("lastName")
        companyName = request_data.get("companyName")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        # Create company
        company_doc_ref = firestore_client.collection("companies").document()
        company_id = company_doc_ref.id
        company_json = Company(id=company_id, name=companyName, ownerUserId=user_uid,
                               createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP", status=CompanyStatus.ACTIVE.value,
                               statusUpdatedAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                                   "id", "createdAt",
                                   "statusUpdatedAt",
                               })
        company_doc_ref.set({
            **company_json,
            "createdAt": SERVER_TIMESTAMP,
            "statusUpdatedAt": SERVER_TIMESTAMP
        })

        # outputs epoch time in milliseconds
        created_at_epoch_time = user_record.user_metadata.creation_timestamp
        # convert milliseconds to seconds before conversion
        created_at_timestamp = datetime.fromtimestamp(
            created_at_epoch_time / 1000.0)

        display_name = f"{firstName} {lastName}"

        # Update user in Firebase Authentication with display name
        auth.update_user(user_uid, display_name=display_name)

        # Create user details in Firestore
        user_json = User(id=user_uid, displayName=display_name, firstName=firstName,
                         lastName=lastName, email=user_record.email, companyId=company_id,
                         role=UserRole.ADMIN.value, status=UserStatus.ACTIVE.value, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP",
                         statusUpdatedAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                             "id", "createdAt",
                             "statusUpdatedAt",
                         })
        user_doc_ref = firestore_client.collection("users").document(user_uid)
        user_doc_ref.set({
            **user_json,
            "createdAt": created_at_timestamp,
            "statusUpdatedAt": created_at_timestamp
        })

        return jsonify(_get_user_json_for_response(user_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error creating user additional properties"}), 500


@bp.get("/users/me")
@login_required
def get_user_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        user_doc_ref = firestore_client.collection(
            "users").document(user_uid)
        return jsonify(_get_user_json_for_response(user_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error getting user"}), 500


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

        display_name = f"{firstName} {lastName}"
        auth.update_user(user_uid, display_name=display_name)

        user_doc_ref = firestore_client.collection(
            "users").document(user_uid)
        user_doc_ref.update({
            "firstName": firstName,
            "lastName": lastName,
            "statusUpdatedAt": SERVER_TIMESTAMP
        })

        return jsonify(_get_user_json_for_response(user_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating user"}), 500


@bp.put("/users/me/deactivate")
@login_required
def deactivate_user_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        user_doc_ref = firestore_client.collection(
            "users").document(user_uid)

        user_snap = user_doc_ref.get()
        company_id = user_snap.get("companyId")

        company_doc_ref = firestore_client.collection(
            "companies").document(company_id)
        company_snap = company_doc_ref.get()

        if user_uid == company_snap.get("ownerUserId"):
            company_doc_ref.update({
                "status": CompanyStatus.INACTIVE.value,
                "statusUpdatedAt": SERVER_TIMESTAMP
            })

        user_doc_ref.update({
            "status": UserStatus.INACTIVE.value,
            # timestamp used to track when the user was deactivated,
            # and determine when to schedule deletion (i.e. 30 days after deactivation)
            "statusUpdatedAt": SERVER_TIMESTAMP
        })

        # Deactivate the user in Firebase Authentication
        auth.update_user(user_uid, disabled=True)
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------------------------------------
# Users helper functions below this line
# ------------------------------------------------------------------------------------------------

def _get_user_json_for_response(user_doc_ref: DocumentReference) -> dict | None:
    try:
        user_json = user_doc_ref.get().to_dict()
        user_json["id"] = user_doc_ref.id
        user_json["createdAt"] = user_json.get("createdAt").isoformat()
        user_json["statusUpdatedAt"] = user_json.get(
            "statusUpdatedAt").isoformat()
        user_obj = User(**user_json)

        return user_obj.model_dump()
    except Exception as e:
        logger.error(f"error: _get_user_json_for_response failed: {e}")
        return None
