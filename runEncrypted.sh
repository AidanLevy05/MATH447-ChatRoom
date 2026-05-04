#!/bin/bash
gnome-terminal --tab --title="Server" -- bash -c "python server.py; exec bash"
sleep 0.5
gnome-terminal --tab --title="Client 1" -- bash -c "python client.py; exec bash"
sleep 0.5
gnome-terminal --tab --title="Client 2" -- bash -c "python client.py; exec bash"
