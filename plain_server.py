#
# plain_server.py
# Created: 04/07/2026
# Last Updated: 04/07/2026 by Aidan
#

import curses

from PlainChatServer import PlainChatServer


def main():
    server = PlainChatServer()
    curses.wrapper(server.run)


if __name__ == '__main__':
    main()
