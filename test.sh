for file in test-files/zpool-status-*; do
	./check_zpool.py --test $file test-files/zfs-get-perfdata.txt
	echo ""
done
./check_zpool.py --test test-files/zpool-status-ok.txt test-files/zfs-get-error.txt
