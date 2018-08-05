#!/usr/bin/python3
# Author: Patrick Salecker <mail@salecker.org>
import subprocess
import sys
import re

opt_warn = 90

def check_open_error(output):
	if output.startswith("cannot open '%s'" % pool_name):
		print("CRITICAL - %s" % output.split('\n')[0])
		sys.exit(2)

def get_perfdata():
	output = subprocess.getoutput(zfs_perfdata_command)
	check_open_error(output)
	perfdata = []
	data = {}
	for line in output.split('\n'):
		line_split = line.split('\t')
		data[line_split[1]] = line_split[2]
	data['total'] = int(data['used']) + int(data['available'])
	percent = 100.0 / data['total'] * int(data['used'])

	for key in ('used', 'available', 'total', 'logicalused', 'compressratio'):
		value = data[key]
		if key == 'compressratio':
			unit = ""
			value = value[:-1]
		else:
			unit = "B"
		perfdata.append("%s=%s%s" % (key, value, unit))
	return " ".join(perfdata), percent

if len(sys.argv) < 2:
	print("""./check_zpool.py <pool name>

e.g. ./check_zpool.py data
""")
	sys.exit(3)
elif '--test' in sys.argv:
	pool_name = 'test'
	zpool_command = "cat %s" % sys.argv[2]
	zfs_perfdata_command = "cat %s" % sys.argv[3]
	print('-- Test run %s --' % sys.argv[2])
else:
	pool_name = sys.argv[1]
	zpool_command = "sudo zpool status %s" % pool_name
	zfs_perfdata_command = "sudo zfs get -p -H used,available,logicalused,compressratio %s" % pool_name

output = subprocess.getoutput(zpool_command)
check_open_error(output)

pool = {}

config = False
columns = []
parent = None
last_key = None

for line in output.split('\n'):
	if ':' in line:
		stripped_line = line.strip()
		key = stripped_line.split(': ')[0]
		if key in ('pool', 'state', 'scan', 'status', 'action', 'see'):
			pool[key] = stripped_line.split(': ')[1]
			last_key = key
		elif line == 'config:':
			config = True
	elif config == False and line.startswith("\t"):
		pool[last_key] = pool[last_key] + "\n" +  line[1:]
	elif config == False and line.startswith("    "):
		pool[last_key] = pool[last_key] + ", " +  line[4:]
	elif config == True and line.startswith("\t"):
		line = line[1:]
		if len(columns) == 0:
			columns = line.split()
			continue
		"""
		row = dict(zip(columns, line.split()))
		if len(row) == 1 and row['NAME'] in ('cache', 'spares'):
			parent = row['NAME']
		elif row['NAME'] == pool['pool']:
			parent = row['NAME']
		elif row['NAME'].startswith('raidz'):
			row['parent'] = parent
			parent = row['NAME']
		else:
			row['parent'] = parent
		if len(row) < 6:
			continue
		print(row)
		for key in ('READ', 'WRITE', 'CKSUM'):
			if row[key] != '0':
				print('warning')
		"""

perfdata, percent = get_perfdata()
percent_string = "%0.1f%% used" % percent

scan_split = pool['scan'].split()
if scan_split[1] == 'in' and scan_split[2] == 'progress':
	scan_reason = scan_split[0]
	match = re.search(r'\s[0-9\.]+% done$', pool['scan'])
	scan_progress = match.group(0)
	scan_str = " (%s %s)" % (scan_reason, scan_progress)
	scan_perfdata = "progress=%s" % scan_progress.split("%")[0].strip()
else:
	scan_str = ""
	scan_perfdata = ""

exit_code = 0
if pool['state'] != 'ONLINE':
	print("CRITICAL - pool '%s' state is '%s'%s" % (pool['pool'], pool['state'], scan_str), end=" ")
	exit_code = 2
elif 'action' in pool:
	print("WARNING - pool '%s' requires action%s" % (pool['pool'], scan_str))
	print(pool['status'])
	exit_code = 1
elif percent > opt_warn:
	print("WARNING - pool '%s' %s" % (pool['pool'], percent_string), end=" ")
	exit_code = 1
elif pool['scan'].startswith('scrub in progress'):
	print("OK - pool '%s' scrub in progress%s\n%s" % (pool['pool'], scan_str, pool['scan']), end=" ")
else:
	print("OK - pool '%s' %s" % (pool['pool'], percent_string), end=" ")

print('|', perfdata, scan_perfdata)
sys.exit(exit_code)
