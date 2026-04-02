import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from auth_decorator import login_required, company_permissions_required, company_owner_required
from logger import logger
from google.cloud.firestore import DocumentReference
from models.company import Company

bp = Blueprint("companies", __name__)


@bp.get("/companies/<company_id>")
@login_required
@company_permissions_required
def get_company(company_id):
    try:
        return jsonify(_get_company_json_for_response(request.company_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error getting company"}), 500


@bp.put("/companies/<company_id>/name")
@login_required
@company_owner_required
def update_company_name(company_id):
    try:
        request_data = request.get_json()
        company_name = request_data.get("name")

        request.company_doc_ref.update({
            "name": company_name,
        })

        return jsonify(_get_company_json_for_response(request.company_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating company"}), 500


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
