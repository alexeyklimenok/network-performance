#!/usr/bin/env python
from novaclient.v1_1 import client as novacli
from keystoneclient.v2_0 import client as keystonecli
from neutronclient.neutron import client as neutroncli
#from neutron.agent.netns_cleanup_util import main as neutron_netns_cleanup

from paramiko import MissingHostKeyPolicy, SSHClient
from time import sleep

import json
import sys

## CONST
PROTO_NAME_TCP = 'tcp'
PROTO_NAME_ICMP = 'icmp'
IPv4 = 'IPv4'

#THIS SHOULD BE ADMIN CREDENTIALS
OS_USERNAME = 'admin'
OS_PASSWORD = 'admin'
OS_TENANT = 'admin'
OS_AUTH_URL = 'http://10.119.192.11:5000/v2.0/'
OS_TOKEN = 'vDgyUPEp'
OS_SERVICE_ENDPOINT = 'http://10.119.192.11:35357/v2.0/'

#VM SSH CREDENTIALS
VM_USERNAME = 'root'
VM_PASSWORD = 'Mirantis01'

#OPENSTACK INFO
MGMT_NET = '993bfea7-30fd-4421-ba14-c3a279ab246f'
IMAGE_ID = '3da4853e-09c8-46b9-901a-4599e103970b'
FLAVOR_ID = 2

#OBJECT PREFIX
TENANT_PREFIX = 'test-'
VM_PREFIX = 'test-'
NETWORK_PREFIX = 'test-'
CIDR_PREFIX = '192.168'

keystone_connection = keystonecli.Client(token=OS_TOKEN,endpoint=OS_SERVICE_ENDPOINT)
#keystone_connection = keystonecli.Client(username=OS_USERNAME, password=OS_PASSWORD, tenant_name=OS_TENANT, auth_url=OS_AUTH_URL)
nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, OS_TENANT, OS_AUTH_URL)
neutron_connection = neutroncli.Client('2.0', auth_url=OS_AUTH_URL, username=OS_USERNAME, password=OS_PASSWORD, tenant_name=OS_TENANT)

def setup_iperf_pair(server, client, **kwargs):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(MissingHostKeyPolicy())
    
    ssh.connect(server, username=VM_USERNAME, password=VM_PASSWORD)
    #ssh_server.connect(server.networks.values()[-1], username=VM_USERNAME, password=VM_PASSWORD)
    ssh.exec_command('/usr/local/bin/iperf3 -s -D')

    ssh.connect(client, username=VM_USERNAME, password=VM_PASSWORD)
    #ssh_client.connect(client.networks.values()[-1], username=VM_USERNAME, password=VM_PASSWORD)
    stdin, stdout, stderr = ssh.exec_command('/usr/local/bin/iperf3 -c %s -J' % server)
    #stdin, stdout, stderr = ssh.exec_command('/usr/local/bin/iperf3 -c %s -J' % server.networks.values()[-1])

    rawdata = stdout.read()
    data = json.loads(rawdata.translate(None,'\t').translate(None,'\n'))

    return data

def run_test():
    for tenant in keystone_connection.tenants.list():
        if tenant.name.startswith(TENANT_PREFIX):
            tenant_nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, tenant.name, OS_AUTH_URL)
            vms = iter(tenant_nova_connection.servers.list())
            for vm in vms:
                try:
                    server = vm
                    client = next(vms)
                    setup_iperf_pair(server, client)
                except:
                    break

