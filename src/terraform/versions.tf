terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend distant (recommandé en prod) — décommenter après création du bucket tfstate :
  # backend "s3" {
  #   bucket         = "clair-obscur-tfstate"
  #   key            = "clair-obscur/s3/terraform.tfstate"
  #   region         = "eu-west-3"
  #   encrypt        = true
  #   dynamodb_table = "clair-obscur-tfstate-lock"
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile != "" ? var.aws_profile : null

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
