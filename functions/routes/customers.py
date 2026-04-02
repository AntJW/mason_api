from enum import Enum

from firebase_admin import firestore
import google.cloud.firestore
from flask import Blueprint, jsonify, request

from auth_decorator import login_required, customer_permissions_required, company_permissions_required
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter, DocumentReference
from logger import logger
from utility import delete_from_storage, clean_string
from models.customer import Customer
from routes.documents import remove_all_document_signatures
from models.address import Address

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
@company_permissions_required
def get_customers():
    try:
        company_doc_ref = request.company_doc_ref

        firestore_client: google.cloud.firestore.Client = firestore.client()

        customer_snapshots = firestore_client.collection(
            "customers").where(filter=FieldFilter("companyId", "==", company_doc_ref.id)).get()

        customer_objs = []
        for customer_snap in customer_snapshots:
            customer_json = customer_snap.to_dict()
            customer_json["id"] = customer_snap.id
            customer_json["createdAt"] = customer_json.get(
                "createdAt").isoformat()
            customer_json["statusUpdatedAt"] = customer_json.get(
                "statusUpdatedAt").isoformat()
            customer_objs.append(Customer(**customer_json))

        return jsonify([customer_obj.model_dump()
                        for customer_obj in customer_objs]), 200
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
            "displayName": clean_string(request_data.get("displayName")),
            "firstName": clean_string(request_data.get("firstName")),
            "lastName": clean_string(request_data.get("lastName")),
            "email": clean_string(request_data.get("email")),
            "phone": clean_string(request_data.get("phone")),
            "address": {
                "street": clean_string(request_data.get("street")),
                "street2": request_data.get("street2"),
                "city": clean_string(request_data.get("city")),
                "state": clean_string(request_data.get("state")),
                "postalCode": clean_string(request_data.get("postalCode")),
                "country": clean_string(request_data.get("country")),
            },
            "createdByUser": user.get("uid"),
            "companyId": user.get("companyId"),
            "status": clean_string(request_data.get("status")).lower(),
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


@bp.put("/customers/<customer_id>")
@login_required
@customer_permissions_required
def update_customer(customer_id):
    try:
        customer_doc_ref = request.customer_doc_ref
        request_data = request.get_json()

        displayName = clean_string(request_data.get("displayName"))
        firstName = clean_string(request_data.get("firstName"))
        lastName = clean_string(request_data.get("lastName"))
        email = clean_string(request_data.get("email"))
        phone = clean_string(request_data.get("phone"))
        address = request_data.get("address")
        street = clean_string(address.get("street"))
        street2 = clean_string(address.get("street2"))
        city = clean_string(address.get("city"))
        state = clean_string(address.get("state"))
        postalCode = clean_string(address.get("postalCode"))
        country = clean_string(address.get("country"))
        status = clean_string(request_data.get("status")).lower()

        clean_address_json = Address(
            street=street,
            street2=street2,
            city=city,
            state=state,
            postalCode=postalCode,
            country=country
        ).model_dump()

        customer_doc_ref.update({
            "displayName": displayName,
            "firstName": firstName,
            "lastName": lastName,
            "email": email,
            "phone": phone,
            "address": clean_address_json,
        })

        if status != customer_doc_ref.get().get("status"):
            customer_doc_ref.update({
                "status": status,
                "statusUpdatedAt": SERVER_TIMESTAMP
            })

        return jsonify(_get_customer_json_for_response(customer_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating customer"}), 500


@bp.delete("/customers/<customer_id>")
@login_required
@customer_permissions_required
def delete_customer(customer_id):
    try:
        customer_doc_ref = request.customer_doc_ref

        firestore_client: google.cloud.firestore.Client = firestore.client()

        conversations_snapshots = firestore_client.collection(
            "conversations").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        for conversation_snap in conversations_snapshots:
            conversation_audio_storage_path = conversation_snap.get(
                "audioStoragePath")
            delete_from_storage(conversation_audio_storage_path)
            conversation_snap.reference.delete()

        documents_snapshots = firestore_client.collection(
            "documents").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        for document_snap in documents_snapshots:
            remove_all_document_signatures(document_snap.reference)
            document_snap.reference.delete()

        customer_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: delete_customer: {e}")
        return jsonify({"error": "Error deleting customer"}), 500


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
