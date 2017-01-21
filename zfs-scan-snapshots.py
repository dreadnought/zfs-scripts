#!/usr/bin/python3

import subprocess
import collections
import time
import hashlib

def get_output(cmd, timeout=0, timeout_ok=False):
	proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
	lines = []
	if timeout > 0:
		if not timeout_loop(timeout, proc):
			print("timeout", end=" ")
			proc.kill()
			if not timeout_ok:
				return False
			lines.append('timeout')
	while True:
		line = proc.stdout.readline().strip()
		if len(line) == 0:
			break
		lines.append(line)

	if len(lines) == 1 and lines[0] == 'timeout':
		print("only", end=" ")
		return False
	return lines

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
	first_snapshot = snapshots[0]
	last_snapshot = snapshots[-1]
	previous_snapshot = first_snapshot
	for snapshot in snapshots:
		if snapshot.startswith('week_'):
			last_weekly_snapshot = snapshot
	print(first_snapshot, '...', last_snapshot)
	for snapshot in snapshots[1:-2]:
		print("-", snapshot, end="\t")
		command = ['/sbin/zfs', 'diff', "%s@%s" % (volume, previous_snapshot), "%s@%s" % (volume, snapshot)]
		command_hash = hash_key(' '.join(command))
		cache_result = get_from_cache(command_hash, cache)
		if cache_result:
			print('(cached)', end=" ")
			zfs_diff = True
			if cache_result.startswith('>'):
				zfs_diff_len = cache_result
			else:
				zfs_diff_len = int(cache_result)
		else:
			zfs_diff = get_output(command, timeout=120, timeout_ok=True)
			if zfs_diff != False:
				zfs_diff_len = len(zfs_diff)
		if zfs_diff == False:
			# timeout
			add_to_cache(command_hash, '>0', cache)
		elif zfs_diff_len != 0:
			print('changes:', zfs_diff_len, end=" ")
			if not cache_result:
				cache_value = int(zfs_diff_len)
				if type(zfs_diff) == list and zfs_diff[0] == 'timeout':
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
		print("")
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

zfs_list = get_output(['/sbin/zfs', 'list', '-H', '-o', 'name'])
volumes = collections.OrderedDict()
todo = []
cache_file = '/var/cache/zfs-snapshots-diff.txt'

for line in zfs_list:
	volumes[line] = {'snapshots': []}

zfs_list_snapshots = get_output(['/sbin/zfs', 'list', '-H', '-o', 'name', '-t', 'snapshot'])
for line in zfs_list_snapshots:
	volume, snapshot = line.split('@', 1)
	if snapshot.startswith('rsync_'):
		continue
	volumes[volume]['snapshots'].append(snapshot)

cache = load_cache(cache_file)
for volume in volumes:
	print(volume, end=" ")
	snapshots = volumes[volume]['snapshots']
	try:
		volume_todo = scan_snapshots(volume, snapshots, cache)
	except KeyboardInterrupt:
		print("interrupted")
		break
	todo.extend(volume_todo)

if len(todo) > 0:
	print("Commands to delete empty snapshots:")
	print("\n ".join(todo))