def make_environment(tenants_num=0, networks_per_tenant=1, vms_per_network=2):
    octet = 115
    vm_inc = 11
    image = nova_connection.images.get(IMAGE_ID)
    flavor = nova_connection.flavors.get(FLAVOR_ID)
    admin_user_id = keystone_connection.users.find(name=OS_USERNAME).id
    member_role_id = keystone_connection.roles.find(name='Member').id
    create_security_rules = True
    for num_tenant in range(1, tenants_num+1):
        tenant = keystone_connection.tenants.create('%stenant%s' % (TENANT_PREFIX, num_tenant))
        keystone_connection.roles.add_user_role(admin_user_id, member_role_id, tenant=tenant.id)
        for num_network in range(networks_per_tenant):
            network_json = {'name': '%snet%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                            'admin_state_up': True,
                            'tenant_id': tenant.id}
            network = neutron_connection.create_network({'network': network_json})
            subnet_json = {'name': '%ssubnet%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                           'network_id': network['network']['id'],
                           'tenant_id': tenant.id,
                           'enable_dhcp': True,
                           'cidr': '%s.%s.0/24' % (CIDR_PREFIX, octet), 'ip_version': 4}
            octet += 1
            subnet = neutron_connection.create_subnet({'subnet': subnet_json})
            router_json = {'name': '%srouter%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                           'tenant_id': tenant.id}
            router = neutron_connection.create_router({'router': router_json})
            port = neutron_connection.add_interface_router(router['router']['id'], {'subnet_id': subnet['subnet']['id']})
            if create_security_rules:
                sg_json = {'name': '%ssg%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                           'tenant_id': tenant.id}
                sg = neutron_connection.create_security_group({'security_group': sg_json})
                sg_rule_icmp_json = {'security_group_id': sg['security_group']['id'],
                                     'direction': 'ingress',
                                     'protocol': PROTO_NAME_ICMP,
                                     'ethertype': IPv4,
                                     'tenant_id': tenant.id}
                sg_rule_icmp = neutron_connection.create_security_group_rule({'security_group_rule': sg_rule_icmp_json})
                sg_rule_ssh_json = {'security_group_id': sg['security_group']['id'],
                                    'direction': 'ingress',
                                    'protocol': PROTO_NAME_TCP,
                                    'port_range_min': 22,
                                    'port_range_max': 22,
                                    'ethertype': IPv4,
                                    'tenant_id': tenant.id}
                sg_rule_ssh = neutron_connection.create_security_group_rule({'security_group_rule': sg_rule_ssh_json})
            for num_vm in range(vms_per_network):
                tenant_nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, tenant.name, OS_AUTH_URL)
                vm = tenant_nova_connection.servers.create('%svm%s' % (VM_PREFIX, vm_inc), image, flavor, nics=[{'net-id': network['network']['id']}, {'net-id': MGMT_NET}], security_groups=['default', sg['security_group']['id']])
                vm_inc += 1
        #We might need to put some sleep here not to overload cluster
        #sleep(5)
            

def teardown():
    print '-----Routers section-----'
    for router in neutron_connection.list_routers()['routers']:
        if router['name'].startswith(NETWORK_PREFIX):
            for subnet in neutron_connection.list_subnets()['subnets']:
                if subnet['name'].startswith(NETWORK_PREFIX):
                    try:
                        print 'Removing port with subnet <%s> from router <%s>' % (subnet['id'], router['id'])
                        neutron_connection.remove_interface_router(router['id'], {'subnet_id': subnet['id']})
                    except:
                        pass
            print 'Removing router %s' % router['id']
            neutron_connection.delete_router(router['id'])
    print '-----Tenant/VMs section-----'
    for tenant in keystone_connection.tenants.list():
        if tenant.name.startswith(TENANT_PREFIX):
            tenant_nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, tenant.name, OS_AUTH_URL)
            for vm in tenant_nova_connection.servers.list():
                if vm.name.startswith(VM_PREFIX):
                    print 'Removing vm %s' %vm.id
                    vm.delete()
            print 'Removing tenant %s' % tenant.id
            tenant.delete()
    sleep(10)
    print '-----SG section-----'
    for sg in neutron_connection.list_security_groups()['security_groups']:
        if sg['name'].startswith(NETWORK_PREFIX):
            print '-----Removing security group <%s>:<%s>' % (sg['name'], sg['id'])
            neutron_connection.delete_security_group(sg['id'])
    print '-----Network section-----'
    for network in neutron_connection.list_networks()['networks']:
        if network['name'].startswith(NETWORK_PREFIX):
            print 'Removing network %s' % network['id']
            neutron_connection.delete_network(network['id'])
    #This netns cleanup should be run on controllers after teardown
    #neutron_netns_cleanup()

#UNCOMMENT TO MAKE A TEARDOWN
teardown()
sys.exit(0)

make_environment(tenants_num=1, networks_per_tenant=1, vms_per_network=2)
