resource "aws_lb" "web" {
  name               = "${var.group_name}-alb"
  load_balancer_type = "application"
  internal           = false

  subnets         = data.aws_subnets.default.ids
  security_groups = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "web" {
  name     = "${var.group_name}-tg"
  port     = var.container_port
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  # Required for Fargate
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}