import boto3
from botocore.exceptions import ClientError
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            config=boto3.session.Config(signature_version=settings.s3_signature_version)
        )
        self.bucket_name = settings.aws_bucket_name

    def generate_presigned_post(self, object_name, fields=None, conditions=None, expiration=3600):
        """Generate a presigned URL S3 POST request to upload a file"""
        try:
            response = self.client.generate_presigned_post(
                self.bucket_name,
                object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Error generating presigned upload URL: {e}")
            return None

    def upload_file(self, file_obj, object_name, content_type=None):
        """Upload a file to an S3 bucket"""
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )
            
            # Construct URL - always return complete URL with https://
            if settings.cloudfront_url:
                # Ensure no double slashes
                base_url = settings.cloudfront_url.rstrip('/')
                # Ensure URL starts with https://
                if not base_url.startswith(('http://', 'https://')):
                    base_url = f"https://{base_url}"
                url = f"{base_url}/{object_name}"
            else:
                # Fallback to S3 URL (always has https://)
                url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}"
                
            return url
        except ClientError as e:
            logger.error(f"Error uploading file: {e}")
            return None

    def generate_presigned_url(self, object_name, expiration=3600):
        """Generate a presigned URL to share an S3 object"""
        try:
            response = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Error generating presigned view URL: {e}")
            return None

    def delete_file(self, object_name):
        """Delete a file from an S3 bucket"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            logger.error(f"Error deleting file: {e}")
            return False

# Singleton instance
try:
    s3_client = S3Client()
except Exception as e:
    logger.warning(f"Failed to initialize S3 client: {e}")
    s3_client = None
