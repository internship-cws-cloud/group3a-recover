terraform {
  required_version = "~> 1.16"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Deliberately no backend block.
  # Bootstrap state remains local.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Group     = var.group_name
      ManagedBy = "terraform"
    }
  }
}

variable "region" {
  type = string
}

variable "group_name" {
  type = string
}

variable "github_org" {
  type = string
}

variable "github_repo" {
  type = string
}

data "aws_caller_identity" "me" {}

# --------------------------------------------------
# S3 BUCKET FOR TERRAFORM STATE
# --------------------------------------------------

resource "aws_s3_bucket" "state" {
  bucket = "${var.group_name}-tfstate-${data.aws_caller_identity.me.account_id}"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --------------------------------------------------
# DYNAMODB STATE-LOCKING TABLE
# --------------------------------------------------

resource "aws_dynamodb_table" "lock" {
  name         = "${var.group_name}-tflock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# --------------------------------------------------
# GITHUB OIDC PROVIDER
# --------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]
}

locals {
  repo = "${var.github_org}/${var.github_repo}"
}

# --------------------------------------------------
# PLAN ROLE TRUST POLICY
# Only pull-request workflows in this repository.
# --------------------------------------------------

data "aws_iam_policy_document" "plan_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"

      identifiers = [
        aws_iam_openid_connect_provider.github.arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"

      values = [
        "sts.amazonaws.com"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${local.repo}:pull_request"
      ]
    }
  }
}

resource "aws_iam_role" "plan" {
  name               = "${var.group_name}-gha-plan"
  assume_role_policy = data.aws_iam_policy_document.plan_trust.json
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# --------------------------------------------------
# DEPLOY ROLE TRUST POLICY
# Only the main branch in this repository.
# --------------------------------------------------

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type = "Federated"

      identifiers = [
        aws_iam_openid_connect_provider.github.arn
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"

      values = [
        "sts.amazonaws.com"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${local.repo}:ref:refs/heads/main"
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${var.group_name}-gha-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
}

# The Week 4 manual uses AdministratorAccess for this exercise.
# This is intentionally broad and must be documented as a weakness.

resource "aws_iam_role_policy_attachment" "deploy_admin" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# --------------------------------------------------
# OUTPUTS
# --------------------------------------------------

output "state_bucket_name" {
  value = aws_s3_bucket.state.bucket
}

output "lock_table_name" {
  value = aws_dynamodb_table.lock.name
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}