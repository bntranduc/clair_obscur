"""
Ingestion streaming (Kafka → lake S3, Spark Structured Streaming).

Modules :
  - ``kafka_to_s3`` : job Spark lecture topic Kafka, écriture Parquet/JSON partitionné sur S3.

Déploiement AWS typique :
  - EMR : ``spark-submit --packages ...`` sur ``kafka_to_s3.py``
  - EC2 : rôle IAM avec ``s3:PutObject`` / ``ListBucket`` sur le bucket ; variables
    ``S3_OUTPUT_PATH`` / ``CHECKPOINT_LOCATION`` en ``s3://`` ou ``s3a://`` ; script ``ec2_run.sh``

Les JARs S3A (``hadoop-aws``) sont ajoutés automatiquement si la sortie ou le checkpoint est sur S3.

Dev local : ``docker-compose.yml`` dans ce dossier pour Kafka + ZooKeeper.

spark-submit (EMR), exemple :
  spark-submit \\
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 \\
    /chemin/vers/src/backend/streaming_ingestion/kafka_to_s3.py
"""

from backend.streaming_ingestion.kafka_to_s3 import main as run_kafka_to_s3_stream

__all__ = ["run_kafka_to_s3_stream"]
