from flask import request, jsonify
from functools import wraps
from firebase_admin import auth, firestore
import google.cloud.firestore
from logger import logger
from models.invitation import InvitationStatus
from google.cloud.firestore import And, FieldFilter, Or, Query
from models.document import DocumentStatus
from models.user import UserStatus, UserRole

# Custom decorator to verify Firebase Authentication token


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Unauthorized: No token provided.")

        # Extract the token
        id_token = auth_header.split("Bearer ")[1]

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)

            # Deny access to anonymous users
            if decoded_token.get('firebase', {}).get('sign_in_provider') == 'anonymous':
                raise Exception(
                    "Unauthorized: Anonymous users are not allowed to access this endpoint.")

            firestore_client: google.cloud.firestore.Client = firestore.client()
            user_doc_snap = firestore_client.collection("users").document(
                decoded_token.get("uid")).get()
            if not user_doc_snap.exists:
                raise Exception("Unauthorized: User not found.")

            request.user = decoded_token  # Attach user info to request
            request.user["displayName"] = user_doc_snap.get("displayName")
            request.user["firstName"] = user_doc_snap.get("firstName")
            request.user["lastName"] = user_doc_snap.get("lastName")
            request.user["email"] = user_doc_snap.get("email")
            request.user["companyId"] = user_doc_snap.get("companyId")
            request.user["role"] = user_doc_snap.get("role")
            request.user["status"] = user_doc_snap.get("status")
            request.user["statusUpdatedAt"] = user_doc_snap.get(
                "statusUpdatedAt")
            request.user["createdAt"] = user_doc_snap.get("createdAt")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return jsonify({"error": "Unauthorized: Invalid or expired token."}), 401

        return f(*args, **kwargs)

    return decorated_function


def new_user_auth(f):
    """
    NOTE: This decororator should ONLY be used for create_new_user_properties_me endpoint. That endpoint is 
    creates a new user properties in the database and return the user object. The @login_required decorator 
    requires user properties to already be set, hence the need for this one off decorator.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Unauthorized: No token provided.")

        # Extract the token
        id_token = auth_header.split("Bearer ")[1]

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)

            # Deny access to anonymous users
            if decoded_token.get('firebase', {}).get('sign_in_provider') == 'anonymous':
                raise Exception(
                    "Unauthorized: Anonymous users are not allowed to access this endpoint.")

            request.user = decoded_token  # Attach user info to request
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return jsonify({"error": "Unauthorized: Invalid or expired token."}), 401

        return f(*args, **kwargs)

    return decorated_function


def login_or_anonymous_required(f):
    """
    Email link user or Firebase Auth anonymous user required. Used in special cases where
    an Firebase auth anynomous user can access the api endpoint, like for getting data for
    the landing page of the website, or from a user invite page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise Exception("Unauthorized: No token provided.")

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
        try:
            customer_id = kwargs.get("customer_id")
            if not customer_id:
                raise Exception("Missing customer_id.")

            user_uid = request.user.get("uid")
            firestore_client: google.cloud.firestore.Client = firestore.client()
            customer_snap = firestore_client.collection("customers").document(
                customer_id
            ).get(field_paths=["userId"])

            if not customer_snap.exists:
                raise Exception("Customer not found.")

            owner_uid = customer_snap.get("userId")
            if owner_uid != user_uid:
                raise Exception(
                    "Unauthorized: user is not the owner of the customer.")
        except Exception as e:
            logger.error(f"customer_owner_required error: {e}")
            return jsonify({"error": "Unauthorized: access denied."}), 403

        return f(*args, **kwargs)

    return decorated_function


