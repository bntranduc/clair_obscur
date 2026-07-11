# --- EC2 worker : git clone + Docker ---

data "aws_vpc" "default" {
  count = var.enable_ec2_worker ? 1 : 0

  default = true
}

data "aws_subnets" "default" {
  count = var.enable_ec2_worker ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
}

data "aws_ami" "amazon_linux_2023" {
  count = var.enable_ec2_worker ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-6.1-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "predict_worker" {
  count = var.enable_ec2_worker ? 1 : 0

  name        = "${var.project_name}-${local.account_suffix}-predict-worker"
  description = "SQS predict worker - egress only, admin via SSM"
  vpc_id      = data.aws_vpc.default[0].id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-predict-worker"
  }
}

resource "aws_iam_role" "predict_worker" {
  count = var.enable_ec2_worker ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-predict-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "predict_worker" {
  count = var.enable_ec2_worker ? 1 : 0

  name = "predict-worker"
  role = aws_iam_role.predict_worker[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = module.predict_queue.queue_arn
      },
      {
        Sid    = "S3LogsRead"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          module.raw_logs.bucket_arn,
          "${module.raw_logs.bucket_arn}/*",
        ]
      },
      {
        Sid    = "S3PredictionsWrite"
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          module.predictions.bucket_arn,
          "${module.predictions.bucket_arn}/*",
        ]
      },
      {
        Sid      = "BedrockInvoke"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBAlertsWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable",
        ]
        Resource = [
          module.alerts.table_arn,
          "${module.alerts.table_arn}/index/*",
        ]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "predict_worker_ssm" {
  count = var.enable_ec2_worker ? 1 : 0

  role       = aws_iam_role.predict_worker[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "predict_worker" {
  count = var.enable_ec2_worker ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-predict-worker"
  role = aws_iam_role.predict_worker[0].name
}

resource "aws_instance" "predict_worker" {
  count = var.enable_ec2_worker ? 1 : 0

  ami                         = data.aws_ami.amazon_linux_2023[0].id
  instance_type               = var.worker_instance_type
  subnet_id                   = tolist(data.aws_subnets.default[0].ids)[0]
  vpc_security_group_ids      = [aws_security_group.predict_worker[0].id]
  iam_instance_profile        = aws_iam_instance_profile.predict_worker[0].name
  key_name                    = var.worker_key_name != "" ? var.worker_key_name : null
  associate_public_ip_address = true
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/templates/worker-user-data.sh.tpl", {
    aws_region             = var.aws_region
    git_repo_url           = var.worker_git_repo_url
    git_ref                = var.worker_git_ref
    raw_logs_bucket        = module.raw_logs.bucket_id
    raw_logs_prefix        = "${var.raw_logs_prefix}/"
    predictions_bucket     = module.predictions.bucket_id
    predictions_prefix     = "${var.predictions_prefix}/"
    sqs_queue_url           = module.predict_queue.queue_url
    sqs_visibility_timeout = var.sqs_visibility_timeout_seconds
    bedrock_model_id       = var.worker_bedrock_model_id
    dynamodb_alerts_table  = module.alerts.table_name
    dynamodb_alerts_pk     = local.dynamodb_alerts_default_pk
  })

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-predict-worker"
  }
}
