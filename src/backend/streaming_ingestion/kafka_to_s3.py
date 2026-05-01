"""
Spark Structured Streaming : Kafka (MSK / local) → S3.

Voir doc détaillée dans le package `streaming_ingestion.__doc__` et variables d'environnement
documentées dans `kafka_to_s3.main`.

Pour EMR :
  spark-submit \\
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 \\
    kafka_to_s3.py

Sur EC2 (PySpark + IAM instance profile) : ``ec2_run.sh`` avec
``S3_OUTPUT_PATH`` / ``CHECKPOINT_LOCATION`` en ``s3://`` ou ``s3a://`` ;
``hadoop-aws`` est ajouté automatiquement à ``spark.jars.packages``.

Ne pas exporter PYSPARK_SUBMIT_ARGS pour ce script : une valeur incorrecte fait échouer
spark-submit (« Missing application resource ») puis JAVA_GATEWAY_EXITED.
Les JARs Kafka sont chargés via spark.jars.packages (voir SPARK_KAFKA_PACKAGES).

WARN hostname loopback : Spark peut afficher un avertissement si /etc/hosts mappe ton hostname
sur 127.0.1.1 ; en général il bascule sur l’IP LAN. Sinon : export SPARK_LOCAL_IP=<ton_ip>.
"""

from __future__ import annotations

import os


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return v


def _optional_env(name: str) -> str | None:
    v = os.getenv(name)
    return v if v else None


def _uses_s3(uri: str) -> bool:
    u = uri.strip().lower()
    return u.startswith("s3a://") or u.startswith("s3://")


def _normalize_storage_uri(uri: str) -> str:
    """Spark / Hadoop écrivent via le filesystem S3A ; ``s3://`` est mappé vers ``s3a://``."""
    u = uri.strip()
    low = u.lower()
    if low.startswith("s3://"):
        return "s3a://" + u[len("s3://") :]
    return u


