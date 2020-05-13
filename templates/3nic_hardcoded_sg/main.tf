data "ibm_is_image" "tmos_image" {
    name = var.tmos_image_name
}

data "ibm_is_subnet" "f5_management" {
  identifier = var.management_subnet_id
}

data "ibm_is_subnet" "f5_internal" {
  identifier = var.internal_subnet_id
}

data "ibm_is_subnet" "f5_external" {
  identifier = var.external_subnet_id
}

data "ibm_is_ssh_key" "f5_ssh_pub_key" {
  name = var.ssh_key_name
}

data "ibm_is_instance_profile" "instance_profile" {
  name = var.instance_profile
}

data "template_file" "user_data" {
  template = "${file("${path.module}/user_data.yaml")}"
  vars = {
    tmos_admin_password = var.tmos_admin_password
    tmos_license_basekey = var.tmos_license_basekey
    phone_home_url = var.phone_home_url
  }
}

resource "random_uuid" "namer" { }

resource "ibm_is_instance" "f5_ve_instance" {
  name    = var.instance_name
  image   = data.ibm_is_image.tmos_image.id
  profile = data.ibm_is_instance_profile.instance_profile.id
  primary_network_interface {
    name            = "management"
    subnet          = data.ibm_is_subnet.f5_management.id
    security_groups = [var.f5_wide_open_sg]
  }
  network_interfaces {
    name            = "tmm-1-1-internal"
    subnet          = data.ibm_is_subnet.f5_internal.id
    security_groups = [var.f5_wide_open_sg]
  }
  network_interfaces {
    name            = "tmm-1-2-external"
    subnet          = data.ibm_is_subnet.f5_external.id
    security_groups = [var.f5_wide_open_sg]
  }
  vpc  = data.ibm_is_subnet.f5_management.vpc
  zone = data.ibm_is_subnet.f5_management.zone
  keys = [data.ibm_is_ssh_key.f5_ssh_pub_key.id]
  user_data = data.template_file.user_data.rendered
}

# create floating IPs
resource "ibm_is_floating_ip" "f5_management_floating_ip" {
  name   = "f0-${random_uuid.namer.result}"
  target = ibm_is_instance.f5_ve_instance.primary_network_interface.0.id
}

#resource "ibm_is_floating_ip" "f5_external_floating_ip" {
#  name   = "external-floating-ip"
#  target = ibm_is_instance.f5_ve_instance.network_interfaces.1.id
#  depends_on = [ibm_is_instance.f5_ve_instance, ibm_is_floating_ip.f5_management_floating_ip]
#}

output "resource_name" {
  value = ibm_is_instance.f5_ve_instance.name
}

output "resource_status" {
  value = ibm_is_instance.f5_ve_instance.status
}

output "VPC" {
  value = ibm_is_instance.f5_ve_instance.vpc
}

output "f5_shell_access" {
  value = "ssh://root@${ibm_is_floating_ip.f5_management_floating_ip.address}"
}


output "f5_admin_portal" {
  value = "https://${ibm_is_floating_ip.f5_management_floating_ip.address}"
}

output "f5_as_url" {
  value = "https://${ibm_is_floating_ip.f5_management_floating_ip.address}/mgmt/shared/appsvcs/declare"
}

output "test_type" {
  value = var.test_type
}
