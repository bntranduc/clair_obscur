# --- EC2 VM démo : capteur logs + cible d'attaques factices ---

data "aws_vpc" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  default = true
}

data "aws_subnets" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.demo_vm[0].id]
  }
}

data "aws_ami" "demo_vm_amazon_linux_2023" {
  count = var.enable_ec2_demo_vm ? 1 : 0

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

resource "aws_security_group" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  name        = "${var.project_name}-${local.account_suffix}-demo-vm"
  description = "VM capteur - egress + nginx local 8080"
  vpc_id      = data.aws_vpc.demo_vm[0].id

  ingress {
    description = "nginx demo (attaques locales / LAN)"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = var.demo_vm_ingress_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-demo-vm"
  }
}

resource "aws_iam_role" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-demo-vm"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "demo_vm_s3_ship" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  name = "vm-log-shipper"
  role = aws_iam_role.demo_vm[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "S3ShipVMLogs"
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:PutObjectAcl"]
      Resource = "${module.raw_logs.bucket_arn}/${var.raw_logs_prefix}/vms/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "demo_vm_ssm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  role       = aws_iam_role.demo_vm[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-demo-vm"
  role = aws_iam_role.demo_vm[0].name
}

resource "aws_instance" "demo_vm" {
  count = var.enable_ec2_demo_vm ? 1 : 0

  ami                         = data.aws_ami.demo_vm_amazon_linux_2023[0].id
  instance_type               = var.demo_vm_instance_type
  subnet_id                   = tolist(data.aws_subnets.demo_vm[0].ids)[0]
  vpc_security_group_ids      = [aws_security_group.demo_vm[0].id]
  iam_instance_profile        = aws_iam_instance_profile.demo_vm[0].name
  associate_public_ip_address = true
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/templates/demo-vm-user-data.sh.tpl", {
    aws_region      = var.aws_region
    git_repo_url    = var.worker_git_repo_url
    git_ref         = var.worker_git_ref
    raw_logs_bucket = module.raw_logs.bucket_id
    raw_logs_prefix = "${var.raw_logs_prefix}/"
  })

  root_block_device {
    volume_size = 12
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-demo-vm"
    Role = "clair-vm-sensor"
  }
}
