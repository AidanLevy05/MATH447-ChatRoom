#
# plain_client.py
# Created: 04/07/2026
# Last Updated: 04/07/2026 by Aidan
#

import curses

from PlainChatClient import PlainChatClient


def main():
    client = PlainChatClient()
    curses.wrapper(client.run)


if __name__ == '__main__':
    main()
