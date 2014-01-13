#! /bin/bash

# assume openrc loaded

DO_UPLOAD_IMAGES=${DO_UPLOAD_IMAGES:-0}
IMAGES_TO_UPLOAD=${IMAGES_TO_UPLOAD:-"jumpbox-base-01 worker-base-01 master-base-01"}
IMAGE_DISTRO=${IMAGE_DISTRO:-"Ubuntu-13.04"}
TEST_NETWORK_NAME=${TEST_NETWORK_NAME:-test-orchestration-$$}
TEST_SUBNET_NAME=${TEST_SUBNET_NAME:-testing-common-subnet}
TEST_SUBNET_CIDR=${TEST_SUBNET_CIDR:-9.0.0.0/8}
TEST_SECURITY_GROUP_NAME=${TEST_SECURITY_GROUP_NAME:-testing-common-subnet-group}
SSH_AND_PING_GROUP_NAME=${SSH_AND_PING_GROUP_NAME:-ssh-and-ping}
#TEST_PUBLIC_KEY=
TEST_PUBLIC_KEY_NAME=${TEST_PUBLIC_KEY_NAME:-testkey_$$}
ROUTABLE_NETWORK_NAME=${ROUTABLE_NETWORK_NAME:-net04_ext}
ROUTABLE_SUBNET_NAME=${ROUTABLE_SUBNET_NAME:-net04_ext__subnet}
FLOATING_NETWORK_NAME=${FLOATING_NETWORK_NAME:-net04_ext}
FLOATING_SUBNET_NAME=${FLOATING_SUBNET_NAME:-net04_ext__subnet}

if [ -z "$TEST_PUBLIC_KEY" ]; then
	echo "A public key is needed in TEST_PUBLIC_KEY" 1>&2
	exit 1
fi

. ./test_functions.sh

if [ $DO_UPLOAD_IMAGES -ne 0 ]; then
	for image in ${IMAGES_TO_UPLOAD}; do
		glance image-create --is-public True --name $(basename $image .qcow2) --disk-format qcow2 --container-format bare --file ${image} --min-disk 10 --min-ram 1
		fail $? "Can not upload $Image"
	done
fi


TEST_NETWORK_ID=$(get_id "$(neutron net-create -c id -f shell ${TEST_NETWORK_NAME})" "Can not create base network" "id")

TEST_SUBNET_ID=$(get_id "$(neutron subnet-create -c id -f shell --ip-version 4 --no-gateway --name "${TEST_SUBNET_NAME}" "${TEST_NETWORK_ID}" "${TEST_SUBNET_CIDR}")" "Can not create subnet for $TEST_NETWORK_NAME" "id" )

TEST_SECURITY_GROUP_ID=$(get_id "$(neutron security-group-create -c id -f shell --description "allow anything from my friends" "${TEST_SECURITY_GROUP_NAME}")" "Can not create security group for TEST_SECURITY_GROUP_NAME" "id")
SSH_AND_PING_GROUP_ID=$(get_id "$(neutron security-group-create -c id -f shell --description "allow ssh and ping" "${SSH_AND_PING_GROUP_NAME}")" "Can not create security group for SSH_AND_PING_GROUP_NAME" "id")

neutron security-group-rule-create  --direction ingress --remote-group-id ${TEST_SECURITY_GROUP_ID}  ${TEST_SECURITY_GROUP_ID}

neutron security-group-rule-create --protocol tcp --direction ingress --remote-group-id ${SSH_AND_PING_GROUP_ID} --port-range-min 22 --port-range-max 22 ${SSH_AND_PING_GROUP_ID}
neutron security-group-rule-create --protocol icmp --direction ingress --remote-group-id ${SSH_AND_PING_GROUP_ID} ${SSH_AND_PING_GROUP_ID}

echo "$TEST_PUBLIC_KEY" | openstack keypair create -f shell -c id --public-key /dev/stdin $TEST_PUBLIC_KEY_NAME
fail $? "Can't upload public key $TEST_PUBLIC_KEY_NAME"


ROUTABLE_NETWORK_ID=$(get_id "$(neutron net-show -c id -f shell "${ROUTABLE_NETWORK_NAME}")" "Can't find network $ROUTABLE_NETWORK_NAME" "id")
ROUTABLE_SUBNET_ID=$(get_id "$(neutron subnet-show -c id -f shell "${ROUTABLE_SUBNET_NAME}")" "Can't find subnet $ROUTABLE_SUBNET_NAME" "id")
FLOATING_NETWORK_ID=$(get_id "$(neutron net-show -c id -f shell "${FLOATING_NETWORK_NAME}")" "Can't find network $FLOATING_NETWORK_NAME" "id")
FLOATING_SUBNET_ID=$(get_id "$(neutron subnet-show -c id -f shell "${FLOATING_SUBNET_NAME}")" "Can't find subnet $FLOATING_SUBNET_NAME" "id")

JUMPBOX_ID=$(get_id "$(launch_controlled_vm m1.small jumpbox-base-01 "${TEST_PUBLIC_KEY_NAME}" jumpbox "$TEST_NETWORK_ID" "$TEST_SUBNET_ID" "$TEST_SECURITY_GROUP_ID" "$ROUTABLE_NETWORK_ID" "$ROUTABLE_SUBNET_ID" "$SSH_AND_PING_GROUP_ID")" "Can't launch jumpbox vm" "id")
echo $JUMPBOX_ID


