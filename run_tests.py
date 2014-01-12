#!/usr/bin/env python
from novaclient.v1_1 import client as novacli
from keystoneclient.v2_0 import client as keystonecli
from neutronclient.neutron import client as neutroncli
#from neutron.agent.netns_cleanup_util import main as neutron_netns_cleanup

from paramiko import MissingHostKeyPolicy, SSHClient

import json
import sys
import time

#THIS SHOULD BE ADMIN CREDENTIALS
OS_USERNAME = 'admin'
OS_PASSWORD = 'admin'
OS_TENANT = 'admin'
OS_AUTH_URL = 'http://192.168.0.100:5000/v2.0/'

#VM SSH CREDENTIALS
VM_USERNAME = 'root'
VM_PASSWORD = 'Mirantis01'

#OPENSTACK INFO
MGMT_NET = 'c2e03d07-1e2e-4cd8-ba70-64b8bef5abf3'
IMAGE_ID = '02a1b2cf-6de7-4666-ba32-86df95f6faaa'
FLAVOR_ID = 1

#OBJECT PREFIX
TENANT_PREFIX = 'test'
VM_PREFIX = 'test'
NETWORK_PREFIX = 'test'
CIDR_PREFIX = '10.10'

keystone_connection = keystonecli.Client(username=OS_USERNAME, password=OS_PASSWORD, tenant_name=OS_TENANT, auth_url=OS_AUTH_URL)
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
    octet = 0
    vm_inc = 11
    image = nova_connection.images.get(IMAGE_ID)
    flavor = nova_connection.flavors.get(FLAVOR_ID)
    admin_user_id = keystone_connection.users.find(name=OS_USERNAME).id
    member_role_id = keystone_connection.roles.find(name='Member').id
    for num_tenant in range(1, tenants_num+1):
        tenant = keystone_connection.tenants.create('%stenant%s' % (TENANT_PREFIX, num_tenant))
        keystone_connection.roles.add_user_role(admin_user_id, member_role_id, tenant=tenant.id)
        for num_network in range(networks_per_tenant):
            network = {'name': '%snet%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                       'admin_state_up': True,
                       'tenant_id': tenant.id}
            net = neutron_connection.create_network({'network': network})
            subnet = {'name': '%ssubnet%s' % (NETWORK_PREFIX, num_tenant*10+num_network),
                      'network_id': net['network']['id'],
                      'tenant_id': tenant.id,
                      'enable_dhcp': True,
                      'cidr': '%s.%s.0/24' % (CIDR_PREFIX, octet), 'ip_version': 4}
            octet += 1
            sub = neutron_connection.create_subnet({'subnet': subnet})
            for num_vm in range(vms_per_network):
                tenant_nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, tenant.name, OS_AUTH_URL)
                vm = tenant_nova_connection.servers.create('%svm%s' % (VM_PREFIX, vm_inc), image, flavor, nics=[{'net-id': net['network']['id']}, {'net-id': MGMT_NET}])
                vm_inc += 1
        #We might need to put some sleep here not to overload cluster
        #time.sleep(5)
            

def teardown():
    for tenant in keystone_connection.tenants.list():
        if tenant.name.startswith(TENANT_PREFIX):
            tenant_nova_connection = novacli.Client(OS_USERNAME, OS_PASSWORD, tenant.name, OS_AUTH_URL)
            for vm in tenant_nova_connection.servers.list():
                if vm.name.startswith(VM_PREFIX):
                    vm.delete()
            tenant.delete()
    time.sleep(10)
    for network in neutron_connection.list_networks()['networks']:
        if network['name'].startswith(NETWORK_PREFIX):
            neutron_connection.delete_network(network['id'])
    time.sleep(10)
    #This netns cleanup should be run on controllers after teardown
    #neutron_netns_cleanup()

#UNCOMMENT TO MAKE A TEARDOWN
teardown()
sys.exit(0)

#make_environment(tenants_num=5, networks_per_tenant=2, vms_per_network=3)
