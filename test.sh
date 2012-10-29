#!/bin/sh

echo "test full workflow"
curl "http://$1/?Body=BW&From=+18188628962"
echo
curl "http://$1/?Body=CW&From=+18188628962"
echo
curl "http://$1/?Body=CW&From=+19715063860"
echo
curl "http://$1/?Body=AW&From=+18188628962"

echo "test user check for available washer code"
curl "http://$1/?Body=BW&From=+19715063860"
echo
curl "http://$1/?Body=AW&From=+18188628962"
