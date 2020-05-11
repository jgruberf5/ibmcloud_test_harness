variable "api_key" {
  default=""
}

variable "region" {
  default=""
  description = "The region where the F5 BIG-IP instance is to be provisioned. To list available regions, run `ibmcloud is regions`. Supported regions are eu-de, eu-gb, us-south, us-east "
}

variable "generation" {
  default     = 2
  description = "The VPC Generation to target. Valid values are 2 or 1."
}

provider "ibm" {
  ibmcloud_api_key      = var.api_key
  generation            = var.generation 
  region                = var.region
  ibmcloud_timeout      = 300
}
