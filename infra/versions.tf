terraform {
  required_version = "~> 1.16"

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
