from enum import Enum

from firebase_admin import firestore
import google.cloud.firestore
from flask import Blueprint, jsonify, request

from auth_decorator import login_required, customer_permissions_required, company_permissions_required
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter, DocumentReference
from logger import logger
from utility import is_valid_email, delete_from_storage
from models.customer import Customer


bp = Blueprint("customers", __name__)


class CustomerStatus(Enum):
    ACTIVE = "active"
    PROSPECT = "prospect"
    INACTIVE = "inactive"
    UNDEFINED = "undefined"


@bp.get("/customers/<customer_id>")
@login_required
@customer_permissions_required
def get_customer(customer_id):
    try:
        return jsonify(_get_customer_json_for_response(request.customer_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/customers")
@login_required
def get_customers():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        customer_docs = firestore_client.collection(
            "customers").where(filter=FieldFilter("userId", "==", user_uid)).get()

        customers_list = []
        for customer_doc in customer_docs:
            customer_json = customer_doc.to_dict()
            customers_list.append({
                "id": customer_doc.id,
                "displayName": customer_json.get("displayName"),
                "firstName": customer_json.get("firstName"),
                "lastName": customer_json.get("lastName"),
                "email": customer_json.get("email"),
                "phone": customer_json.get("phone"),
                "address": customer_json.get("address"),
                "userId": customer_json.get("userId"),
                "status": customer_json.get("status"),
                "createdAt": customer_json.get("createdAt").isoformat()
            })

        return jsonify(customers_list), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers")
@login_required
@company_permissions_required
def create_customer():
    try:
        user = request.user
        request_data = request.get_json()

        firestore_client: google.cloud.firestore.Client = firestore.client()

        customers_doc_ref = firestore_client.collection("customers").document()

        customer_json = {
            "id": customers_doc_ref.id,
            "displayName": request_data.get("displayName").strip(),
            "firstName": request_data.get("firstName"),
            "lastName": request_data.get("lastName"),
            "email": request_data.get("email"),
            "phone": request_data.get("phone"),
            "address": {
                "street": request_data.get("street"),
                "street2": request_data.get("street2"),
                "city": request_data.get("city"),
                "state": request_data.get("state"),
                "postalCode": request_data.get("postalCode"),
                "country": request_data.get("country"),
            },
            "createdByUser": user.get("uid"),
            "companyId": user.get("companyId"),
            "status": request_data.get("status").strip().lower(),
            "statusUpdatedAt": "PLACEHOLDER_FOR_SERVER_TIMESTAMP",
            "createdAt": "PLACEHOLDER_FOR_SERVER_TIMESTAMP"
        }

        customer_json = Customer(**customer_json).model_dump(exclude={
            "id", "createdAt", "statusUpdatedAt",
        })

        customers_doc_ref.set(
            {**customer_json, "createdAt": SERVER_TIMESTAMP, "statusUpdatedAt": SERVER_TIMESTAMP})

        return jsonify(_get_customer_json_for_response(customers_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error creating customer"}), 500


@bp.put("/customers/<customer_id>/update")
@login_required
def update_customer(customer_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()

        displayName = request_data.get("displayName")
        firstName = request_data.get("firstName")
        lastName = request_data.get("lastName")
        email = request_data.get("email")
        phone = request_data.get("phone")
        address = request_data.get("address")
        street = address.get("street")
        street2 = address.get("street2")
        city = address.get("city")
        state = address.get("state")
        postalCode = address.get("postalCode")
        country = address.get("country")
        status = request_data.get("status")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        customer_doc_ref = firestore_client.collection(
            "customers").document(customer_id)

        customer_doc_ref.update({
            "displayName": displayName,
            "firstName": firstName,
            "lastName": lastName,
            "email": email,
            "phone": phone,
            "address": address,
            "status": status
        })
        customer_doc = customer_doc_ref.get(field_paths=[
                                            "displayName", "firstName", "lastName", "email", "phone", "address", "status", "userId", "createdAt"])
        customer_json = customer_doc.to_dict()
        customer_json["id"] = customer_doc_ref.id
        customer_json["createdAt"] = customer_doc.get("createdAt").isoformat()
        return jsonify(customer_json), 200
    except Exception as e:
        logger.error(f"error: {e}")


@bp.delete("/customers/<customer_id>/delete")
@login_required
def delete_customer(customer_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        conversations_docs = firestore_client.collection(
            "conversations").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        for conversation_doc in conversations_docs:
            conversation_audio_storage_path = conversation_doc.get(
                "audioStoragePath")
            delete_from_storage(conversation_audio_storage_path)
            conversation_doc.delete()

        customer_doc_ref = firestore_client.collection(
            "customers").document(customer_id)

        customer_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------------------------------------
# Customers helper functions below this line
# ------------------------------------------------------------------------------------------------

def _get_customer_json_for_response(customer_doc_ref: DocumentReference) -> dict | None:
    try:
        customer_json = customer_doc_ref.get().to_dict()
        customer_json["id"] = customer_doc_ref.id
        customer_json["createdAt"] = customer_json.get("createdAt").isoformat()
        customer_json["statusUpdatedAt"] = customer_json.get(
            "statusUpdatedAt").isoformat()

        return Customer(**customer_json).model_dump()
    except Exception as e:
        logger.error(f"error: _get_customer_json_for_response failed: {e}")
        return None
