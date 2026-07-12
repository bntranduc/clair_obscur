# --- EC2 VM fraîche : test du flux vm_setup/connect.sh (sans agent préinstallé) ---

resource "aws_security_group" "fresh_vm" {
  count = var.enable_ec2_fresh_vm ? 1 : 0

  name        = "${var.project_name}-${local.account_suffix}-fresh-vm"
  description = "Fresh VM vm_setup test - nginx 8080 after connect.sh"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "nginx demo (attaques)"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = var.fresh_vm_ingress_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-fresh-vm"
  }
}

resource "aws_iam_role" "fresh_vm" {
  count = var.enable_ec2_fresh_vm ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-fresh-vm"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "fresh_vm_ssm" {
  count = var.enable_ec2_fresh_vm ? 1 : 0

  role       = aws_iam_role.fresh_vm[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "fresh_vm" {
  count = var.enable_ec2_fresh_vm ? 1 : 0

  name = "${var.project_name}-${local.account_suffix}-fresh-vm"
  role = aws_iam_role.fresh_vm[0].name
}

resource "aws_instance" "fresh_vm" {
  count = var.enable_ec2_fresh_vm ? 1 : 0

  ami                          = data.aws_ami.amazon_linux_2023.id
  instance_type                = var.fresh_vm_instance_type
  subnet_id                    = tolist(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids       = [aws_security_group.fresh_vm[0].id]
  iam_instance_profile         = aws_iam_instance_profile.fresh_vm[0].name
  associate_public_ip_address  = true
  user_data_replace_on_change  = true

  user_data = templatefile("${path.module}/templates/fresh-vm-user-data.sh.tpl", {
    git_repo_url = var.worker_git_repo_url
    git_ref      = var.worker_git_ref
  })

  root_block_device {
    volume_size = 12
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-${local.account_suffix}-fresh-vm"
    Role = "clair-vm-fresh-test"
  }
}
