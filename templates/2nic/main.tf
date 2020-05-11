data "ibm_is_image" "tmos_image" {
    name = var.tmos_image_name
}

data "ibm_is_subnet" "f5_management" {
  identifier = var.management_subnet_id
}

data "ibm_is_subnet" "f5_data" {
  identifier = var.data_subnet_id
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

# create F5 control plane firewalling
# https://support.f5.com/csp/article/K46122561
resource "ibm_is_security_group" "f5_management_sg" {
  name = "f5-management-sg"
  vpc  = data.ibm_is_subnet.f5_management.vpc
}

resource "ibm_is_security_group_rule" "f5_management_in_icmp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  icmp {
    type = 8
  }
}

resource "ibm_is_security_group_rule" "f5_management_in_ssh" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  tcp {
    port_min = 22
    port_max = 22
  }
}
resource "ibm_is_security_group_rule" "f5_management_in_https" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  tcp {
    port_min = 443
    port_max = 443
  }
}
resource "ibm_is_security_group_rule" "f5_management_in_snmp_tcp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  tcp {
    port_min = 161
    port_max = 161
  }
}
resource "ibm_is_security_group_rule" "f5_management_in_snmp_udp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  udp {
    port_min = 161
    port_max = 161
  }
}
resource "ibm_is_security_group_rule" "f5_management_in_ha" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  udp {
    port_min = 1026
    port_max = 1026
  }
}

resource "ibm_is_security_group_rule" "f5_management_in_iquery" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "inbound"
  tcp {
    port_min = 4353
    port_max = 4353
  }
}

// allow all outbound on control plane
// all TCP
resource "ibm_is_security_group_rule" "f5_management_out_tcp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "outbound"
  tcp {
    port_min = 1
    port_max = 65535
  }
}

// all outbound UDP
resource "ibm_is_security_group_rule" "f5_management_out_udp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "outbound"
  udp {
    port_min = 1
    port_max = 65535
  }
}

// all ICMP
resource "ibm_is_security_group_rule" "f5_management_out_icmp" {
  group     = ibm_is_security_group.f5_management_sg.id
  direction = "outbound"
  icmp {
    type = 0
  }
}

// allow all traffic to data plane interfaces
// TMM is the firewall
resource "ibm_is_security_group" "f5_tmm_sg" {
  name = "f5-tmm-sg"
  vpc  = data.ibm_is_subnet.f5_management.vpc
}

// all TCP
resource "ibm_is_security_group_rule" "f5_tmm_in_tcp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  tcp {
    port_min = 1
    port_max = 65535
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_tcp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  tcp {
    port_min = 1
    port_max = 65535
  }
}

// all UDP
resource "ibm_is_security_group_rule" "f5_tmm_in_udp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  udp {
    port_min = 1
    port_max = 65535
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_udp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  udp {
    port_min = 1
    port_max = 65535
  }
}

// all ICMP
resource "ibm_is_security_group_rule" "f5_tmm_in_icmp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "inbound"
  icmp {
    type = 8
  }
}

resource "ibm_is_security_group_rule" "f5_tmm_out_icmp" {
  group     = ibm_is_security_group.f5_tmm_sg.id
  direction = "outbound"
  icmp {
    type = 0
  }
}

resource "ibm_is_instance" "f5_ve_instance" {
  name    = var.instance_name
  image   = data.ibm_is_image.tmos_image.id
  profile = data.ibm_is_instance_profile.instance_profile.id
  primary_network_interface {
    name            = "management"
    subnet          = data.ibm_is_subnet.f5_management.id
    security_groups = [ibm_is_security_group.f5_management_sg.id]
  }
  network_interfaces {
    name            = "tmm-1-1-data"
    subnet          = data.ibm_is_subnet.f5_data.id
    security_groups = [ibm_is_security_group.f5_tmm_sg.id]
  }
  vpc  = data.ibm_is_subnet.f5_management.vpc
  zone = data.ibm_is_subnet.f5_management.zone
  keys = [data.ibm_is_ssh_key.f5_ssh_pub_key.id]
  user_data = data.template_file.user_data.rendered
}

# create floating IPs
resource "ibm_is_floating_ip" "f5_management_floating_ip" {
  name   = "management-floating-ip"
  target = ibm_is_instance.f5_ve_instance.primary_network_interface.0.id
}

#resource "ibm_is_floating_ip" "f5_data_floating_ip" {
#  name   = "data-floating-ip"
#  target = ibm_is_instance.f5_ve_instance.network_interfaces.0.id
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
  value = "ssh://root@${ibm_is_floating_ip.f5_management_ip.address}"
}

output "f5_admin_portal" {
  value = "https://${ibm_is_floating_ip.f5_management_ip.address}"
}

output "f5_as_url" {
  value = "https://${ibm_is_floating_ip.f5_management_ip.address}/mgmt/shared/appsvcs/declare"
}

output "test_type" {
  value = var.test_type
}