def _merge_maven_coords(*groups: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for g in groups:
        for part in g.split(","):
            p = part.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    return ",".join(out)


def _spark_jars_packages(kafka_packages: str, output_path: str, checkpoint: str) -> str:
    override = os.getenv("SPARK_JARS_PACKAGES", "").strip()
    if override:
        return override
    extra = os.getenv("SPARK_EXTRA_PACKAGES", "")
    s3_coords = ""
    if _uses_s3(output_path) or _uses_s3(checkpoint):
        s3_coords = os.getenv(
            "SPARK_HADOOP_AWS_PACKAGES",
            "org.apache.hadoop:hadoop-aws:3.3.4",
        )
    return _merge_maven_coords(kafka_packages, s3_coords, extra)


def main() -> None:
    """
    Variables d'environnement principales :

      KAFKA_BOOTSTRAP_SERVERS   Brokers (ex: localhost:9092 ou MSK)
      KAFKA_TOPIC               Topic à consommer

      KAFKA_SET_GROUP_ID        true pour passer kafka.group.id (déconseillé en Structured Streaming :
                                les offsets sont dans le checkpoint Spark ; défaut: absent)

      KAFKA_GROUP_ID            Utilisé seulement si KAFKA_SET_GROUP_ID=true

      S3_OUTPUT_PATH            ex: s3a://bucket/raw/kafka/logs/
      CHECKPOINT_LOCATION       ex: s3a://bucket/checkpoints/kafka-logs/

      TRIGGER_INTERVAL          Défaut: 60 seconds
      STARTING_OFFSETS          latest | earliest (défaut: latest)

      KAFKA_SECURITY_PROTOCOL   PLAINTEXT | SASL_SSL | SSL
      KAFKA_SASL_MECHANISM      ex: SCRAM-SHA-512
      KAFKA_SASL_USERNAME       /
      KAFKA_SASL_PASSWORD       /

      STREAM_OUTPUT_FORMAT      parquet | json

      SPARK_KAFKA_PACKAGES      coord Maven du connecteur Kafka (défaut adapté Spark 3.5.x / Scala 2.12)

      SPARK_JARS_PACKAGES       si défini, remplace entièrement la liste Maven (Kafka + S3, etc.)

      SPARK_HADOOP_AWS_PACKAGES coord(s) Maven pour S3A (défaut: hadoop-aws 3.3.4), ajouté(s) si la sortie
                                ou le checkpoint est sur s3/s3a

      SPARK_EXTRA_PACKAGES      coords Maven supplémentaires, fusionnées avec les précédentes

      AWS_REGION / AWS_DEFAULT_REGION  propagées en fs.s3a.endpoint.region si présentes (EC2 / IAM)

      S3A_ENDPOINT              endpoint style compatible path (MinIO, LocalStack) → fs.s3a.endpoint

      S3A_PATH_STYLE_ACCESS     true|false pour endpoint custom (défaut: true si S3A_ENDPOINT est défini)

      SPARK_SESSION_TIMEZONE    fuseau Spark SQL (défaut: UTC, recommandé pour dt/hour sur EC2)
    """
    # PySpark démarre un JVM via spark-submit ; PYSPARK_SUBMIT_ARGS invalide casse le gateway.
    os.environ.pop("PYSPARK_SUBMIT_ARGS", None)

    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError as e:
        raise RuntimeError(
            "PySpark is required. Run on EMR/Glue or: pip install pyspark (dev only)."
        ) from e

    bootstrap = _env("KAFKA_BOOTSTRAP_SERVERS")
    topic = _env("KAFKA_TOPIC")
    output_path = _normalize_storage_uri(_env("S3_OUTPUT_PATH")).rstrip("/") + "/"
    checkpoint = _normalize_storage_uri(_env("CHECKPOINT_LOCATION")).rstrip("/") + "/"
    trigger = os.getenv("TRIGGER_INTERVAL", "60 seconds")
    starting_offsets = os.getenv("STARTING_OFFSETS", "latest")

    security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    sasl_mechanism = _optional_env("KAFKA_SASL_MECHANISM")
    sasl_username = _optional_env("KAFKA_SASL_USERNAME")
    sasl_password = _optional_env("KAFKA_SASL_PASSWORD")

    output_format = os.getenv("STREAM_OUTPUT_FORMAT", "parquet").lower()

    kafka_packages = os.getenv(
        "SPARK_KAFKA_PACKAGES",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
    )
    jars_packages = _spark_jars_packages(kafka_packages, output_path, checkpoint)

    builder = (
        SparkSession.builder.appName(os.getenv("SPARK_APP_NAME", "kafka-logs-to-s3"))
        .config("spark.jars.packages", jars_packages)
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"))
        .config(
            "spark.sql.session.timeZone",
            os.getenv("SPARK_SESSION_TIMEZONE", "UTC"),
        )
    )
    if _uses_s3(output_path) or _uses_s3(checkpoint):
        builder = builder.config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        region = _optional_env("AWS_REGION") or _optional_env("AWS_DEFAULT_REGION")
        if region:
            builder = builder.config("spark.hadoop.fs.s3a.endpoint.region", region)
        s3a_endpoint = _optional_env("S3A_ENDPOINT")
        if s3a_endpoint:
            builder = builder.config("spark.hadoop.fs.s3a.endpoint", s3a_endpoint)
            path_style = os.getenv("S3A_PATH_STYLE_ACCESS", "true").lower()
            builder = builder.config(
                "spark.hadoop.fs.s3a.path.style.access",
                "true" if path_style in ("1", "true", "yes") else "false",
            )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))

    reader = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", starting_offsets)
        .option("failOnDataLoss", os.getenv("KAFKA_FAIL_ON_DATA_LOSS", "false"))
    )

    if os.getenv("KAFKA_SET_GROUP_ID", "").lower() in ("1", "true", "yes"):
        gid = os.getenv("KAFKA_GROUP_ID", "").strip()
        if gid:
            reader = reader.option("kafka.group.id", gid)

    reader = reader.option("kafka.security.protocol", security_protocol)
    if security_protocol.upper().startswith("SASL") and sasl_mechanism:
        reader = reader.option("kafka.sasl.mechanism", sasl_mechanism)
        if sasl_username and sasl_password:
            reader = reader.option(
                "kafka.sasl.jaas.config",
                (
                    "org.apache.kafka.common.security.scram.ScramLoginModule required "
                    f'username="{sasl_username}" password="{sasl_password}";'
                ),
            )

    raw = reader.load()

    json_str = raw.select(
        F.col("timestamp").alias("kafka_ingest_ts"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.expr("CAST(value AS STRING)").alias("raw_json"),
    )

    event_ts = F.coalesce(
        F.get_json_object(F.col("raw_json"), "$.timestamp"),
        F.get_json_object(F.col("raw_json"), "$._source.timestamp"),
    )

    enriched = (
        json_str.withColumn("event_timestamp", event_ts)
        .withColumn(
            "dt",
            F.date_format(
                F.coalesce(
                    F.to_timestamp(F.col("event_timestamp")),
                    F.to_timestamp(F.col("kafka_ingest_ts")),
                ),
                "yyyy-MM-dd",
            ),
        )
        .withColumn(
            "hour",
            F.date_format(
                F.coalesce(
                    F.to_timestamp(F.col("event_timestamp")),
                    F.to_timestamp(F.col("kafka_ingest_ts")),
                ),
                "HH",
            ),
        )
    )

    out_df = enriched.select(
        "kafka_ingest_ts",
        "kafka_partition",
        "kafka_offset",
        "event_timestamp",
        "dt",
        "hour",
        "raw_json",
    )

    writer = (
        out_df.writeStream.outputMode("append")
        .option("checkpointLocation", checkpoint)
        .partitionBy("dt", "hour")
        .trigger(processingTime=trigger)
    )

    if output_format == "json":
        query = writer.format("json").option("path", output_path).start()
    elif output_format == "parquet":
        query = writer.format("parquet").option("path", output_path).start()
    else:
        raise RuntimeError(f"Unsupported STREAM_OUTPUT_FORMAT={output_format} (use parquet or json)")

    query.awaitTermination()


if __name__ == "__main__":
    main()
