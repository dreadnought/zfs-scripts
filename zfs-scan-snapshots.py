#!/usr/bin/python3

import subprocess
import collections
import time
import hashlib
import sys

megabyte = 1024 * 1024

def get_output(cmd, timeout=0, timeout_ok=False):
	proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
	lines = []
	if timeout > 0:
		if not timeout_loop(timeout, proc):
			print("timeout", end=" ")
			proc.kill()
			if not timeout_ok:
				return False, ['timeout', len(lines)]
			lines.append('timeout')
	while True:
		line = proc.stdout.readline().strip()
		if len(line) == 0:
			break
		lines.append(line)
	stderr = proc.stderr.readlines()
	if len(stderr) > 0:
		if len(stderr) == 1 and stderr[0].startswith('Unable to determine path or stats for object'):
			return False, ['error-ok', len(lines)]
		print("Error:", stderr)
		return False, ['error']

	if len(lines) == 1 and lines[0] == 'timeout':
		print("only", end=" ")
		return False, ['timeout', 0]
	return True, lines

def timeout_loop(seconds, proc):
	done = 0
	while True:
		mseconds = seconds / 100
		time.sleep(mseconds)
		if proc.poll() != None:
			return True

		if done > seconds:
			break
		done += mseconds
	return False

def scan_snapshots(volume, snapshots, cache):
	todo = []
	if len(snapshots) < 3:
		print('has less than 3 snapshots')
		return todo
	first_snapshot = snapshots[0][0]
	last_snapshot = snapshots[-1][0]
	previous_snapshot = first_snapshot
	previous_used = int(snapshots[0][1])
	for snapshot, used in snapshots:
		if snapshot.startswith('week_'):
			last_weekly_snapshot = snapshot
	print(first_snapshot, '...', last_snapshot)
	x = 0
	num_snapshots_str = "%s" % (len(snapshots) - 3)
	for snapshot, used in snapshots[1:-2]:
		x += 1
		x_str = "%s%s" % (" " * (len(num_snapshots_str) - len(str(x))), x)
		print('[%s/%s]' % (x_str, num_snapshots_str), "-", snapshot, end="\t")
		# STAGE 0: read from cache
		command = ['/sbin/zfs', 'diff', "%s@%s" % (volume, previous_snapshot), "%s@%s" % (volume, snapshot)]
		command_hash = hash_key(' '.join(command))
		cache_result = get_from_cache(command_hash, cache)
		used_diff = used - previous_used
		if cache_result:
			print('(cached)', end=" ")
			success = True
			if not cache_result.isdigit():
				zfs_diff_len = cache_result
			else:
				zfs_diff_len = int(cache_result)
		# STAGE 1: compare the used size
		elif used_diff < megabyte * -1 or used_diff > megabyte * 1:
			#add_to_cache(command_hash, cache_value, cache)
			success = True
			cache_result = True
			zfs_diff_len = 'by-size-change %s Byte' % (used_diff)
		# STAGE 2: use "zfs diff" for snapshots where the used size stayed the same
		else:
			success, output_lines = get_output(command, timeout=120, timeout_ok=True)
			if success:
				zfs_diff_len = len(output_lines)
		if not success:
			if 'timeout' in output_lines:
				add_to_cache(command_hash, '>0', cache)
			elif 'error-ok' in output_lines:
				print("error-ok", len(output_lines))
				add_to_cache(command_hash, ">%s" % len(output_lines), cache)
			elif 'error' in output_lines:
				pass
		elif zfs_diff_len != 0:
			print('changes:', zfs_diff_len, end=" ")
			if not cache_result:
				cache_value = int(zfs_diff_len)
				if success and output_lines[0] == 'timeout':
					cache_value = ">%s" % (int(cache_value) - 1)
				add_to_cache(command_hash, cache_value, cache)
		elif zfs_diff_len == 0:
			print("empty", end=" ")
			cmd = "zfs destroy %s@%s" % (volume, snapshot)
			prefix = snapshot.split('_')[0]
			if prefix == 'day':
				todo.append(cmd)
			elif prefix == 'week' and (previous_snapshot.startswith('week_') or previous_snapshot.startswith('month_')):
				if snapshot != last_weekly_snapshot:
					todo.append(cmd)
				else:
					print("but the latest weekly snapshot", end=" ")
			elif not cache_result:
				add_to_cache(command_hash, zfs_diff_len, cache)
		previous_snapshot = snapshot
		previous_used = used
		print("", flush=True)
	return todo

def load_cache(cache_file):
	cache = {}
	with open(cache_file) as f:
		for line in f:
			key, value = line.split()
			cache[key] = value
	return cache

def add_to_cache(hash, value, cache):
	cache[hash] = value
	with open(cache_file, 'a') as f:
		f.write("%s %s\n" %(hash, value))

def hash_key(key):
	return hashlib.sha256(str.encode(key)).hexdigest()

def get_from_cache(hash, cache):
	if hash in cache:
		return cache[hash]
	else:
		False

success, zfs_list = get_output(['/sbin/zfs', 'list', '-H', '-o', 'name'])
volumes = collections.OrderedDict()
todo = []
cache_file = '/var/cache/zfs-snapshots-diff.txt'
if len(sys.argv) == 2:
	filter_volume = sys.argv[1]
else:
	filter_volume = None

for line in zfs_list:
	volumes[line] = {'snapshots': []}

success, zfs_list_snapshots = get_output(['/sbin/zfs', 'list', '-H', '-p', '-o', 'name,used', '-t', 'snapshot'])
for line in zfs_list_snapshots:
	name, used = line.split('\t', 1)
	volume, snapshot = name.split('@', 1)
	if snapshot.startswith('rsync_'):
		continue
	volumes[volume]['snapshots'].append([snapshot, int(used)])

cache = load_cache(cache_file)
for volume in volumes:
	print(volume, end=" ")
	if filter_volume and not volume.startswith("%s" % filter_volume):
		print("skip by filter")
		continue
	snapshots = volumes[volume]['snapshots']
	try:
		volume_todo = scan_snapshots(volume, snapshots, cache)
	except KeyboardInterrupt:
		print("interrupted")
		break
	todo.extend(volume_todo)
	print("", flush=True)

if len(todo) > 0:
	print("Commands to delete empty snapshots:")
	print("\n ".join(todo))
