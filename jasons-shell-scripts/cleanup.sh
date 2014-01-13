for a in $(neutron port-list -f csv -c id -c name --quote none | grep -- -port | awk -F, '{print $1}'); do neutron port-delete $a; done
for a in $(neutron net-list  -c id -c name -f csv --quote none | grep orchestration- | awk -F, '{print $1}'); do neutron net-delete $a; done
