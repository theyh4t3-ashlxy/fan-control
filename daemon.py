#!/usr/bin/env python3
import os
import sys

# keep imports sane if started from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fanctl.daemon import main

if __name__ == "__main__":
    main()
