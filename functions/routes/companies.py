import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter

from auth_decorator import login_required
from logger import logger

bp = Blueprint("companies", __name__)


@bp.post("/companies/create")
@login_required
def create_company():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        company_name = request_data.get("name")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        company_doc_ref = firestore_client.collection(
            "companies").document()
        company_id = company_doc_ref.id

        company_json = {
            "name": company_name,
            "createdAt": SERVER_TIMESTAMP,
            "adminUserId": user_uid
        }

        company_doc_ref.set(company_json)

        company_doc = company_doc_ref.get(field_paths=[
            "name", "createdAt", "adminUserId"])
        company_json = company_doc.to_dict()
        company_json["id"] = company_id
        company_json["createdAt"] = company_doc.get(
            "createdAt").isoformat()

        return jsonify(company_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/companies/me")
@login_required
def get_company_me():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        company_docs = firestore_client.collection(
            "companies").where(filter=FieldFilter("adminUserId", "==", user_uid)).get()

        company_json = {}
        for company_doc in company_docs:
            company_json = company_doc.to_dict()
            company_json["id"] = company_doc.id
            company_json["createdAt"] = company_doc.get(
                "createdAt").isoformat()
            break

        if not company_json:
            return jsonify({}), 404

        return jsonify(company_json), 200
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
        company_admin_user_id = request_data.get("adminUserId")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        company_doc_ref = firestore_client.collection(
            "companies").document(company_id)

        company_doc_ref.update({
            "name": company_name,
        })

        company_doc = company_doc_ref.get(field_paths=[
            "name", "adminUserId", "createdAt"])
        company_json = company_doc.to_dict()
        company_json["id"] = company_id
        company_json["createdAt"] = company_doc.get(
            "createdAt").isoformat()
        return jsonify(company_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500

