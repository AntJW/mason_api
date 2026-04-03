import json
import os
import re

import google.cloud.firestore
from firebase_admin import firestore
from flask import Blueprint, jsonify, request
from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter, DocumentReference
from auth_decorator import login_required, company_permissions_required, template_permissions_required
from clients.llm_client import LLMClient
from logger import logger
from models.template import Template

bp = Blueprint("templates", __name__)


@bp.post("/templates/create")
@login_required
@company_permissions_required
def create_template():
    try:
        user = request.user
        request_data = request.get_json()
        template_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        firestore_client: google.cloud.firestore.Client = firestore.client()
        template_doc_ref = firestore_client.collection(
            "templates").document()

        template_json = Template(
            id=template_doc_ref.id,
            name=template_name,
            text=text,
            plainText=plain_text,
            createdByUserId=user.get("uid"),
            companyId=user.get("companyId"),
            createdAt="PLACEHOLDER_FOR_SERVER_TIMESTAMP",
        ).model_dump(exclude={
            "id", "createdAt",
        })

        template_doc_ref.set({
            **template_json,
            "createdAt": SERVER_TIMESTAMP
        })

        return jsonify(_get_template_json_for_response(template_doc_ref)), 201
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/templates")
@login_required
@company_permissions_required
def get_templates():
    try:
        user = request.user
        firestore_client: google.cloud.firestore.Client = firestore.client()
        templates_snapshots = firestore_client.collection(
            "templates").where(filter=FieldFilter("companyId", "==", user.get("companyId"))).get()

        templates_objs = []
        for template_snap in templates_snapshots:
            template_json = template_snap.to_dict()
            template_json["id"] = template_snap.id
            template_json["createdAt"] = template_json.get(
                "createdAt").isoformat()
            templates_objs.append(Template(**template_json))

        return jsonify([template_obj.model_dump() for template_obj in templates_objs]), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/templates/<template_id>")
@login_required
@template_permissions_required
def get_template(template_id):
    try:
        return jsonify(_get_template_json_for_response(request.template_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error getting template"}), 500


@bp.put("/templates/<template_id>/update")
@login_required
@template_permissions_required
def update_template(template_id):
    try:
        template_doc_ref = request.template_doc_ref
        request_data = request.get_json()
        template_name = request_data.get("name")
        text = request_data.get("text")
        plain_text = request_data.get("plainText")

        template_json = template_doc_ref.get().to_dict()
        template_json["id"] = template_doc_ref.id
        template_json["createdAt"] = template_json.get(
            "createdAt").isoformat()

        # Update template values
        template_json["name"] = template_name
        template_json["text"] = text
        template_json["plainText"] = plain_text

        template_obj = Template(**template_json)
        template_doc_ref.update(template_obj.model_dump(include={
            "name", "text", "plainText",
        }))

        return jsonify(_get_template_json_for_response(template_doc_ref)), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error updating template"}), 500


@bp.delete("/templates/<template_id>/delete")
@login_required
@template_permissions_required
def delete_template(template_id):
    try:
        template_doc_ref = request.template_doc_ref
        template_doc_ref.delete()
        return jsonify({}), 200
    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error deleting template"}), 500


@bp.post("/templates/ai/generate")
@login_required
@company_permissions_required
def ai_generate_template_text():
    try:
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

        llm_client = LLMClient()

        response_text = llm_client.create_message(
            system=system_message,
            messages=[{"role": "user", "content": prompt}]
        )

        # Remove ```json fences
        cleaned_response_text = re.sub(
            r"```json|```", "", response_text).strip()

        template_delta = json.loads(cleaned_response_text)

        return jsonify(template_delta), 200

    except Exception as e:
        logger.error(f"error: {e}")
        return jsonify({"error": "Error generating template text"}), 500


# ------------------------------------------------------------------------------------------------
# Templates helper functions below this line
# ------------------------------------------------------------------------------------------------

def _get_template_json_for_response(template_doc_ref: DocumentReference) -> dict | None:
    try:
        template_json = template_doc_ref.get().to_dict()
        template_json["id"] = template_doc_ref.id
        template_json["createdAt"] = template_json.get("createdAt").isoformat()
        return Template(**template_json).model_dump()
    except Exception as e:
        logger.error(f"error: _get_template_json_for_response failed: {e}")
        return None