def customer_permissions_required(f):
    """Require user to be member of the company that owns the customer to access certain customer endpoints.
    Use only below ``@login_required`` so ``request.user`` is set.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            customer_id = kwargs.get("customer_id")
            if not customer_id:
                raise Exception("Missing customer_id.")

            firestore_client: google.cloud.firestore.Client = firestore.client()

            customer_doc_ref = firestore_client.collection("customers").document(
                customer_id
            )
            customer_snap = customer_doc_ref.get()

            if not customer_snap.exists:
                raise Exception("Customer not found.")

            if customer_snap.get("companyId") != request.user.get("companyId"):
                raise Exception(
                    "Unauthorized: user is not a member of the company that owns the customer.")

            request.customer_doc_ref = customer_doc_ref
        except Exception as e:
            logger.error(f"customer_permissions_required error: {e}")
            return jsonify({"error": "Unauthorized: access denied."}), 403

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
            document_snap = document_doc_ref.get()
            if not document_snap.exists:
                raise Exception("Document not found")

            # If document is not in status 'sent', restrict access.
            if document_snap.get("status") != DocumentStatus.SENT.value:
                raise Exception("Document is not in status 'sent'")

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
                filter=complex_filter).order_by("sentAt", direction=Query.DESCENDING).limit(1).get()

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
            request.document_doc_ref = document_doc_ref
            request.invitation_doc_ref = invitation_snapshots[0].reference
        except Exception as e:
            logger.error(f"signing_token_required error: {e}")
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated_function


def company_permissions_required(f):
    """
    Require the user to be a member of the company to access certain company endpoints.
    Use below @login_required so request.user is set.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            company_id = kwargs.get("company_id")
            if not company_id:
                raise Exception("Company ID is required")

            firestore_client: google.cloud.firestore.Client = firestore.client()
            company_doc_ref = firestore_client.collection("companies").document(
                company_id)

            if not company_doc_ref.get().exists:
                raise Exception("Company not found")

            if company_doc_ref.id != request.user.get("companyId"):
                raise Exception("Unauthorized: company ID mismatch.")

            if request.user.get("status") != UserStatus.ACTIVE.value:
                raise Exception(
                    "Unauthorized: user is not have active status.")

            request.company_doc_ref = company_doc_ref
        except Exception as e:
            logger.error(f"company_permissions_required error: {e}")
            return jsonify({"error": "Unauthorized: access denied."}), 403

        return f(*args, **kwargs)

    return decorated_function


def company_admin_required(f):
    """
    Require the user to have admin permissions to access certain company endpoints.
    Use below @login_required so request.user is set.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            company_id = kwargs.get("company_id")
            if not company_id:
                raise Exception("Company ID is required")

            firestore_client: google.cloud.firestore.Client = firestore.client()
            company_doc_ref = firestore_client.collection("companies").document(
                company_id)

            if not company_doc_ref.get().exists:
                raise Exception("Company not found")

            if company_doc_ref.id != request.user.get("companyId"):
                raise Exception("Unauthorized: company ID mismatch.")

            if request.user.get("role") != UserRole.ADMIN.value:
                raise Exception("Unauthorized: user is not have admin role.")

            if request.user.get("status") != UserStatus.ACTIVE.value:
                raise Exception(
                    "Unauthorized: user is not have active status.")

            request.company_doc_ref = company_doc_ref
        except Exception as e:
            logger.error(f"company_admin_required error: {e}")
            return jsonify({"error": "Unauthorized: access denied."}), 403

        return f(*args, **kwargs)

    return decorated_function


def company_owner_required(f):
    """
    Require the user to be the owner of the company to access certain company endpoints.
    Use below @login_required so request.user is set.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            company_id = kwargs.get("company_id")
            if not company_id:
                raise Exception("Company ID is required")

            firestore_client: google.cloud.firestore.Client = firestore.client()
            company_doc_ref = firestore_client.collection("companies").document(
                company_id)

            if not company_doc_ref.get().exists:
                raise Exception("Company not found")

            if company_doc_ref.get().get("ownerUserId") != request.user.get("uid"):
                raise Exception(
                    "Unauthorized: user is not the owner of the company.")

            request.company_doc_ref = company_doc_ref
        except Exception as e:
            logger.error(f"company_owner_required error: {e}")
            return jsonify({"error": "Unauthorized: access denied."}), 403

        return f(*args, **kwargs)

    return decorated_function
