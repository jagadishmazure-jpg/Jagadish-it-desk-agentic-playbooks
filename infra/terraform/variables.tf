variable "env" {
  description = "Environment name (dev or prod)."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus2"
}

variable "prefix" {
  description = "Short lowercase name prefix (3-10 letters or digits)."
  type        = string
  default     = "itdesk"
  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.prefix))
    error_message = "prefix must be 3-10 lowercase letters or digits."
  }
}

variable "log_retention_days" {
  description = "Log Analytics retention."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags on every resource."
  type        = map(string)
  default = {
    workload = "it-desk-agent"
    owner    = "ops-platform"
    data     = "synthetic"
  }
}
