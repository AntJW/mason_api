from enum import Enum

from firebase_admin import firestore
import google.cloud.firestore
from flask import Blueprint, jsonify, request

from auth_decorator import login_required
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
from logger import logger
from utility import is_valid_email, delete_from_storage

bp = Blueprint("customers", __name__)


class CustomerStatus(Enum):
    ACTIVE = "active"
    PROSPECT = "prospect"
    INACTIVE = "inactive"
    UNDEFINED = "undefined"


@bp.get("/customers/<customer_id>")
@login_required
def get_customer(customer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        customer_doc_ref = firestore_client.collection(
            "customers").document(customer_id)
        customer_doc = customer_doc_ref.get(field_paths=[
                                            "displayName", "firstName", "lastName", "email", "phone", "address", "status", "userId", "createdAt"])
        customer_json = customer_doc.to_dict()
        customer_json["createdAt"] = customer_doc.get(
            "createdAt").isoformat()
        customer_json["id"] = customer_doc_ref.id
        return jsonify(customer_json), 200
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


@bp.post("/customer/create")
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
        return jsonify(customer_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


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
