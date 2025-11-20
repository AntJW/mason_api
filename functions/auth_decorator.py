from flask import request, jsonify
from functools import wraps
from firebase_admin import auth, firestore
import google.cloud.firestore
from logger import logger

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

