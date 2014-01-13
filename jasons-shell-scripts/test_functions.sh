fail()
{
	STATUS=$1
	MESSAGE=$2
	if [ $STATUS -ne 0 ]; then
		echo $MESSAGE 1>&2
		exit 1
	fi
}

get_id()
{
	STATUS=$?
	RES=$1
	MESSAGE="${2}"
	VAL="${3}"
	fail $STATUS "${MESSAGE} ${RES}"
	eval $(echo "${RES}" | tail -1)
	echo $(eval echo \$$VAL)
}

allocate_port()
{
	NAME=$1
	shift
	NETWORK=$1
	shift
	SUBNET=$1
	shift
	SGROUPS=""
	echo "Groups are $SGROUPS and @ is [$@]" 1>&2
	for a in "$@"; do
		SGROUPS="$SGROUPS --security-group ${a}"
	done
	

	RES=$(neutron port-create -f shell -c id --name "${NAME}" ${SGROUPS} --fixed-ip subnet_id=$SUBNET ${NETWORK})
	if [ $? -ne 0 ]; then
		echo "Failed to create port $RES"
		return 1
	fi
	eval $(echo "$RES" | tail -1)
	echo $id
	return 0
}

launch_controlled_vm()
{
	FLAVOR=$1
	shift
	IMAGE=$1
	shift
	KEY=$1
	shift
	NAME=$1
	shift
	CONTROL_NET=$1
	shift
	CONTROL_SUBNET=$1
	shift
	CONTROL_SECURITY_GROUP=$1
	shift

	TARGET_NET=$1
	shift
	TARGET_SUBNET=$1
	shift

	TARGET_SECURITY_GROUPS="$@"

	CONTROL_NET_PORT=$(allocate_port "${NAME}-control-port" $CONTROL_NET $CONTROL_SUBNET $CONTROL_SECURITY_GROUP)
	if [ $? -ne 0 ]; then
		echo "Failed to create control net port $CONTROL_NET_PORT"
		return 1;
	fi

	VM_NET_PORT=$(allocate_port "${NAME}-target-port" $TARGET_NET $TARGET_SUBNET $TARGET_SECURITY_GROUPS)
	if [ $? -ne 0 ]; then
 		echo "Failed to create vm port $VM_NET_PORT"
 		return 1
	fi

	RES="$(openstack server create -f shell -c id  --image "${IMAGE}" --flavor "${FLAVOR}" --key-name "${KEY}" --nic "port-id=${VM_NET_PORT}" --nic "port-id=${CONTROL_NET_PORT}" "${NAME}")"
	if [ $? -ne 0 ]; then
		echo "$RES"
		return 1
	fi
	echo "$RES"
	return 0
}
