#! /usr/bin/perl -w

use strict;
use IO::File;
use utf8;

require 'functions.pl';

my $aggregates;
{
	my $fh = new IO::File( "openstack aggregate list -f csv|" ) || die "Can't setup aggregate list $!";
	$aggregates = load_csv_list($fh) || die "Failed to load aggregates $!";
}

foreach my $aggregate (@$aggregates) {
	my $id = $aggregate->{'ID'};
	my $hosts;
	my $parsed = run_shell_cmd("openstack aggregate show -f shell $id");
	if (!$parsed) { warn "Failed to run show for $id"; next; }
	$hosts = $parsed->{'hosts'};
	$hosts =~ s/^\[u'(.*)'\]/$1/;
	my (@parts) = split( /',\s+u'/, $hosts );
	map { utf8::encode($_); } @parts;
	my @results = map { run_shell_cmd("openstack aggregate remove host -f shell -c id $id $_") } @parts;
	
	run_shell_cmd("openstack aggregate delete $id") || die "Failed to delete $id";
}

