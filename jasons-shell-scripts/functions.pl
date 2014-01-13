use Text::CSV;

sub get_shell_value($$);

sub load_csv_list($);

sub load_shell_list($);
sub run_shell_cmd($);
sub run_csv_cmd($);


sub run_shell_cmd($) {
  my ($cmd) = @_;

  print STDERR "run_shell_cmd: $cmd\n";
  my $fh = new IO::File( "$cmd|" );
  if (!$fh) {
	return undef;
  }
  return load_shell_list($fh);
}

sub run_csv_cmd($) {
  my ($cmd) = @_;

  print STDERR "run_csv_cmd: $cmd\n";
  my $fh = new IO::File( "$cmd|" );
  if (!$fh) {
	return undef;
  }
  return load_csv_list($fh);
}


sub load_shell_list($) {
  my ($fh) = @_;

  my %result;

  while (<$fh>) {
	chomp;
	my ($key,$value) = split( /=/, $_, 2);
	if (!defined($value)) {
		warn "No value for $key in $_";
	} else {
		$value =~ s/^"(.*)"$/$1/;
	}
	$result{$key} = $value;
  }
  return \%result;
}

sub load_csv_list($) {
	my ($fh) = @_;
	my $csv = Text::CSV->new ( { always_quote => 1} ) || die "Can't setup CSV parsing $! " . Text::CSV->error_diag () ;
	my $row = $csv->getline($fh);
	if (!$row) {
		return undef;
	}
	$csv->column_names(@$row);
	my @result;
	while ($row = $csv->getline_hr($fh)) {
		push @result, $row;
	}
	return \@result;
}

sub get_shell_value($$) {
  my ($tag,$raw) = (@_);
  
  my ($key,$value) = split( /=/, $raw, 2);
  if ($key ne $tag) {
	warn "key tag missmatch, wanted $tag, got $key in $raw";
  }
  $value =~ s/^"(.*)"$/$1/;
  return $value;
}


1;
