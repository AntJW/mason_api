import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter

from auth_decorator import login_required
from logger import logger
from google.cloud.firestore import DocumentReference
from models.company import Company

bp = Blueprint("companies", __name__)


@bp.get("/companies/me")
@login_required
def get_company_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        company_snapshots = firestore_client.collection(
            "companies").where(filter=FieldFilter("ownerUserId", "==", user_uid)).get()

        if not company_snapshots:
            raise Exception("Company not found")

        company_doc_ref = company_snapshots[0].reference

        return jsonify(_get_company_json_for_response(company_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/companies/me")
@login_required
def update_company_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        company_id = request_data.get("id")
        company_name = request_data.get("name")
        company_admin_user_id = request_data.get("ownerUserId")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        company_doc_ref = firestore_client.collection(
            "companies").document(company_id)

        company_doc_ref.update({
            "name": company_name,
        })

        return jsonify(_get_company_json_for_response(company_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------------------------------------
# Companies helper functions below this line
# ------------------------------------------------------------------------------------------------

def _get_company_json_for_response(company_doc_ref: DocumentReference) -> dict | None:
    try:
        company_json = company_doc_ref.get().to_dict()
        company_json["id"] = company_doc_ref.id
        company_json["createdAt"] = company_json.get("createdAt").isoformat()
        company_json["statusUpdatedAt"] = company_json.get(
            "statusUpdatedAt").isoformat()
        company_obj = Company(**company_json)
        return company_obj.model_dump()
    except Exception as e:
        logger.error(f"error: _get_company_json_for_response failed: {e}")
        return None
