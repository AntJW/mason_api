import os
import requests

# EmailClient is a client for sending emails. Currently using the Mailgun API.


class EmailClient:
    def __init__(self):
        self._base_url = os.getenv('EMAIL_SERVICE_BASE_URL')
        self._domain = os.getenv('EMAIL_SERVICE_DOMAIN')
        self._api_key = os.getenv('EMAIL_SERVICE_API_KEY')

    def send_simple_message(self, to: str, subject: str, text: str):
        return requests.post(
            f"{self._base_url}/v3/{self._domain}/messages",
            auth=("api", self._api_key),
            data={"from": f"Mailgun Sandbox <postmaster@{self._domain}>",
                  "to": to,
                  "subject": subject,
                  "text": text})
