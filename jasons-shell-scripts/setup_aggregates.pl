#! /usr/bin/perl -w

use strict;
use IO::File;

require 'functions.pl';

my %seen_types;
my %seen_racks;
my %hypervisors;

my %rack_and_row_types;

print STDERR "Loading node types\n";
{
  my $fh = new IO::File("node_types.txt", "r") || die "Can't read node types $!";
  while (<$fh>) {
	my $line = $_;
	$line =~ s/#.*//;
	my ($rack,$row,$type) = split( /\s/, $line);
	if (!(defined($rack) && defined($row) && defined($type))) {
	  next;
	}
	$rack_and_row_types{"${rack}-${row}"} = {
											 'rack' => $rack,
											 'row' => $row,
											 'type' => $type
											};
  }
}


print STDERR "Loading hypervisor info\n";
{ 
  my $rows = run_csv_cmd("openstack hypervisor list -f csv --quote none") || die "Can't load hypervisors $!";
  foreach my $row (@$rows) {
	my $short = $row->{'Hypervisor Hostname'};
	$short =~ s/\..*$//;		# lose the domain name
	$hypervisors{$short} = {
							'id' => $row->{'ID'},
							'hostname' => $row->{'Hypervisor Hostname'}
						   };
#	print STDERR"Storing $short, $hypervisors{$short}->{'id'}, $hypervisors{$short}->{'hostname'}\n";

  }
}

print STDERR "Loading rack descriptors\n";
{
  my $fh = new IO::File("env_10_rack_and_row_map", "r") || die "Can't read node types $!";
  while (<$fh>) {
	chomp;
	print STDERR "Working on $_\n";
	my $line = $_;
	$line =~ s/#.*//;
	my ($node,$rack,$row) = split( /\s/, $line);
	if (!(defined($node) && defined($rack) && defined($row))) {
	  next;
	}
	my $rackName = "rack-$rack";
	if (!defined($seen_racks{$rackName})) {

	  #print STDERR "openstack aggregate create -f shell -c id --zone '$rackName' '$rackName'\n";
	  my $rack = run_shell_cmd("openstack aggregate create -f shell -c id --zone '$rackName' '$rackName'");
	  if ( !$rack ) {
		warn "Failed to create rack $rackName";
	  }
	  my $rackId = $rack->{'id'};
	  print STDERR "created Rackid is $rackId for $rackName\n";

	  $seen_racks{$rackName} = $rackId;
	  print STDERR "Stored $rackName $rackId\n";
	}
	my $hypervisor = $hypervisors{$node};
	if (!$hypervisor) {
	  warn "Can't find a hypervisor entry for $node";
	  next;
	}
	my $type = $rack_and_row_types{"${rack}-${row}"};
	if (!$type) {
	  $type = "green-compute";
	} else {
	  $type = $type->{'type'};
	}
	if (!defined($seen_types{$type})) {
	  $seen_types{$type} = 1;
	  my $type = run_shell_cmd("openstack aggregate create -f shell -c id '$type'");
	} 
	
	my $addedHost = run_shell_cmd("openstack aggregate add host -f shell -c id $rackName $hypervisor->{'hostname'}");
	print "Added host $addedHost->{'id'} to $rackName\n";
	$addedHost = run_shell_cmd("openstack aggregate add host -f shell -c id $type $hypervisor->{'hostname'}");
	print "Added host $addedHost->{'id'} to $type\n";
  }
}

print STDERR "Dumping rack descriptors\n";
foreach my $rackName (keys %seen_racks) {
  system( "openstack aggregate show $rackName" );
  if ( $? != 0 ) {
	warn "Unable to list aggregate $rackName";
  }
}

