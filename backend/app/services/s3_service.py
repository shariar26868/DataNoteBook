import boto3
import os
import uuid
from pathlib import Path
from botocore.exceptions import ClientError

from app.core.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    return _s3_client


def upload_fileobj_to_s3(fileobj, s3_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file-like object to S3. Returns the s3_key."""
    client = get_s3_client()
    client.upload_fileobj(
        fileobj,
        settings.S3_BUCKET_NAME,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    return s3_key


def upload_bytes_to_s3(data: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes to S3. Returns the s3_key."""
    import io
    return upload_fileobj_to_s3(io.BytesIO(data), s3_key, content_type)


def download_fileobj_from_s3(s3_key: str):
    """Download a file from S3 and return a BytesIO object."""
    import io
    client = get_s3_client()
    buf = io.BytesIO()
    client.download_fileobj(settings.S3_BUCKET_NAME, s3_key, buf)
    buf.seek(0)
    return buf


def generate_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Generate a pre-signed URL for temporary public access to an S3 object."""
    client = get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expiry_seconds,
    )
    return url


def delete_from_s3(s3_key: str) -> None:
    """Delete an object from S3."""
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except ClientError:
        pass
