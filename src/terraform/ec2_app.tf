# --- EC2 app : API FastAPI + frontend Next.js (docker compose prod) ---

data "aws_vpc" "app" {
  count = var.enable_ec2_app ? 1 : 0

  default = true
}

data "aws_subnets" "app" {
  count = var.enable_ec2_app ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.app[0].id]
  }
}

data "aws_ami" "app_amazon_linux_2023" {
  count = var.enable_ec2_app ? 1 : 0

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

resource "aws_security_group" "app" {
  count = var.enable_ec2_app ? 1 : 0

  name        = "${var.project_name}-${local.account_suffix}-app"
  description = "API 8020 + frontend 3000"
  vpc_id      = data.aws_vpc.app[0].id

  ingress {
    from_port   = 8020
    to_port     = 8020
    protocol    = "tcp"
    cidr_blocks = var.app_ingress_cidr_blocks
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = var.app_ingress_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-app"
  }
}

resource "aws_iam_role" "app" {
  count = var.enable_ec2_app ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-app"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "app" {
  count = var.enable_ec2_app ? 1 : 0

  name = "app-api"
  role = aws_iam_role.app[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBRead"
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:DescribeTable",
        ]
        Resource = [
          module.normalized_logs.table_arn,
          "${module.normalized_logs.table_arn}/index/*",
        ]
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
        Sid    = "S3PredictionsRead"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
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
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app_ssm" {
  count = var.enable_ec2_app ? 1 : 0

  role       = aws_iam_role.app[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "app" {
  count = var.enable_ec2_app ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-app"
  role = aws_iam_role.app[0].name
}

resource "aws_instance" "app" {
  count = var.enable_ec2_app ? 1 : 0

  ami                         = data.aws_ami.app_amazon_linux_2023[0].id
  instance_type               = var.app_instance_type
  subnet_id                   = tolist(data.aws_subnets.app[0].ids)[0]
  vpc_security_group_ids      = [aws_security_group.app[0].id]
  iam_instance_profile        = aws_iam_instance_profile.app[0].name
  key_name                    = var.worker_key_name != "" ? var.worker_key_name : null
  associate_public_ip_address = true
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/templates/app-user-data.sh.tpl", {
    aws_region         = var.aws_region
    git_repo_url       = var.worker_git_repo_url
    git_ref            = var.worker_git_ref
    raw_logs_bucket    = module.raw_logs.bucket_id
    raw_logs_prefix    = "${var.raw_logs_prefix}/"
    predictions_bucket = module.predictions.bucket_id
    predictions_prefix = "${var.predictions_prefix}/"
    dynamodb_table     = module.normalized_logs.table_name
    dynamodb_pk        = local.dynamodb_default_pk
    bedrock_model_id   = var.worker_bedrock_model_id
  })

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-app"
  }
}
