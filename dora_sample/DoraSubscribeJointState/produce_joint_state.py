from dora import Node
import pyarrow as pa
import numpy as np


def main():
    node = Node()

    count = 0
    for event in node:
        if event["type"] == "INPUT":
            if event["id"] == "tick":
                if count % 2 == 0:
                    data = [0.012, -0.57, 0.0, -2.81, 0.0, 3.037, 0.741, 0.0399, 0.0399]
                else:
                    data = [0.0 for _ in range(9)]
                count += 1
                node.send_output(output_id="joint_state", data=pa.array(data), metadata={})


if __name__ == "__main__":
    main()
