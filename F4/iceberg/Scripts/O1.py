"""O1: spazio occupato su MinIO (file fisici, anche eventualmente orfani).
Misurazione include paginazione S3 MinIO. Richiede boto3.
"""
import time
import boto3
from common import (run, NAMESPACE, MINIO_ENDPOINT, MINIO_ACCESS_KEY,
                    MINIO_SECRET_KEY, MINIO_REGION, BUCKET, MINIO_FOLDERS, TABLES)


def execute():
    client = boto3.client('s3', endpoint_url=MINIO_ENDPOINT,
                          aws_access_key_id=MINIO_ACCESS_KEY,
                          aws_secret_access_key=MINIO_SECRET_KEY,
                          region_name=MINIO_REGION)
    out = {}
    for tag in TABLES:
        table = MINIO_FOLDERS[tag]
        prefix = f'{NAMESPACE}/{table}/'
        start = time.perf_counter()
        file_count, byte_count = 0, 0
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=BUCKET, Prefix=prefix):
            for item in page.get('Contents', []):
                file_count += 1
                byte_count += item['Size']
        out[tag] = {'bucket': BUCKET, 'prefix': prefix, 'numero_oggetti': file_count,
                    'byte': byte_count, 'MiB': round(byte_count / 1024**2, 3),
                    'tempo_secondi': round(time.perf_counter()-start, 6)}
    return out


if __name__ == '__main__':
    run('O1', execute)
