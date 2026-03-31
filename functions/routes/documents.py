import json
import os
import re
import uuid
import datetime
import secrets
import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter
from google.cloud.firestore_v1.field_path import FieldPath
from qdrant_client import models
from auth_decorator import (
    login_required, customer_owner_required, signing_token_required)
from clients.email_client import EmailClient
from clients.llm_client import LLMClient
from clients.vector_db_client import VectorDBClient
from logger import logger
from enum import Enum
from google.cloud.firestore import And, Or, Increment, DocumentReference
from utility import (
    datetime_iso_or_none,
    delete_tmp_file,
    delete_from_storage,
    save_file_to_tmp,
    upload_to_storage,
)
from models.invitation import InvitationStatus, Invitation
from models.audit_log import AuditLogAction, AuditLogActorRole, AuditLogTargetType, AuditLog
from models.signing_document import SigningDocument
from models.document import DocumentStatus
from models.signature import Signature
from models.document import Document
from models.signer import Signer
from models.signature_box import SignatureBox

bp = Blueprint("documents", __name__)


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

        document_json = Document(id=document_doc_ref.id, name=document_name, text=text, plainText=plain_text,
                                 sourceTemplateId=source_template_id, customerId=customer_id, status=DocumentStatus.DRAFT, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                                     "id", "createdAt",
                                 })
        document_doc_ref.set({
            **document_json,
            "createdAt": SERVER_TIMESTAMP
        })

        # Create default user signer
        user_signer_ref = document_doc_ref.collection("signers").document()
        user_signer_json = Signer(id=user_signer_ref.id, name=user.get(
            "name"), email=user.get("email"), color=4282145399, userId=user_uid, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                "id", "createdAt",
            })
        user_signer_ref.set(
            {**user_signer_json, "createdAt": SERVER_TIMESTAMP})

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

            customer_signer_ref = document_doc_ref.collection(
                "signers").document()
            customer_signer_json = Signer(id=customer_signer_ref.id, name=customer_signer_name, email=customer_json.get(
                "email"), color=4283417505, customerId=customer_id, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                    "id",
                    "createdAt",
                })
            customer_signer_ref.set({
                **customer_signer_json,
                "createdAt": SERVER_TIMESTAMP
            })

        create_document_audit_log(document_doc_ref, action=AuditLogAction.DOCUMENT_CREATED, actor_role=AuditLogActorRole.USER,
                                  target_id=document_doc_ref.id, target_type=AuditLogTargetType.DOCUMENT, actor_id=user_uid, actor_email=user.get(
                                      "email"),
                                  actor_name=user.get("name"), ip_address=request.remote_addr, user_agent=request.user_agent.string)

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error creating document"}, 500)


