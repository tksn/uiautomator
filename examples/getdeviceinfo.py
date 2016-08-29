from __future__ import print_function
import logging
import uiautomatorminus as uiauto


def main():
    d = uiauto.Device()
    print(d.info)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
