# RDS needs to be told which subnets it may live in.
resource "aws_db_subnet_group" "db" {
  name       = "${var.group_name}-db"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "tasks" {
  identifier     = "${var.group_name}-tasks"
  engine         = "postgres"
  engine_version = "16"

  # the smallest and cheapest that exists. Do not change this.
  instance_class    = "db.t4g.micro"
  allocated_storage = 20

  db_name  = "tasks"
  username = "tasks"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]

  # not reachable from the internet, only from inside the VPC
  publicly_accessible = false
  multi_az            = false

  # week 3 only. The Recover it groups will change both of these.
  backup_retention_period = 0
  skip_final_snapshot     = true
}
