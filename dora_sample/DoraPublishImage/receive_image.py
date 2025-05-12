import numpy as np
from dora import Node
import pyarrow as pa


def main():
    node = Node()

    image_data = None
    for event in node:
        if event["type"] == "INPUT":
            if event["id"] == "image":
                image_data = event["value"].to_pylist()[0]

if __name__ == "__main__":
    main()
