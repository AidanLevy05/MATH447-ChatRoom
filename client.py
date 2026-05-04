#
# client.py
# Created: 03/30/2026
# Last Updated: 03/31/2026 by Aidan
#

import curses

from ChatClient import ChatClient


def main():
    client = ChatClient()
    curses.wrapper(client.run)


if __name__ == '__main__':
    main()
