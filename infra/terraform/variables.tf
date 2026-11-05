variable "project_name" {
  description = "Name prefix for all resources."
  type        = string
  default     = "uptime-monitor"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-central-1"
}

variable "image_tag" {
  description = "Tag of the container image in ECR to deploy."
  type        = string
  default     = "latest"
}

variable "container_port" {
  description = "Port the API container listens on."
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units (256, 512, 1024, ...)."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Number of API tasks the ECS service should run."
  type        = number
  default     = 1
}

variable "worker_tick_seconds" {
  description = "How often the worker wakes up to look for due monitors."
  type        = number
  default     = 5
}

variable "db_instance_class" {
  description = "RDS instance class for PostgreSQL."
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Name of the PostgreSQL database to create."
  type        = string
  default     = "uptime"
}

variable "db_username" {
  description = "Master username for the RDS instance."
  type        = string
  default     = "uptime"
}

# CHANGE_ME: supply the database password at apply time, e.g.
#   TF_VAR_db_password='...' terraform apply
# or via a gitignored terraform.tfvars file. Never commit a real password.
variable "db_password" {
  description = "Master password for the RDS instance (supplied out-of-band)."
  type        = string
  sensitive   = true
}
