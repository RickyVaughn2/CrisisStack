#!/bin/sh 
sudo apt-get update 
##on ubuntu install nodejs 
## on raspbian , install the node library in librariers folder. 
sudo apt-get -y install gzip git-core curl libssl-dev pkg-config build-essential npm
su pi
cd /home/pi
mkdir applications
cd applications 
git clone https://github.com/ether/etherpad-lite
cd etherpad-lite
npm install dirty && npm update
./bin/run.sh