#!/bin/bash

rm -rf ./*.tar.gz
cd 1nic
tar cvzf ../1nic.tar.gz ./ > /dev/null
cd ../2nic
tar cvzf ../2nic.tar.gz ./ > /dev/null
cd ../3nic
tar cvzf ../3nic.tar.gz ./ > /dev/null
cd ..