@bp.get("/customers/<customer_id>/documents")
@login_required
@customer_owner_required
def get_documents(customer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        documents_snapshots = firestore_client.collection(
            "documents").where(filter=FieldFilter("customerId", "==", customer_id)).get()

        documents_list = []
        for document_snap in documents_snapshots:
            document_json = get_merged_document(document_snap.reference)
            documents_list.append(document_json)

        return jsonify(documents_list), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error retrieving documents"}, 500)


@bp.get("/customers/<customer_id>/documents/<document_id>")
@login_required
@customer_owner_required
def get_document(customer_id, document_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error retrieving document"}, 500)


@bp.put("/customers/<customer_id>/documents/<document_id>/update")
@login_required
@customer_owner_required
def update_document(customer_id, document_id):
    try:
        user = request.user
        request_data = request.get_json()
        document_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        document_json = document_doc_ref.get().to_dict()
        document_json["id"] = document_doc_ref.id
        document_json["createdAt"] = "PLACEHOLDER_FOR_SERVER_TIMESTAMP"

        document_obj = Document(**document_json)

        document_obj.name = document_name
        document_obj.text = text
        document_obj.plainText = plain_text

        document_doc_ref.update(document_obj.model_dump(include={
            "name", "text", "plainText",
        }))

        create_document_audit_log(document_doc_ref, action=AuditLogAction.DOCUMENT_UPDATED.value, actor_role=AuditLogActorRole.USER.value,
                                  target_id=document_doc_ref.id, target_type=AuditLogTargetType.DOCUMENT.value, actor_id=user.get("uid"), actor_email=user.get(
                                      "email"),
                                  actor_name=user.get("name"), ip_address=request.remote_addr, user_agent=request.user_agent.string)

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating document"}, 500)


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

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        signers_docs = document_doc_ref.collection("signers").where(
            filter=FieldFilter("email", "==", signer_email)).get()

        if len(signers_docs) > 0:
            raise Exception("Signer already exists")

        signer_doc_ref = document_doc_ref.collection("signers").document()
        signer_json = Signer(id=signer_doc_ref.id, name=signer_name, email=signer_email, color=signer_color, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
            "id", "createdAt",
        })
        signer_doc_ref.set({**signer_json, "createdAt": SERVER_TIMESTAMP})

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error creating document signer"}, 500)


@bp.delete("/customers/<customer_id>/documents/<document_id>/signers/<signer_id>")
@login_required
@customer_owner_required
def delete_document_signer(customer_id, document_id, signer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        if not signer_doc_ref.get().exists:
            raise Exception("Signer not found")

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

        # Batch delete signature boxes
        batch.commit()

        # Delete signer
        signer_doc_ref.delete()

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error deleting document signer"}, 500)


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

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        if not signer_doc_ref.get().exists:
            raise Exception("Signer not found")

        signer_json = Signer(id=signer_doc_ref.id, name=signer_name, email=signer_email,
                             color=signer_color, userId=signer_userId, customerId=signer_customerId, createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP").model_dump(exclude={
                                 "id", "createdAt",
                             })
        signer_doc_ref.update({**signer_json, "updatedAt": SERVER_TIMESTAMP})

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating document signer"}, 500)


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

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        signature_boxes_coll_ref = document_doc_ref.collection(
            "signatureBoxes")
        existing_signature_boxes_docs = signature_boxes_coll_ref.list_documents()

        batch = firestore_client.batch()
        for existing_signature_box_doc in existing_signature_boxes_docs:
            batch.delete(existing_signature_box_doc)
        batch.commit()

        for signature_box in signature_boxes:
            signature_box_doc_ref = signature_boxes_coll_ref.document()
            signature_box_json = SignatureBox(
                id=signature_box_doc_ref.id, **signature_box)

            signature_box_doc_ref.set(signature_box_json.model_dump(exclude={
                "id",
            }))

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating document signature boxes"}, 500)


@bp.post("/customers/<customer_id>/documents/<document_id>/signatures")
@login_required
@customer_owner_required
def create_user_document_signature(customer_id, document_id):
    try:
        user = request.user
        request_form = request.form
        signer_id = request_form.get("signerId")
        signature_image_file = request.files["file"]

        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        signer_snap = signer_doc_ref.get()
        if not signer_snap.exists:
            raise Exception("Signer not found")

        if signer_snap.to_dict().get("userId", None) != user.get("uid"):
            raise Exception("Signer is not the current user")

        # Get existing signature boxes for signer
        signature_box_coll_ref = document_doc_ref.collection("signatureBoxes")
        signature_box_snapshots = signature_box_coll_ref.where(
            filter=FieldFilter("signerId", "==", signer_id)).get()

        # Check if signature box already has a signature
        for signature_box_snap in signature_box_snapshots:
            if signature_box_snap.to_dict().get("signatureId", None) is not None:
                raise Exception("Signature box already has a signature")

        # Upload signature image to storage
        tmp_path = save_file_to_tmp(signature_image_file)
        signature_image_path = f"customers/{customer_id}/documents/{document_id}/signatures/{uuid.uuid4()}.png"
        upload_to_storage(tmp_path, signature_image_path,
                          content_type="image/png")
        delete_tmp_file(tmp_path)

        signature_doc_ref = document_doc_ref.collection(
            "signatures").document()

        signature_obj = Signature(id=signature_doc_ref.id, signerId=signer_id,
                                  signatureImageStoragePath=signature_image_path, signedAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP")
        signature_doc_ref.set({
            **signature_obj.model_dump(exclude={
                "id", "signedAt",
            }), "signedAt": SERVER_TIMESTAMP
        })

        # Update signature boxes with signature id
        for signature_box_snap in signature_box_snapshots:
            signature_box_obj = SignatureBox(
                id=signature_box_snap.id, **signature_box_snap.to_dict())
            signature_box_obj.signatureId = signature_doc_ref.id

            signature_box_snap.reference.update(signature_box_obj.model_dump(include={
                "signatureId",
            }))

        all_signature_box_snapshots = signature_box_coll_ref.get()

        signature_boxes_with_signatures = [
            signature_box_snap
            for signature_box_snap in all_signature_box_snapshots
            if signature_box_snap.to_dict().get("signatureId", None) is not None
        ]

        # Update document status if applicable
        if len(signature_boxes_with_signatures) == len(all_signature_box_snapshots):
            document_doc_ref.update({
                "status": DocumentStatus.COMPLETED.value
            })
        elif signer_doc_ref.get().to_dict().get("userId", None) is not None and document_doc_ref.get().to_dict().get("status", None) not in (DocumentStatus.SENT.value, DocumentStatus.COMPLETED.value):
            document_doc_ref.update({
                "status": DocumentStatus.PREPARED.value
            })

        create_document_audit_log(document_doc_ref, action=AuditLogAction.SIGNATURE_COMPLETED, actor_role=AuditLogActorRole.SIGNER, target_id=signature_doc_ref.id, target_type=AuditLogTargetType.SIGNATURE,
                                  actor_id=signer_id, actor_email=signer_snap.get("email"), actor_name=signer_snap.get("name"),
                                  ip_address=request.remote_addr, user_agent=request.user_agent.string)

        # Clean up signers without matching signature boxes.
        remove_signers_without_matching_signature_boxes(document_doc_ref)

        return jsonify(get_merged_document(document_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error creating user document signature"}, 500)


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

        if not document_doc_ref.get().exists:
            raise Exception("Document not found")

        if document_doc_ref.get().to_dict().get("status") == DocumentStatus.COMPLETED.value:
            raise Exception("Document is already in status 'complete'")

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

            token = create_signing_token()
            signing_url = create_signing_url(token, document_id)

            # TODO: Add retry logic and error handling for email sending.
            response = EmailClient().send_simple_message(
                recipient_email, subject, body + "\n\n" + signing_url)

            invitation_doc_ref = document_doc_ref.collection(
                "invitations").document()
            invitation_json = Invitation(id=invitation_doc_ref.id, signerId=signer_id, email=recipient_email,
                                         name=recipient_name, documentId=document_id, token=token, status=InvitationStatus.SENT.value,
                                         sentAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP", expiresAt="PLACEHOLDER_FOR_DATETIME", reminderCount=0).model_dump(exclude={
                                             "id", "sentAt", "expiresAt",
                                         })

            invitation_doc_ref.set({
                **invitation_json,
                "sentAt": SERVER_TIMESTAMP,
                "expiresAt": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
            })

            create_document_audit_log(document_doc_ref, action=AuditLogAction.INVITATION_SENT, actor_role=AuditLogActorRole.USER, target_id=invitation_doc_ref.id, target_type=AuditLogTargetType.INVITATION,
                                      actor_id=user_uid, actor_email=user.get("email"), actor_name=user.get("name"),
                                      ip_address=request.remote_addr, user_agent=request.user_agent.string)

        document_doc_ref.update({
            "status": DocumentStatus.SENT.value
        })

        return jsonify(get_merged_document(document_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error sending signature invitations"}, 500)


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

        if not document_doc_ref.get().exists:
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

            complex_filter = And(filters=[
                Or(filters=[
                    FieldFilter("status", "==", InvitationStatus.SENT.value),
                    FieldFilter("status", "==", InvitationStatus.OPENED.value),
                    FieldFilter("status", "==",
                                InvitationStatus.DECLINED.value),
                ]),
                FieldFilter("signerId", "==", signer_id),
                FieldFilter("documentId", "==", document_id),
            ])
            # Update invitations status to canceled
            invitation_doc_snapshots = document_doc_ref.collection("invitations").where(
                filter=complex_filter).get()

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

        if not document_doc_ref.get().exists:
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


@bp.post("/customers/<customer_id>/documents/<document_id>/signers/<signer_id>/reminder")
@login_required
@customer_owner_required
def send_signature_reminder(customer_id, document_id, signer_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()

        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if document_doc_ref.get().to_dict().get("status") == DocumentStatus.COMPLETED.value:
            return jsonify({"error": "Document is already in status 'complete'"}, 400)

        signer_doc_snapshot = document_doc_ref.collection(
            "signers").document(signer_id).get()
        if not signer_doc_snapshot:
            return jsonify({"error": "Signer not found"}, 404)

        signer = signer_doc_snapshot.to_dict()
        signer_email = signer.get("email")
        signer_name = signer.get("name")

        complex_filter = And(filters=[
            Or(filters=[
                FieldFilter("status", "==", InvitationStatus.SENT.value),
                FieldFilter("status", "==", InvitationStatus.OPENED.value)
            ]),
            FieldFilter("signerId", "==", signer_id),
            FieldFilter("documentId", "==", document_id),
            FieldFilter("expiresAt", ">", datetime.datetime.now(
                datetime.timezone.utc)),
        ])
        existing_invitations_snapshots = document_doc_ref.collection("invitations").where(
            filter=complex_filter).get()

        # Get token for reminder invitation. If no existing invitations, generate new token.
        if existing_invitations_snapshots:
            token = existing_invitations_snapshots[0].to_dict().get("token")
        else:
            token = create_signing_token()

        signing_url = create_signing_url(token, document_id)

        # TODO: Add retry logic and error handling for email sending.
        response = EmailClient().send_simple_message(signer_email, "Signature Reminder",
                                                     "You have a signature request for the document. Please sign it. " + signing_url)

        if existing_invitations_snapshots:
            existing_invitations_snapshots[0].reference.update({
                "lastReminderAt": SERVER_TIMESTAMP,
                "reminderCount": Increment(1),
            })
        else:
            document_doc_ref.collection("invitations").document().set({
                "signerId": signer_id,
                "email": signer_email,
                "name": signer_name,
                "documentId": document_id,
                "token": token,
                "status": InvitationStatus.SENT.value,
                "sentAt": SERVER_TIMESTAMP,
                "expiresAt": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14),
            })
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.delete("/customers/<customer_id>/documents/<document_id>/delete")
@login_required
@customer_owner_required
def delete_document(customer_id, document_id):
    try:
        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = get_document_ref_for_customer(
            firestore_client, customer_id, document_id)

        if not document_doc_ref.get().exists:
            return jsonify({"error": "Document not found"}, 404)

        if document_doc_ref.get().to_dict().get("status") in (DocumentStatus.PREPARED.value, DocumentStatus.SENT.value, DocumentStatus.COMPLETED.value):
            return jsonify({"error": "Document not eligible for deletion due to it's current status."}, 400)

        # TODO: Check document audit logs to determine if it previously had signatures. If so,
        # archive this document, instead of deleting it. status = "archived"

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

        llm_client = LLMClient()

        response_text = llm_client.create_message(
            system=system_message,
            messages=[{"role": "user", "content": prompt}]
        )

        # Remove ```json fences
        cleaned_response_text = re.sub(
            r"```json|```", "", response_text).strip()

        document_delta = json.loads(cleaned_response_text)

        return jsonify(document_delta), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/documents/<document_id>/signing-requests/<token>")
@signing_token_required
def get_signing_document(document_id, token):
    try:
        signer_id = request.signer_id
        firestore_client = firestore.client()

        return jsonify(get_merged_signing_document(
            firestore_client, document_id, signer_id)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error retrieving signing document"}, 500)


@bp.post("/documents/<document_id>/signing-requests/<token>/signatures")
@signing_token_required
def create_signer_document_signature(document_id, token):
    try:
        document_doc_ref = request.document_doc_ref
        invitation_doc_ref = request.invitation_doc_ref
        signer_id = request.signer_id
        signer_name = request.signer_name
        signer_email = request.signer_email
        signature_image_file = request.files["file"]

        firestore_client: google.cloud.firestore.Client = firestore.client()

        # Upload signature image to storage
        tmp_path = save_file_to_tmp(signature_image_file)
        signature_image_path = f"customers/{document_doc_ref.get().get("customerId")}/documents/{document_id}/signatures/{uuid.uuid4()}.png"
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

        # Update invitation status to completed
        invitation_doc_ref.update({
            "status": InvitationStatus.COMPLETED.value,
            "completedAt": SERVER_TIMESTAMP,
        })

        # Create audit log for signature completion
        create_document_audit_log(document_doc_ref, AuditLogAction.SIGNATURE_COMPLETED, AuditLogActorRole.SIGNER, signature_doc_ref.id, AuditLogTargetType.SIGNATURE,
                                  actor_id=signer_id, actor_email=signer_email, actor_name=signer_name, ip_address=request.remote_addr, user_agent=request.user_agent.string)

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

        # Clean up signers without matching signature boxes.
        remove_signers_without_matching_signature_boxes(document_doc_ref)

        return jsonify(get_merged_signing_document(firestore_client, document_id, signer_id)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error submitting signature"}, 500)


@bp.post("/documents/<document_id>/signing-requests/<token>/signatures/decline")
@signing_token_required
def decline_signature_invitation(document_id, token):
    try:
        signer_id = request.signer_id
        signer_name = request.signer_name
        signer_email = request.signer_email
        request_data = request.get_json()
        reason = request_data.get("reason")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        document_snap = document_doc_ref.get()
        if not document_snap.exists:
            raise Exception("Document not found")

        complex_filter = And(filters=[
            Or(filters=[
                FieldFilter("status", "==", InvitationStatus.SENT.value),
                FieldFilter("status", "==", InvitationStatus.OPENED.value),
            ]),
            FieldFilter("signerId", "==", signer_id),
            FieldFilter("documentId", "==", document_id),
        ])
        invitation_snapshots = document_doc_ref.collection("invitations").where(
            filter=complex_filter).get()

        if not invitation_snapshots:
            raise Exception("Invitation not found")

        # Update invitation status to declined
        invitation_snapshots[0].reference.update({
            "status": InvitationStatus.DECLINED.value,
            "declinedAt": SERVER_TIMESTAMP,
            "declinedReason": reason,
        })
        invitation_id = invitation_snapshots[0].id

        # Update audit log to record the signature decline
        create_document_audit_log(document_doc_ref, AuditLogAction.SIGNATURE_DECLINED, AuditLogActorRole.SIGNER, invitation_id, AuditLogTargetType.SIGNATURE,
                                  actor_id=signer_id, actor_email=signer_email, actor_name=signer_name, ip_address=request.remote_addr, user_agent=request.user_agent.string)

        return jsonify(get_merged_signing_document(firestore_client, document_id, signer_id)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error declining signature"}, 500)


# ------------------------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------------------------


# Get merged document helper function
def get_merged_document(document_doc_ref) -> dict | None:
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
            signer_json["createdAt"] = signer_json.get(
                "createdAt").isoformat()
            signer_json["updatedAt"] = datetime_iso_or_none(signer_json.get(
                "updatedAt"))
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

        invitations_docs = document_doc_ref.collection("invitations").get()
        invitations_json = []
        for invitation_doc in invitations_docs:
            invitation_json = invitation_doc.to_dict()
            invitation_json["id"] = invitation_doc.id
            invitation_json["sentAt"] = invitation_json.get(
                "sentAt").isoformat()
            invitation_json["expiresAt"] = invitation_json.get(
                "expiresAt").isoformat()
            invitation_json["openedAt"] = datetime_iso_or_none(
                invitation_json.get("openedAt"))

            invitation_json["completedAt"] = datetime_iso_or_none(
                invitation_json.get("completedAt"))

            invitation_json["canceledAt"] = datetime_iso_or_none(
                invitation_json.get("canceledAt"))

            invitation_json["declinedAt"] = datetime_iso_or_none(
                invitation_json.get("declinedAt"))

            invitation_json["lastReminderAt"] = datetime_iso_or_none(
                invitation_json.get("lastReminderAt"))

            invitations_json.append(invitation_json)
        document_json["invitations"] = invitations_json

        audit_logs_docs = document_doc_ref.collection("auditLogs").get()
        audit_logs_json = []
        for audit_log_doc in audit_logs_docs:
            audit_log_json = audit_log_doc.to_dict()
            audit_log_json["id"] = audit_log_doc.id
            audit_log_json["timestamp"] = audit_log_json.get(
                "timestamp").isoformat()
            audit_logs_json.append(audit_log_json)
        document_json["auditLogs"] = audit_logs_json

        return document_json
    except Exception as e:
        logger.error(f"error: {e}")
        return None


# Get signing document json helper function, which is a limited view of the document,
# only including fields that are needed for signing.
def get_merged_signing_document(firestore_client: google.cloud.firestore.Client, document_id: str, signer_id: str) -> dict | None:
    try:
        document_doc_ref = firestore_client.collection(
            "documents").document(document_id)

        document_snap = document_doc_ref.get()
        if not document_snap.exists:
            raise Exception("Document not found")

        customer_id = document_snap.get("customerId")

        customer_snap = firestore_client.collection(
            "customers").document(customer_id).get()
        if not customer_snap.exists:
            raise Exception("Customer not found")
        user_id = customer_snap.get("userId")

        user_doc_ref = firestore_client.collection(
            "users").document(user_id)

        user_snap = user_doc_ref.get()
        if not user_snap.exists:
            raise Exception("User not found")

        company_snapshots = firestore_client.collection("companies").where(
            filter=FieldFilter("adminUserId", "==", customer_id)).get()

        if company_snapshots:
            company_name = company_snapshots[0].get("name")
        else:
            company_name = None

        signer_doc_ref = document_doc_ref.collection(
            "signers").document(signer_id)
        signer_json = signer_doc_ref.get().to_dict()
        signer_json["id"] = signer_doc_ref.id
        signer_json["createdAt"] = signer_json.get(
            "createdAt").isoformat()
        signer_json["updatedAt"] = datetime_iso_or_none(signer_json.get(
            "updatedAt"))

        signature_boxes_snapshots = document_doc_ref.collection("signatureBoxes").where(
            filter=FieldFilter("signerId", "==", signer_id)).get()

        if not signature_boxes_snapshots:
            raise Exception("No signature boxes found")

        signature_boxes_json = []
        for signature_box_snapshot in signature_boxes_snapshots:
            signature_box_json = signature_box_snapshot.to_dict()
            signature_box_json["id"] = signature_box_snapshot.id
            signature_boxes_json.append(signature_box_json)

        signatures_snapshots = document_doc_ref.collection("signatures").where(
            filter=FieldFilter("signerId", "==", signer_id)).get()

        signatures_json = []
        if signatures_snapshots:
            for signature_snapshot in signatures_snapshots:
                signature_json = signature_snapshot.to_dict()
                signature_json["id"] = signature_snapshot.id
                signature_json["signedAt"] = signature_json.get(
                    "signedAt").isoformat()
                signatures_json.append(
                    Signature(**signature_json).model_dump())

        audit_logs_snapshots = document_doc_ref.collection("auditLogs").get()

        if not audit_logs_snapshots:
            raise Exception("No audit logs found")

        audit_logs_list = []
        for audit_log_snapshot in audit_logs_snapshots:
            audit_log_json = audit_log_snapshot.to_dict()
            audit_log_json["id"] = audit_log_snapshot.id
            audit_log_json["timestamp"] = audit_log_json.get(
                "timestamp").isoformat()

            audit_log = AuditLog(**audit_log_json)
            audit_logs_list.append(audit_log.model_dump(exclude={
                "actor": {"ipAddress", "userAgent"},
            }))

        signing_document = SigningDocument(
            id=document_id,
            name=document_snap.get("name"),
            text=document_snap.get("text"),
            signer=signer_json,
            signatureBoxes=signature_boxes_json,
            signatures=signatures_json,
            adminName=user_snap.get("displayName"),
            adminEmail=user_snap.get("email"),
            companyName=company_name,
            auditLogs=audit_logs_list
        )

        return signing_document.model_dump()
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
    try:
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
    except Exception as e:
        logger.error(f"error: {e}")


def create_document_audit_log(document_doc_ref: DocumentReference, action: AuditLogAction, actor_role: AuditLogActorRole, target_id: str, target_type: AuditLogTargetType,
                              actor_id: str = None, actor_email: str = None, actor_name: str = None, ip_address: str = None,
                              user_agent: str = None, metadata_reason: str = None, metadata_method: str = None):
    try:
        audit_log_doc_ref = document_doc_ref.collection("auditLogs").document()
        audit_log_doc_ref.set({
            "documentId": document_doc_ref.id,
            "timestamp": SERVER_TIMESTAMP,
            "action": action,
            "actor": {
                "id": actor_id,
                "role": actor_role,
                "name": actor_name,
                "email": actor_email,
                "ipAddress": ip_address,  # endpoint request object request.remote_addr
                "userAgent": user_agent,  # endpoint request object request.user_agent.string
            },
            "target": {
                "id": target_id,
                "type": target_type,
            },
            "metadata": {
                "reason": metadata_reason,
                "method": metadata_method,
            },
        })
    except Exception as e:
        logger.error(f"error: {e}")


def create_signing_token():
    return secrets.token_urlsafe(32)


def create_signing_url(token: str, document_id: str):
    return f"{os.getenv('FULL_WEB_DOMAIN')}/#/sign/{document_id}?token={token}"
