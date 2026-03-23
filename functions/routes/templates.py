import json
import os
import re

import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter

from auth_decorator import login_required
from clients.llm_client import LLMClient
from logger import logger

bp = Blueprint("templates", __name__)


@bp.post("/templates/create")
@login_required
def create_template():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        template_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        template_doc_ref = firestore_client.collection(
            "templates").document()
        template_id = template_doc_ref.id

        template_json = {
            "name": template_name,
            "text": text,
            "plainText": plain_text,
            "createdAt": SERVER_TIMESTAMP,
            "userId": user_uid
        }

        template_doc_ref.set(template_json)

        template_doc = template_doc_ref.get(field_paths=[
            "name", "text", "plainText", "createdAt", "userId"])
        template_json = template_doc.to_dict()
        template_json["id"] = template_id
        template_json["createdAt"] = template_doc.get(
            "createdAt").isoformat()

        return jsonify(template_json), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/templates")
@login_required
def get_templates():
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        templates_docs = firestore_client.collection(
            "templates").where(filter=FieldFilter("userId", "==", user_uid)).get()

        templates_list = []
        for template_doc in templates_docs:
            template_json = template_doc.to_dict()
            templates_list.append({
                "id": template_doc.id,
                "name": template_json.get("name"),
                "text": template_json.get("text"),
                "plainText": template_json.get("plainText"),
                "createdAt": template_json.get("createdAt").isoformat(),
                "userId": template_json.get("userId")
            })
        return jsonify(templates_list), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/templates/<template_id>")
@login_required
def get_template(template_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        template_doc_ref = firestore_client.collection(
            "templates").document(template_id)
        template_doc = template_doc_ref.get(field_paths=[
            "name", "text", "plainText", "createdAt", "userId"])
        template_json = template_doc.to_dict()
        template_json["id"] = template_id
        template_json["createdAt"] = template_doc.get(
            "createdAt").isoformat()
        return jsonify(template_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.put("/templates/<template_id>/update")
@login_required
def update_template(template_id):
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        template_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        template_doc_ref = firestore_client.collection(
            "templates").document(template_id)
        template_doc_ref.update({
            "name": template_name,
            "text": text,
            "plainText": plain_text,
        })

        template_doc = template_doc_ref.get(field_paths=[
            "name", "text", "plainText", "createdAt", "userId"])
        template_json = template_doc.to_dict()
        template_json["id"] = template_id
        template_json["createdAt"] = template_doc.get(
            "createdAt").isoformat()
        return jsonify(template_json), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.delete("/templates/<template_id>/delete")
@login_required
def delete_template(template_id):
    try:
        user = request.user
        user_uid = user.get("uid")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        template_doc_ref = firestore_client.collection(
            "templates").document(template_id)
        template_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/templates/ai/generate")
@login_required
def ai_generate_template_text():
    try:
        user = request.user
        user_uid = user.get("uid")
        request_data = request.get_json()
        prompt = request_data.get("prompt")
        current_text = request_data.get("currentText")

        current_delta_str = json.dumps(current_text)

        system_parts = [
            "You are a document template generation assistant for a contractor CRM platform. The user will send a prompt describing what they want in a reusable document template.",
            "",
            "Templates are used repeatedly across different customers, so they must be customer-agnostic. Use placeholder variables like **CUSTOMER_NAME**, **CUSTOMER_ADDRESS**, **CUSTOMER_EMAIL**, **CUSTOMER_PHONE**, **DATE**, **PROJECT_DESCRIPTION**, **COMPANY_NAME**, etc. where customer- or project-specific details would go. Never hard-code specific names, addresses, or details that would change per customer.",
            "",
            "The current template and your response both use Quill Delta JSON format: {\"ops\": [{\"insert\": \"text\", \"attributes\": {...}}, ...]}. Preserve all existing formatting attributes (bold, italic, header, alignment, color, etc.) unless the user explicitly asks to change them.",
            "",
            "Important formatting rules:",
            "1. Block-level attributes (header, list, align, indent, blockquote, code-block, direction) MUST be applied to the newline character (\"\\n\") that terminates the line, NOT to the text insert.",
            "2. Text formatting attributes (bold, italic, underline, strike, code, color, background, link) MUST be applied to the text insert operations.",
            "3. Never apply \"header\" to a text insert. It must only appear on a newline insert.",
            "4. Every block must end with a newline insert.",
            "",
            "If the user asks to modify the current template (e.g. 'fix the tone', 'add a section about X', 'rewrite paragraph 2'), apply those changes and return the full modified template. Do not return only the changed portion—always return the complete template. If there is no existing content or the user asks for a new template from scratch, generate accordingly.",
            "",
            "---",
            "Current template in Quill Delta JSON:",
            current_delta_str or "(No existing content)",
        ]

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

        template_delta = json.loads(cleaned_response_text)

        return jsonify(template_delta), 200

    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500
