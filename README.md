# Info

All scripts are tested with Ubuntu 16.04 and zfsutils 0.6.5.

# Scripts

## check_zpool.py

check_zpool.py is a nagios/icinga check to test the state of a zfs pool.

### Examples

#### OK

```
# ./check_zpool.py test
OK - pool 'test' 72.8% used | used=131554135920480B available=49240834683040B total=180794970603520B logicalused=158240438841344B compressratio=1.25
```

#### WARNING

```
# ./check_zpool.py test
WARNING - pool 'test' requires action (scrub  83.92% done)
One or more devices has experienced an unrecoverable error.  An
attempt was made to correct the error.  Applications are unaffected.
| used=131554135920480B available=49240834683040B total=180794970603520B logicalused=158240438841344B compressratio=1.25
```

#### CRITICAL

```
# ./check_zpool.py test
CRITICAL - pool 'test' state is 'DEGRADED' (scrub  14.91% done) | used=131554135920480B available=49240834683040B total=180794970603520B logicalused=158240438841344B compressratio=1.25
```

## zfs-scan-snapshots.py

zfs-scan-snapshots.py is a script that searches for empty ZFS snapshots by executing *zfs diff*. 
It only shows you the empty snapshots and don't execute the destroy commands itself. 
The number of changed files between two snapshots will be cached to speed up the next run.

### Conditions

The script treats snapshot different according to their prefixes:

- rsync: Snapshots starting with *rsync_* will be ignored
- day: They will be listed for deletion if there are no changes compared with the snapshot before
- week: Like *day_*, but additional requirements are that the snapshot before starts with *week_* or *month_* and that it is not the last *week_* snapshot
- month: They will be scanned, but never be listed for deletion

Such snapshots structure can be created with [zfsnap](https://github.com/zfsnap/zfsnap) and a cronjob like this:

Note that the first and last snapshot of a (sub-)volume also can't be listed for deletion.

```
# m h  dom mon dow       user  command
00 22	* * *		root	/usr/sbin/zfSnap -a 6m -p day_ -r test
00 22	* * 0		root	/usr/sbin/zfSnap -a 12m -p week_ -r test
00 22	1 * *		root	/usr/sbin/zfSnap -a 24m -p month_ -r test
05 23	* * *		root	/usr/sbin/zfSnap -d -p day_
```

### Example

```
# ./zfs-scan-snapshots.py
test day_2016-10-18_06.02.01--6m ... day_2017-01-21_06.02.01--6m
- day_2016-10-22_06.02.01--6m	(cached) changes: 4 
- week_2016-10-23_06.01.01--12m	(cached) empty 
- day_2016-10-24_06.02.01--6m	(cached) changes: 2 
- week_2016-10-30_06.01.02--12m	(cached) empty 
- month_2016-11-01_06.00.01--24m	(cached) empty 
- month_2016-12-01_06.00.01--24m	(cached) empty 
- month_2017-01-01_06.00.01--24m	(cached) empty 
- week_2017-01-08_06.01.01--12m	empty 
- day_2017-01-14_06.02.01--6m	empty 
- week_2017-01-15_06.01.01--12m	empty 
- day_2017-01-16_06.02.01--6m	empty 
- day_2017-01-17_06.02.01--6m	empty 
- day_2017-01-18_06.02.01--6m	empty 
- day_2017-01-19_06.02.01--6m	empty 
backup/sub day_2016-11-24_06.02.01--6m ... day_2017-01-21_06.02.01--6m
- week_2016-11-27_06.01.01--12m	(cached) empty 
- month_2016-12-01_06.00.01--24m	(cached) empty 
- month_2017-01-01_06.00.01--24m	(cached) empty 
- day_2017-01-07_06.02.01--6m	(cached) changes: 110 
- week_2017-01-08_06.01.01--12m	(cached) empty 
- day_2017-01-14_06.02.01--6m	empty 
- week_2017-01-15_06.01.01--12m	empty 
- day_2017-01-16_06.02.01--6m	empty 
- day_2017-01-17_06.02.01--6m	empty 
- day_2017-01-18_06.02.01--6m	empty 
- day_2017-01-19_06.02.01--6m	changes: 2 

Commands to delete empty snapshots:
zfs destroy test@week_2017-01-08_06.01.01--12m
 zfs destroy test@day_2017-01-14_06.02.01--6m
 zfs destroy test@day_2017-01-16_06.02.01--6m
 zfs destroy test@day_2017-01-17_06.02.01--6m
 zfs destroy test@day_2017-01-18_06.02.01--6m
 zfs destroy test@day_2017-01-19_06.02.01--6m
 zfs destroy backup/sub@day_2017-01-14_06.02.01--6m
 zfs destroy backup/sub@day_2017-01-16_06.02.01--6m
 zfs destroy backup/sub@day_2017-01-17_06.02.01--6m
 zfs destroy backup/sub@day_2017-01-18_06.02.01--6m
```
