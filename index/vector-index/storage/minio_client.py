"""MinIO 클라이언트"""
import logging
from io import BytesIO
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    """MinIO 클라이언트 래퍼"""
    
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        self._ensure_buckets()
    
    def _ensure_buckets(self):
        """필요한 버킷이 존재하는지 확인하고 없으면 생성"""
        bucket = settings.minio_bucket
        try:
            # bucket_exists 대신 list_objects를 사용 (ListBucket 권한 활용)
            objects = self.client.list_objects(bucket, prefix="", recursive=False)
            next(objects, None)  # 첫 번째 객체만 가져와서 버킷 존재 확인
            logger.debug(f"버킷 확인 완료: {bucket}")
        except S3Error as e:
            if e.code == 'NoSuchBucket':
                self.client.make_bucket(bucket)
                logger.info(f"버킷 생성: {bucket}")
            elif e.code == 'AccessDenied':
                # 버킷은 존재하지만 HeadBucket 권한이 없는 경우 - 무시하고 진행
                logger.warning(f"버킷 존재 확인 불가 (권한 부족), 버킷이 존재한다고 가정: {bucket}")
            else:
                raise
        except StopIteration:
            # 버킷은 존재하지만 비어있는 경우
            logger.debug(f"버킷 확인 완료 (비어있음): {bucket}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def download_object(self, bucket: str, object_key: str) -> bytes:
        """객체 다운로드"""
        try:
            response = self.client.get_object(bucket, object_key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"MinIO 다운로드 실패: {bucket}/{object_key}, 에러: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upload_object(
        self,
        bucket: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """객체 업로드"""
        try:
            data_stream = BytesIO(data)
            self.client.put_object(
                bucket,
                object_key,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.debug(f"MinIO 업로드 완료: {bucket}/{object_key}")
            return object_key
        except S3Error as e:
            logger.error(f"MinIO 업로드 실패: {bucket}/{object_key}, 에러: {e}")
            raise
    
    def get_object_metadata(self, bucket: str, object_key: str) -> Optional[dict]:
        """객체 메타데이터 조회"""
        try:
            stat = self.client.stat_object(bucket, object_key)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
            }
        except S3Error as e:
            logger.error(f"MinIO 메타데이터 조회 실패: {bucket}/{object_key}, 에러: {e}")
            return None
    
    def object_exists(self, bucket: str, object_key: str) -> bool:
        """객체 존재 여부 확인"""
        try:
            self.client.stat_object(bucket, object_key)
            return True
        except S3Error:
            return False






