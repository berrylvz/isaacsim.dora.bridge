from dora import Node
from dora import DoraStatus
import pyarrow as pa
import numpy as np
import random
import cv2


def inference(image, joint_state):
    next_joint_state_data = [random.uniform(-3.13, 3.13) for _ in range(9)]
    return next_joint_state_data

def main():
    node = Node()

    image = None
    joint_state = None
    for event in node:
        if event["type"] == "INPUT":
            event_id = event["id"]
            if event_id == "tick":
                if image is not None and joint_state is not None:
                    next_joint_state = inference(image, joint_state)
                    node.send_output(output_id="joint_state", data=pa.array(next_joint_state), metadata={})
            elif event_id == "image":
                image = event["value"].to_pylist()[0]
            elif event_id == "joint_state":
                joint_state = event["value"].to_pylist()
            
            if image is not None:
                image_data = image["image"]
                layout = image["layout"]
                image_data = np.array(image_data, dtype=np.uint8).reshape(layout["height"], layout["width"], layout["channels"])
                image_data = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR)
                image_data = np.transpose(image_data, (1, 0, 2))
                cv2.imshow("image", image_data)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return DoraStatus.STOP

if __name__ == "__main__":
    main()
