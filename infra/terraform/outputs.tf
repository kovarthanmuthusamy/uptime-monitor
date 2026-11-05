output "api_url" {
  description = "Base URL of the deployed dashboard/API (via the ALB)."
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL to push the image to."
  value       = aws_ecr_repository.main.repository_url
}

output "rds_endpoint" {
  description = "Endpoint of the RDS PostgreSQL instance."
  value       = aws_db_instance.main.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster running the API and worker services."
  value       = aws_ecs_cluster.main.name
}
