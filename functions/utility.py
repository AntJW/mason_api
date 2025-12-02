import re
import io
from werkzeug.datastructures import FileStorage
import os
import tempfile
from firebase_admin import storage
import subprocess


def is_valid_email(email: str) -> bool:
    """
    Simple email validator. Uses a regex to check if the email is valid.
    """
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}", email):
        return False
    return True


def max_length(value: str, max_length: int) -> bool:
    """
    Check if the value is less than or equal to the max length.
    """
    if len(value.strip()) > max_length:
        return False
    return True


def min_length(value: str, min_length: int) -> bool:
    """
    Check if the value is greater than or equal to the min length.
    """
    if len(value.strip()) < min_length:
        return False
    return True


def convert_audio_sample_rate(file_path, sample_rate: int = 16000):
    """
    Convert audio file to specified sample rate using librosa.
    Returns (audio_array, sample_rate) tuple.
    """
    try:
        # Use FFmpeg to convert directly to stdout
        command = [
            'ffmpeg',
            '-i', file_path,
            '-ar', str(sample_rate),  # Resample
            '-ac', '1',  # Mono
            '-f', 'wav',  # Output format
            '-'  # Output to stdout
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            check=True,
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr.decode()}")

        wav_bytes_io = io.BytesIO(result.stdout)
        wav_bytes_io.seek(0)  # rewind to the start

        return wav_bytes_io
    except Exception as e:
        raise e


def upload_to_storage(local_tmp_file_path, storage_file_path, make_public: bool = False):
    try:
        bucket = storage.bucket()
        blob = bucket.blob(storage_file_path)
        blob.upload_from_filename(local_tmp_file_path)

        if make_public:
            blob.make_public()

        return blob
    except Exception as e:
        raise e


def download_from_storage(storage_file_path) -> str:
    try:
        local_tmp_file_path = tempfile.NamedTemporaryFile(delete=False).name
        bucket = storage.bucket()
        blob = bucket.blob(storage_file_path)
        blob.download_to_filename(local_tmp_file_path)
        return local_tmp_file_path
    except Exception as e:
        raise e


def save_file_to_tmp(file: FileStorage) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    return tmp_path


def delete_tmp_file(tmp_path: str):
    os.remove(tmp_path)
