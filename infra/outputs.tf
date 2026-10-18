```hcl
output "alb_url" {
  description = "URL of the Task Tracker Application Load Balancer"
  value       = "http://${aws_lb.web.dns_name}"
}

output "db_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.tasks.address
}
