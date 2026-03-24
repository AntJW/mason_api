import json
import os
import re
import uuid
import datetime
import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
from google.cloud.firestore_v1.field_path import FieldPath
from qdrant_client import models
from auth_decorator import login_required, customer_owner_required
from clients.email_client import EmailClient
from clients.llm_client import LLMClient
from clients.vector_db_client import VectorDBClient
from logger import logger
from enum import Enum
from utility import (
    delete_tmp_file,
    delete_from_storage,
    save_file_to_tmp,
    upload_to_storage,
)

bp = Blueprint("documents", __name__)


# Confirmed QA
@bp.post("/customers/<customer_id>/documents/create")
@login_required
@customer_owner_required
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

        document_json = {
            "name": document_name,
            "text": text,
            "plainText": plain_text,
            "sourceTemplateId": source_template_id,
            "customerId": customer_id,
            "status": DocumentStatus.DRAFT.value,
            "createdAt": SERVER_TIMESTAMP
        }

        document_doc_ref.set(document_json)

        # Create default user signer
        document_doc_ref.collection("signers").document().set({
            "name": user.get("name"),
            "email": user.get("email"),
            "color": 4282145399,  # blue color
            "userId": user_uid
        })

        customer_doc_ref = firestore_client.collection(
            "customers").document(customer_id)
        customer_doc = customer_doc_ref.get()
        customer_json = customer_doc.to_dict()

        # Create default customer signer if email and firstName or lastName are set
        if customer_json.get("email") and (customer_json.get("firstName") or customer_json.get("lastName")):
            customer_signer_name = ""
            if customer_json.get("firstName") and customer_json.get("lastName"):
                customer_signer_name = f"{customer_json.get('firstName')} {customer_json.get('lastName')}"
            elif customer_json.get("firstName"):
                customer_signer_name = customer_json.get("firstName")
            else:
                customer_signer_name = customer_json.get("lastName")

            document_doc_ref.collection("signers").document().set({
                "name": customer_signer_name,
                "email": customer_json.get("email"),
                "color": 4283417505,  # aqua green color
                "customerId": customer_id
            })

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.get("/customers/<customer_id>/documents")
@login_required
@customer_owner_required
def get_documents(customer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        documents_docs = firestore_client.collection(
            "documents").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        documents_list = []
        for document_doc in documents_docs:
            document_json = get_merged_document(document_doc.reference)
            documents_list.append(document_json)
        return jsonify(documents_list), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.get("/customers/<customer_id>/documents/<document_id>")
@login_required
@customer_owner_required
def get_document(customer_id, document_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.put("/customers/<customer_id>/documents/<document_id>/update")
@login_required
@customer_owner_required
def update_document(customer_id, document_id):
    try:
        request_data = request.get_json()
        document_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        document_doc_ref.update({
            "name": document_name,
            "text": text,
            "plainText": plain_text,
        })

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.post("/customers/<customer_id>/documents/<document_id>/signers")
@login_required
@customer_owner_required
def create_document_signer(customer_id, document_id):
    try:
        request_data = request.get_json()
        signer_name = request_data.get("name")
        signer_email = request_data.get("email")
        signer_color = request_data.get("color")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        signers_docs = document_doc_ref.collection("signers").where(
            filter=FieldFilter("email", "==", signer_email)).get()

        if len(signers_docs) > 0:
            return jsonify({"error": "Signer already exists"}, 400)

        document_doc_ref.collection("signers").document().set({
            "name": signer_name,
            "email": signer_email,
            "color": signer_color,
        })

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.delete("/customers/<customer_id>/documents/<document_id>/signers/<signer_id>")
@login_required
@customer_owner_required
def delete_document_signer(customer_id, document_id, signer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        if not signer_doc_ref:
            return jsonify({"error": "Signer not found"}, 404)

        # Get signature boxes for signer
        signature_boxes_snapshots = document_doc_ref.collection("signatureBoxes").where(
            filter=FieldFilter("signerId", "==", signer_id)).get()

        batch = firestore_client.batch()
        signature_ids = set()
        for signature_box_snapshot in signature_boxes_snapshots:
            batch.delete(signature_box_snapshot.reference)
            data = signature_box_snapshot.to_dict() or {}
            sid = data.get("signatureId")
            if sid:
                signature_ids.add(sid)

        # # TODO: I think this is safe to remove in this endpoint. Signers should not have signatures / signature images
        # # during the execution of this endpoint. When document is signature request canceled,
        # # is when signatures images if they exists, should be deleted. Keep for reference, but I might relocate this to a different endpoint.
        # signature_image_storage_paths = []
        # if signature_ids:
        #     sig_refs = [
        #         document_doc_ref.collection("signatures").document(sid)
        #         for sid in signature_ids
        #     ]
        #     for sig_snap in firestore_client.get_all(sig_refs):
        #         if not sig_snap.exists:
        #             continue
        #         path = (sig_snap.to_dict() or {}).get(
        #             "signatureImageStoragePath")
        #         if path:
        #             signature_image_storage_paths.append(path)

        # # Delete signature images from storage
        # for signature_image_storage_path in signature_image_storage_paths:
        #     delete_from_storage(signature_image_storage_path)

        # Batch delete signature boxes
        batch.commit()

        # Delete signer
        signer_doc_ref.delete()

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.put("/customers/<customer_id>/documents/<document_id>/signers/<signer_id>")
@login_required
@customer_owner_required
def update_document_signer(customer_id, document_id, signer_id):
    try:
        request_data = request.get_json()
        signer_name = request_data.get("name")
        signer_email = request_data.get("email")
        signer_color = request_data.get("color")
        signer_userId = request_data.get("userId", None)
        signer_customerId = request_data.get("customerId", None)

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        if not signer_doc_ref:
            return jsonify({"error": "Signer not found"}, 404)

        signer_doc_ref.update({
            "name": signer_name,
            "email": signer_email,
            "color": signer_color,
            "userId": signer_userId,
            "customerId": signer_customerId
        })

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.put("/customers/<customer_id>/documents/<document_id>/signature-boxes")
@login_required
@customer_owner_required
def update_document_signature_boxes(customer_id, document_id):
    try:
        request_data = request.get_json()
        signature_boxes = request_data.get("signatureBoxes")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        signature_boxes_coll_ref = document_doc_ref.collection(
            "signatureBoxes")
        existing_signature_boxes_docs = signature_boxes_coll_ref.list_documents()

        batch = firestore_client.batch()
        for existing_signature_box_doc in existing_signature_boxes_docs:
            batch.delete(existing_signature_box_doc)
        batch.commit()

        for signature_box in signature_boxes:
            signature_boxes_coll_ref.document().set(signature_box)

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.post("/customers/<customer_id>/documents/<document_id>/signatures")
@login_required
@customer_owner_required
def create_document_signature(customer_id, document_id):
    try:
        request_form = request.form
        signer_id = request_form.get("signerId")
        signature_image_file = request.files["file"]

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        # Upload signature image to storage
        tmp_path = save_file_to_tmp(signature_image_file)
        signature_image_path = f"customers/{customer_id}/documents/{document_id}/signatures/{uuid.uuid4()}.png"
        upload_to_storage(tmp_path, signature_image_path,
                          content_type="image/png")
        delete_tmp_file(tmp_path)

        signature_doc_ref = document_doc_ref.collection(
            "signatures").document()
        signature_doc_ref.set({
            "signerId": signer_id,
            "signatureImageStoragePath": signature_image_path,
            "signedAt": SERVER_TIMESTAMP
        })

        # Get existing signature boxes for signer
        signature_box_coll_ref = document_doc_ref.collection("signatureBoxes")
        signature_boxes = signature_box_coll_ref.where(
            filter=FieldFilter("signerId", "==", signer_id)).get()

        # Update signature boxes with signature id
        for signature_box in signature_boxes:
            signature_box.reference.update({
                "signatureId": signature_doc_ref.id
            })

        matching_signer = document_doc_ref.collection(
            "signers").document(signer_id).get().to_dict()

        all_signature_boxes = signature_box_coll_ref.get()

        signature_boxes_with_signatures = [
            signature_box
            for signature_box in all_signature_boxes
            if signature_box.to_dict().get("signatureId")
        ]

        # Update document status if applicable
        if len(signature_boxes_with_signatures) == len(all_signature_boxes):
            document_doc_ref.update({
                "status": DocumentStatus.COMPLETED.value
            })
        elif matching_signer and matching_signer.get("userId") and document_doc_ref.get().to_dict().get("status") not in (DocumentStatus.SENT.value, DocumentStatus.COMPLETED.value):
            document_doc_ref.update({
                "status": DocumentStatus.PREPARED.value
            })

        # Clean up signers without matching signature boxes.
        remove_signers_without_matching_signature_boxes(document_doc_ref)

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.post("/customers/<customer_id>/documents/<document_id>/signatures/invitations")
@login_required
@customer_owner_required
def send_signature_invitations(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        if document_doc_ref.get().to_dict().get("status") == DocumentStatus.COMPLETED.value:
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        # Clean up signers without matching signature boxes.
        remove_signers_without_matching_signature_boxes(document_doc_ref)

        # Recipients list: all signers that are not the current_user / contractor.
        recipients = [signer for signer in document_doc_ref.collection(
            "signers").get() if signer.to_dict().get("userId", None) != user_uid]

        subject = "New document ready for you to sign"
        body = "Contractor has a document ready for you to sign. Please sign it electronically, by clicking the link below:"
        for recipient in recipients:
            signer_id = recipient.id
            recipient_email = recipient.to_dict().get("email")
            recipient_name = recipient.to_dict().get("name")

            response = EmailClient().send_simple_message(
                recipient_email, subject, body)
            # TODO: Add retry logic and error handling for email sending.

            document_doc_ref.collection("invitations").document().set({
                "signerId": signer_id,
                "email": recipient_email,
                "name": recipient_name,
                "documentId": document_id,
                # TODO: Generate token for signer to use to sign the document.
                "token": "TODO: Generate token",
                "status": InvitationStatus.SENT.value,
                "sentAt": SERVER_TIMESTAMP,
                "expiresAt": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14),
            })

        document_doc_ref.update({
            "status": DocumentStatus.SENT.value
        })

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.put("/customers/<customer_id>/documents/<document_id>/signatures/invitations/cancel")
@login_required
@customer_owner_required
def cancel_signature_invitations(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        if document_doc_ref.get().to_dict().get("status") == DocumentStatus.COMPLETED.value:
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        # Remove signatures, and their references from signature boxes
        remove_all_document_signatures(document_doc_ref)

        # update document status to draft
        document_doc_ref.update({
            "status": "draft"
        })

        batch = firestore_client.batch()

        # Recipients list: all signers that are not the current_user / contractor.
        recipients = set(signer for signer in document_doc_ref.collection(
            "signers").get() if signer.to_dict().get("userId", None) != user_uid)
        # send email to all signers to cancelling signature request
        for recipient in recipients:
            signer_id = recipient.id
            recipient_email = recipient.to_dict().get("email")
            recipient_name = recipient.to_dict().get("name")
            # TODO: Add retry logic and error handling for email sending.
            response = EmailClient().send_simple_message(recipient_email, "Signature Request Canceled",
                                                         "The signature request for the document has been canceled.")

            # Update invitations status to canceled
            invitation_doc_snapshots = document_doc_ref.collection("invitations").where(
                filter=FieldFilter("signerId", "==", signer_id)).where(
                filter=FieldFilter("documentId", "==", document_id)).get()

            for invitation_doc_snapshot in invitation_doc_snapshots:
                batch.update(invitation_doc_snapshot.reference, {
                    "status": InvitationStatus.CANCELED.value,
                    "canceledAt": SERVER_TIMESTAMP,
                    "canceledBy": user_uid
                })

        batch.commit()

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.put("/customers/<customer_id>/documents/<document_id>/signatures/me")
@login_required
@customer_owner_required
def remove_user_signature(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        existing_document_json = document_doc_ref.get().to_dict()

        status = existing_document_json.get("status")
        if status in (DocumentStatus.SENT.value, DocumentStatus.COMPLETED.value):
            return jsonify({"error": "Document cannot be modified in current status."}, 400)

        signer_doc_snapshots = document_doc_ref.collection("signers").where(
            filter=FieldFilter("userId", "==", user_uid)).get()
        if not signer_doc_snapshots:
            return jsonify({"error": "Signer not found"}, 404)

        signer = signer_doc_snapshots[0].to_dict()
        signer["id"] = signer_doc_snapshots[0].id

        signature_boxes_snapshots = document_doc_ref.collection("signatureBoxes").where(
            filter=FieldFilter("signerId", "==", signer.get("id"))).get()
        if not signature_boxes_snapshots:
            return jsonify({"error": "Signature boxes not found"}, 404)

        signature_ids_to_delete = set()
        for signature_box_snapshot in signature_boxes_snapshots:
            signature_box = signature_box_snapshot.to_dict()
            if signature_box.get("signatureId"):
                signature_ids_to_delete.add(signature_box.get("signatureId"))
                signature_box_snapshot.reference.update({
                    "signatureId": None
                })

        # Delete signature images from storage and update signature image storage path to None
        signatures_doc_refs = document_doc_ref.collection(
            "signatures").list_documents()
        for signature in signatures_doc_refs:
            if signature.id not in signature_ids_to_delete:
                continue
            data = signature.get().to_dict() or {}
            image_storage_path = data.get("signatureImageStoragePath")
            if image_storage_path:
                delete_from_storage(image_storage_path)
                signature.delete()

        document_doc_ref.update({
            "status": "draft"
        })

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/<document_id>/signatures/reminders")
@login_required
@customer_owner_required
def send_signature_reminders(customer_id, document_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        signer = request_data.get("signer")

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if document_doc_ref.get().to_dict().get("status") == DocumentStatus.COMPLETED.value:
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        existing_document_json = document_doc_ref.get().to_dict()

        response = EmailClient().send_simple_message(signer.get("email"), "Signature Reminder",
                                                     "You have a signature request for the document. Please sign it.")

        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


# Confirmed QA
@bp.delete("/customers/<customer_id>/documents/<document_id>/delete")
@login_required
@customer_owner_required
def delete_document(customer_id, document_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref:
            return jsonify({"error": "Document not found"}, 404)

        if document_doc_ref.get().to_dict().get("status") in (DocumentStatus.PREPARED.value, DocumentStatus.SENT.value, DocumentStatus.COMPLETED.value):
            return jsonify({"error": "Document not eligible for deletion due to it's current status."}, 400)

        document_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/customers/<customer_id>/documents/ai/generate")
@login_required
@customer_owner_required
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


# ------------------------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------------------------

DocumentStatus = Enum("DocumentStatus", [(
    "DRAFT", "draft"), ("PREPARED", "prepared"), ("SENT", "sent"), ("COMPLETED", "completed")])

InvitationStatus = Enum("InvitationStatus", [("SENT", "sent"), ("OPENED", "opened"), (
    "COMPLETED", "completed"), ("CANCELED", "canceled"), ("DECLINED", "declined")])

# Get merged document helper function


def get_merged_document(document_doc_ref):
    try:
        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_doc_ref.id
        document_json["createdAt"] = document_json.get(
            "createdAt").isoformat()

        signers_doc_ref = document_doc_ref.collection("signers").get()
        signers_json = []
        for signer_doc in signers_doc_ref:
            signer_json = signer_doc.to_dict()
            signer_json["id"] = signer_doc.id
            signers_json.append(signer_json)
        document_json["signers"] = signers_json

        signature_boxes_docs = document_doc_ref.collection(
            "signatureBoxes").get()
        signature_boxes_json = []
        for signature_box_doc in signature_boxes_docs:
            signature_box_json = signature_box_doc.to_dict()
            signature_box_json["id"] = signature_box_doc.id
            signature_boxes_json.append(signature_box_json)
        document_json["signatureBoxes"] = signature_boxes_json

        signatures_docs = document_doc_ref.collection("signatures").get()
        signatures_json = []
        for signature_doc in signatures_docs:
            signature_json = signature_doc.to_dict()
            signature_json["id"] = signature_doc.id
            signature_json["signedAt"] = signature_json.get(
                "signedAt").isoformat()
            signatures_json.append(signature_json)
        document_json["signatures"] = signatures_json

        return document_json
    except Exception as e:
        logger.error(f"error: {e}")
        return None


# Get document ref for customer helper function
def get_document_ref_for_customer(firestore_client, customer_id, document_id):
    try:
        document_ref = firestore_client.collection(
            "documents").document(document_id)
        document_snapshots = list(firestore_client.collection(
            "documents").where(filter=FieldFilter("__name__", "==", document_ref)).where(filter=FieldFilter("customerId", "==", customer_id)).limit(1).get())

        if not document_snapshots:
            return None

        return document_snapshots[0].reference
    except Exception as e:
        logger.error(f"error: {e}")
        return None


# Remove signers that don't have a matching signature box. This is to ensure
# that the signers list is up to date, once signatures are added.
def remove_signers_without_matching_signature_boxes(document_doc_ref):
    try:
        all_signature_boxes = document_doc_ref.collection(
            "signatureBoxes").get()
        all_signature_boxes_signer_ids = set(
            signature_box.to_dict().get("signerId")
            for signature_box in all_signature_boxes
        )
        for signer in document_doc_ref.collection("signers").list_documents():
            if signer.id not in all_signature_boxes_signer_ids:
                signer.delete()
    except Exception as e:
        logger.error(f"error: {e}")


def remove_all_document_signatures(document_doc_ref):
    signatures_doc_refs = document_doc_ref.collection(
        "signatures").list_documents()
    for signature in signatures_doc_refs:
        data = signature.get().to_dict() or {}
        image_storage_path = data.get("signatureImageStoragePath")
        if image_storage_path:
            delete_from_storage(image_storage_path)
            signature.delete()

    signatures_boxes_doc_refs = document_doc_ref.collection(
        "signatureBoxes").list_documents()

    for signature_box in signatures_boxes_doc_refs:
        signature_box.update({
            "signatureId": None
        })
