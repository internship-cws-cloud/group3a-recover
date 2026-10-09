variable "region" {
  description = "AWS region. Everyone in the cohort uses the same one."
  type        = string
}

variable "group_name" {
  description = "3arecoverit"
  type        = string
  # keep it short - some AWS names have a 32 character limit
}

variable "image_tag" {
  description = "Which image tag in ECR to deploy"
  type        = string
  default     = "v1"
}

variable "container_port" {
  type    = number
  default = 8080
}

variable "db_password" {
  description = "Database password. Comes from terraform.tfvars, never from here."
  type        = string
  sensitive   = true
}
