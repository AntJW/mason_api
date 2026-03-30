from flask import request, jsonify
from functools import wraps
from firebase_admin import auth, firestore
import google.cloud.firestore
from logger import logger
from models.invitation import InvitationStatus
from google.cloud.firestore import And, FieldFilter, Or

# Custom decorator to verify Firebase Authentication token


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized: No token provided."}), 401

        # Extract the token
        id_token = auth_header.split("Bearer ")[1]

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)

            # Deny access to anonymous users
            if decoded_token.get('firebase', {}).get('sign_in_provider') == 'anonymous':
                return jsonify({"error": "Unauthorized: Invalid or expired token."}), 401

            request.user = decoded_token  # Attach user info to request
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return jsonify({"error": "Unauthorized: Invalid or expired token."}), 401

        return f(*args, **kwargs)

    return decorated_function


# Email link user or Firebase Auth anonymous user required. Used in special cases where
# an Firebase auth anynomous user can access the api endpoint, like for getting data for
# the landing page of the website, or from a user invite page.
def login_or_anonymous_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized: No token provided."}), 401

        # Extract the token
        id_token = auth_header.split("Bearer ")[1]

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)
            request.user = decoded_token  # Attach user info to request
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return jsonify({"error": "Unauthorized: Invalid or expired token."}), 401

        return f(*args, **kwargs)

    return decorated_function


def customer_owner_required(f):
    """Require the URL ``customer_id`` to belong to ``request.user`` (Firestore ``userId``).

    Use only below ``@login_required`` so ``request.user`` is set.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return jsonify({"error": "Missing customer_id."}), 400

        user_uid = request.user.get("uid")
        firestore_client: google.cloud.firestore.Client = firestore.client()
        customer_snap = firestore_client.collection("customers").document(
            customer_id
        ).get(field_paths=["userId"])

        if not customer_snap.exists:
            return jsonify({"error": "Customer not found."}), 404

        owner_uid = customer_snap.get("userId")
        if owner_uid != user_uid:
            return jsonify({"error": "Forbidden: customer does not belong to this user."}), 403

        return f(*args, **kwargs)

    return decorated_function


# Used to verify that the signer has authorized token to sign the document.
def signing_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            document_id = kwargs.get("document_id")
            if not document_id:
                raise Exception("Document ID is required")

            token = kwargs.get("token")
            if not token:
                raise Exception("Token is required")

            firestore_client = firestore.client()
            document_doc_ref = firestore_client.collection(
                "documents").document(document_id)
            document_json = document_doc_ref.get().to_dict()
            if not document_json:
                raise Exception("Document not found")

            complex_filter = And(filters=[
                Or(filters=[
                    FieldFilter("status", "==", InvitationStatus.SENT.value),
                    FieldFilter("status", "==", InvitationStatus.OPENED.value),
                    FieldFilter("status", "==",
                                InvitationStatus.DECLINED.value),
                ]),
                FieldFilter("documentId", "==", document_id),
                FieldFilter("token", "==", token),
            ])
            invitation_snapshots = document_doc_ref.collection("invitations").where(
                filter=complex_filter).get()

            if not invitation_snapshots:
                raise Exception("Invitation not found")

            signer_id = invitation_snapshots[0].to_dict().get("signerId")

            signer_snap = document_doc_ref.collection(
                "signers").document(signer_id).get()
            if not signer_snap.exists:
                raise Exception("Signer not found")

            request.signer_id = signer_id
            request.signer_name = signer_snap.get("name")
            request.signer_email = signer_snap.get("email")
            request.signer_color = signer_snap.get("color")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated_function
