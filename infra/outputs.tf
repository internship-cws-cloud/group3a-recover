output "app_url" {
  description = "Open this URL in a browser"
  value       = "http://${aws_lb.web.dns_name}"
}

output "db_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.tasks.address
}
