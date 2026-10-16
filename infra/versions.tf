terraform {
  required_version = "~> 1.16"

    # Remote backend for Terraform state
  backend "s3" {
    bucket         = "group3a-tfstate-706967260509"
    key            = "infra/terraform.tfstate"
    region         = "eu-north-1"
    dynamodb_table = "group3a-tflock"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region

  # Every resource gets these tags without you writing them each time.
  # The Group tag is what makes per-group cost reporting possible.
  default_tags {
    tags = {
      Group     = var.group_name
      Programme = "cloud-internship"
      ManagedBy = "terraform"
    }
  }
}
