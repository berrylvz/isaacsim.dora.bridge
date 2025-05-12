from dora import Node
import pyarrow as pa
import numpy as np


def main():
    node = Node()

    joint_state = None
    for event in node:
        if event["type"] == "INPUT":
            if event["id"] == "joint_state":
                joint_state = event["value"].to_pylist()


if __name__ == "__main__":
    main()
