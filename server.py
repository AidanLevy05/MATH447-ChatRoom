#
# server.py
# Created: 03/30/2026
# Last Updated: 03/31/2026 by Aidan
#

import curses

from ChatServer import ChatServer


def main():
    server = ChatServer()
    curses.wrapper(server.run)


if __name__ == '__main__':
    main()
