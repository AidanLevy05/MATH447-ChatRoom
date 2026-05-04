#!/bin/bash
gnome-terminal --tab --title="Plain Server" -- bash -c "python plain_server.py; exec bash"
sleep 0.5
gnome-terminal --tab --title="Plain Client 1" -- bash -c "python plain_client.py; exec bash"
sleep 0.5
gnome-terminal --tab --title="Plain Client 2" -- bash -c "python plain_client.py; exec bash"
