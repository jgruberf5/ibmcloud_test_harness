data "ibm_is_image" "tmos_image" {
    name = var.tmos_image_name
}

data "ibm_is_subnet" "f5_subnet" {
  identifier = var.subnet_id
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

// allow all traffic to data plane interfaces
// TMM is the firewall
resource "ibm_is_security_group" "f5_tmm_sg" {
  name = "sd-${random_uuid.namer.result}"
  vpc  = data.ibm_is_subnet.f5_subnet.vpc
}

// all TCP
resource "ibm_is_security_group_rule" "f5_tmm_in_tcp" {
  depends_on = [ibm_is_security_group.f5_tmm_sg]
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  tcp {
    port_min = 1
    port_max = 65535
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_tcp" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_in_tcp]
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  tcp {
    port_min = 1
    port_max = 65535
  }
}

// all UDP
resource "ibm_is_security_group_rule" "f5_tmm_in_udp" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_out_tcp]
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  udp {
    port_min = 1
    port_max = 65535
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_udp" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_in_udp]  
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  udp {
    port_min = 1
    port_max = 65535
  }
}

// all ICMP
resource "ibm_is_security_group_rule" "f5_tmm_in_icmp" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_out_udp] 
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  icmp {
    type = 8
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_icmp" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_in_icmp]
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  icmp {
    type = 0
  }
}

resource "ibm_is_instance" "f5_ve_instance" {
  depends_on = [ibm_is_security_group_rule.f5_tmm_out_icmp]
  name    = var.instance_name
  image   = data.ibm_is_image.tmos_image.id
  profile = data.ibm_is_instance_profile.instance_profile.id
  primary_network_interface {
    name            = "tmm-1nic"
    subnet          = data.ibm_is_subnet.f5_subnet.id
    security_groups = [ibm_is_security_group.f5_tmm_sg.id]
  }
  vpc  = data.ibm_is_subnet.f5_subnet.vpc
  zone = data.ibm_is_subnet.f5_subnet.zone
  keys = [data.ibm_is_ssh_key.f5_ssh_pub_key.id]
  user_data = data.template_file.user_data.rendered
}

# create floating IPs
resource "ibm_is_floating_ip" "f5_management_floating_ip" {
  name   = "f0-${random_uuid.namer.result}"
  target = ibm_is_instance.f5_ve_instance.primary_network_interface.0.id
}

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
  value = "https://${ibm_is_floating_ip.f5_management_floating_ip.address}:8443"
}

output "f5_as_url" {
  value = "https://${ibm_is_floating_ip.f5_management_floating_ip.address}:8443/mgmt/shared/appsvcs/declare"
}

output "test_type" {
  value = var.test_type
}
