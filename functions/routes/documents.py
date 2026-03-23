import json
import os
import re
import uuid

import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
from qdrant_client import models

from auth_decorator import login_required
from clients.email_client import EmailClient
from clients.llm_client import LLMClient
from clients.vector_db_client import VectorDBClient
from logger import logger
from utility import (
    delete_tmp_file,
    delete_from_storage,
    save_file_to_tmp,
    upload_to_storage,
)

bp = Blueprint("documents", __name__)


@bp.post("/customers/<customer_id>/documents/create")
@login_required
def create_document(customer_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        document_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")
        source_template_id = request_data.get("sourceTemplateId", None)

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document()
        document_id = document_doc_ref.id

        document_json = {
            "name": document_name,
            "text": text,
            "plainText": plain_text,
            "sourceTemplateId": source_template_id,
            "customerId": customer_id,
            "createdAt": SERVER_TIMESTAMP
        }

        document_doc_ref.set(document_json)

        document_doc = document_doc_ref.get(field_paths=[
            "name", "text", "plainText", "sourceTemplateId", "customerId", "createdAt"])
        document_json = document_doc.to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_doc.get(
            "createdAt").isoformat()

        return jsonify(document_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/customers/<customer_id>/documents")
@login_required
def get_documents(customer_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        documents_docs = firestore_client.collection(
            "documents").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        documents_list = []
        for document_doc in documents_docs:
            document_json = document_doc.to_dict()
            documents_list.append({
                "id": document_doc.id,
                "name": document_json.get("name"),
                "text": document_json.get("text"),
                "plainText": document_json.get("plainText"),
                "customerId": document_json.get("customerId"),
                "sourceTemplateId": document_json.get("sourceTemplateId", None),
                "createdAt": document_json.get("createdAt").isoformat(),
                "status": document_json.get("status")
            })
        return jsonify(documents_list), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/customers/<customer_id>/documents/<document_id>")
@login_required
def get_document(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)
        document_doc = document_doc_ref.get(field_paths=[
            "name", "text", "plainText", "sourceTemplateId", "signers", "signatureBoxes", "customerId", "createdAt", "status"])
        document_json = document_doc.to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_doc.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/customers/<customer_id>/documents/<document_id>/update")
@login_required
def update_document(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        document_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")
        source_template_id = request_data.get("sourceTemplateId", None)

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)
        document_doc_ref.update({
            "name": document_name,
            "text": text,
            "plainText": plain_text,
            "sourceTemplateId": source_template_id
        })

        document_doc = document_doc_ref.get(field_paths=[
            "name", "text", "plainText", "sourceTemplateId", "signers", "signatureBoxes", "customerId", "createdAt", "status"])
        document_json = document_doc.to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_doc.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/customers/<customer_id>/documents/<document_id>/signers")
@login_required
def update_document_signers(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        signers = request_data.get("signers")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)
        document_doc_ref.update({
            "signers": signers
        })

        document_doc = document_doc_ref.get(field_paths=[
            "name", "text", "plainText", "sourceTemplateId", "signers", "signatureBoxes", "customerId", "createdAt", "status"])
        document_json = document_doc.to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_doc.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/customers/<customer_id>/documents/<document_id>/signature-boxes")
@login_required
def update_document_signature_boxes(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        signature_boxes = request_data.get("signatureBoxes")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)
        document_doc_ref.update({
            "signatureBoxes": signature_boxes
        })

        document_doc = document_doc_ref.get(field_paths=[
            "name", "text", "plainText", "sourceTemplateId", "signers", "signatureBoxes", "customerId", "createdAt", "status"])
        document_json = document_doc.to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_doc.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/<document_id>/signatures")
@login_required
def create_document_signature(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_form = request.form
        signer_id = request_form.get("signerId")
        signature_image_file = request.files["file"]

        firestore_client: google.cloud.firestore.Client = firestore.client()

        # Upload signature image to storage
        tmp_path = save_file_to_tmp(signature_image_file)
        signature_image_path = f"customers/{customer_id}/documents/{document_id}/signatures/{uuid.uuid4()}.png"
        upload_to_storage(tmp_path, signature_image_path,
                          content_type="image/png")
        delete_tmp_file(tmp_path)

        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        # Get existing signature image url for specific signer if exists, and delete it from storage if exists
        existing_document_json = document_doc_ref.get().to_dict()
        signature_boxes = existing_document_json.get("signatureBoxes", [])
        for signature_box in signature_boxes:
            if signature_box.get("signerId") == signer_id and signature_box.get("signatureImageStoragePath"):
                try:
                    delete_from_storage(signature_box.get(
                        "signatureImageStoragePath"))
                except Exception as e:
                    logger.error(f"error: {e}")

                break

        # Update document signatures in firestore (signatureImageStoragePath) for specific signer
        for signature_box in signature_boxes:
            if signature_box.get("signerId") == signer_id:
                signature_box["signatureImageStoragePath"] = signature_image_path

        document_doc_ref.update({
            "signatureBoxes": signature_boxes
        })

        updated_document_json = document_doc_ref.get().to_dict()

        signers = updated_document_json.get("signers") or []
        matching_signer = next(
            (s for s in signers if s.get("id") == signer_id), None)

        # How many signature boxes have the signature image path
        signature_boxes = updated_document_json.get("signatureBoxes") or []
        signature_boxes_with_image_path = [
            signature_box for signature_box in signature_boxes if signature_box.get("signatureImageStoragePath")
        ]
        if len(signature_boxes_with_image_path) == len(signature_boxes):
            document_doc_ref.update({
                "status": "complete"
            })
        elif (
            matching_signer
            and matching_signer.get("userId")
            and updated_document_json.get("status") != "sent"
            and updated_document_json.get("status") != "complete"
        ):
            document_doc_ref.update({
                "status": "prepared"
            })

        # Remove signers that don't have a matching signature box. This is to ensure
        # that the signers list is up to date, once signatures are added.
        signers = updated_document_json.get("signers") or []
        signature_boxes = updated_document_json.get("signatureBoxes") or []
        if len(signers) != len(signature_boxes):
            signature_boxes_signer_ids = [signature_box.get(
                "signerId") for signature_box in signature_boxes]
            signers = [signer for signer in signers if signer.get(
                "id") in signature_boxes_signer_ids]
            document_doc_ref.update({
                "signers": signers
            })

        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_json.get(
            "createdAt").isoformat()

        return jsonify(document_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/<document_id>/signatures/invitations")
@login_required
def send_signature_invitations(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        subject = request_data.get("subject")
        body = request_data.get("body")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        if document_doc_ref.get().to_dict().get("status") == "complete":
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        existing_document_json = document_doc_ref.get().to_dict()

        signature_boxes_signer_ids = [signature_box.get(
            "signerId") for signature_box in existing_document_json.get("signatureBoxes")]
        signers = existing_document_json.get("signers")

        recipients = [signer.get("email") for signer in signers if signer.get(
            "id") in signature_boxes_signer_ids]

        for recipient in recipients:
            response = EmailClient().send_simple_message(recipient, subject, body)

        document_doc_ref.update({
            "status": "sent"
        })

        # Remove signers that don't have a matching signature box. This is to ensure
        # that the signers list is up to date, once invitations are sent.
        signers = existing_document_json.get("signers") or []
        signature_boxes = existing_document_json.get("signatureBoxes") or []
        if len(signers) != len(signature_boxes):
            signature_boxes_signer_ids = [signature_box.get(
                "signerId") for signature_box in signature_boxes]
            signers = [signer for signer in signers if signer.get(
                "id") in signature_boxes_signer_ids]
            document_doc_ref.update({
                "signers": signers
            })

        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_json.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/customers/<customer_id>/documents/<document_id>/signatures/invitations/cancel")
@login_required
def cancel_signature_invitations(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        existing_document_json = document_doc_ref.get().to_dict()
        updated_signature_boxes = []
        for signature_box in existing_document_json.get("signatureBoxes") or []:

            # delete signature image from storage if exists
            if signature_box.get("signatureImageStoragePath"):
                delete_from_storage(signature_box.get(
                    "signatureImageStoragePath"))

                signature_box['signatureImageStoragePath'] = None

            updated_signature_boxes.append(signature_box)

        # update document status to draft
        document_doc_ref.update({
            "signatureBoxes": updated_signature_boxes,
            "status": "draft"
        })

        # send email to all signers to cancelling signature request
        signers = existing_document_json.get("signers") or []
        recipients = [signer.get("email") for signer in signers]
        for recipient in recipients:
            response = EmailClient().send_simple_message(recipient, "Signature Request Cancelled",
                                                         "The signature request for the document has been cancelled.")

        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_json.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/customers/<customer_id>/documents/<document_id>/signatures/me")
@login_required
def remove_user_signature(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        existing_document_json = document_doc_ref.get().to_dict()

        status = existing_document_json.get("status")
        if status != "prepared":
            return jsonify({"error": "Document cannot be modified in current status."}, 400)

        signer = next((s for s in existing_document_json.get(
            "signers") or [] if s.get("userId") == user_uid), None)

        signature_boxes = existing_document_json.get("signatureBoxes") or []
        updated_signature_boxes = []
        for signature_box in signature_boxes:
            if signature_box.get("signerId") == signer.get("id") and signature_box.get("signatureImageStoragePath") is not None:
                delete_from_storage(signature_box.get(
                    "signatureImageStoragePath"))
                signature_box['signatureImageStoragePath'] = None
            updated_signature_boxes.append(signature_box)

        document_doc_ref.update({
            "signatureBoxes": updated_signature_boxes,
            "status": "draft"
        })

        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_id
        document_json["createdAt"] = document_json.get(
            "createdAt").isoformat()
        return jsonify(document_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/<document_id>/signatures/reminders")
@login_required
def send_signature_reminders(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        signer = request_data.get("signer")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        if document_doc_ref.get().to_dict().get("status") == "complete":
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        existing_document_json = document_doc_ref.get().to_dict()

        response = EmailClient().send_simple_message(signer.get("email"), "Signature Reminder",
                                                     "You have a signature request for the document. Please sign it.")

        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.delete("/customers/<customer_id>/documents/<document_id>/delete")
@login_required
def delete_document(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)
        document_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/ai/generate")
@login_required
def ai_generate_document_text(customer_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        prompt = request_data.get("prompt")
        current_text = request_data.get("currentText")

        vector_db_client = VectorDBClient()

        hits = vector_db_client.query(
            query=prompt, limit=5, query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="userId", match=models.MatchValue(value=user_uid)),
                    models.FieldCondition(
                        key="customerId", match=models.MatchValue(value=customer_id))
                ]
            ))

        past_conversations = ""
        for hit in hits:
            past_conversations += f"Transcript: {hit.payload.get('content')}\n\n"

        customer_doc_ref = firestore.client().collection("customers").document(
            customer_id)
        customer_doc = customer_doc_ref.get(
            field_paths=["displayName", "firstName", "lastName"])
        customer_data = customer_doc.to_dict() if customer_doc.exists else {}
        customer_name = (
            f"{customer_data.get('firstName', '')} {customer_data.get('lastName', '')}".strip(
            )
            or customer_data.get("displayName")
        )

        current_delta_str = json.dumps(current_text)

        system_parts = [
            "You are a document generation assistant. The user will send a prompt describing what they want in the document.",
            "The current document and your response both use Quill Delta JSON format: {\"ops\": [{\"insert\": \"text\", \"attributes\": {...}}, ...]}. Preserve all existing formatting attributes (bold, italic, header, alignment, color, etc.) unless the user explicitly asks to change them.",
            "",
            "Important formatting rules:",
            "1. Block-level attributes (header, list, align, indent, blockquote, code-block, direction) MUST be applied to the newline character (\"\\n\") that terminates the line, NOT to the text insert.",
            "2. Text formatting attributes (bold, italic, underline, strike, code, color, background, link) MUST be applied to the text insert operations.",
            "3. Never apply \"header\" to a text insert. It must only appear on a newline insert.",
            "4. Every block must end with a newline insert.",
            "",
            "Important: If the user asks to modify, edit, revise, or change the current document (e.g. 'fix the tone', 'add a section about X', 'rewrite paragraph 2'), apply those changes to the existing content and return the full modified document as a Delta. Do not return only the changed portion—always return the complete document. If there is no existing content or the user asks for a new document from scratch, generate accordingly.",
            "",
            "---",
            "Current document in Quill Delta JSON (modify this when the user requests edits; otherwise extend or replace as their prompt indicates):",
            current_delta_str or "(No existing content)",
            "",
            "---",
            "Customer this document is for:",
            customer_name,
        ]
        if past_conversations:
            system_parts.extend([
                "",
                "---",
                "Relevant past conversations with this customer (use for context only):",
                past_conversations.strip(),
            ])
        system_parts.extend(["", "---", "Output valid JSON only."])
        system_message = "\n".join(system_parts)

        llm_client = LLMClient().client

        response = llm_client.messages.create(
            model=os.getenv("LLM_MODEL"),
            max_tokens=4096,
            system=system_message,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text

        # Remove ```json fences
        cleaned_response_text = re.sub(
            r"```json|```", "", response_text).strip()

        document_delta = json.loads(cleaned_response_text)

        return jsonify(document_delta), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500
