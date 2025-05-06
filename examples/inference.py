from dora import Node
from dora import DoraStatus
import pyarrow as pa
from multiprocessing import shared_memory
import numpy as np
import pickle
import random
import cv2

# TODO: set the name of the shared memory
shm_name_dora_publish_image = "dora_publish_image"
shm_name_dora_publish_joint_state = "dora_publish_joint_state"
shm_name_dora_subscribe_joint_state = "dora_subscribe_joint_state"

# TODO: set the size of shm_dora_subscribe_joint_state (>= size of the joint state)
size_shm_joint_state = 1024

# TODO: set the params of the image
image_width = 640
image_height = 480
image_channels = 3

# TODO: set the length of joint state
len_joint_state = 9

def create_shm():
    shm_dora_publish_image = shared_memory.SharedMemory(name=shm_name_dora_publish_image, create=False)
    shm_dora_publish_joint_state = shared_memory.SharedMemory(name=shm_name_dora_publish_joint_state, create=False)
    try:
        shm_dora_subscribe_joint_state = shared_memory.SharedMemory(name=shm_name_dora_subscribe_joint_state)
        shm_dora_subscribe_joint_state.close()
        shm_dora_subscribe_joint_state.unlink()
    except:
        pass
    shm_dora_subscribe_joint_state = shared_memory.SharedMemory(name=shm_name_dora_subscribe_joint_state, create=True, size=size_shm_joint_state)
    return shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state

def destroy_shm(shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state):
    shm_dora_publish_image.close()
    shm_dora_publish_joint_state.close()
    shm_dora_subscribe_joint_state.close()
    shm_dora_subscribe_joint_state.unlink()

def sub_image(shm_dora_publish_image):
    image_data = pickle.loads(shm_dora_publish_image.buf)
    if image_data is not None:
        image_data = np.array(image_data, dtype=np.uint8).reshape(image_width, image_height, image_channels)
        return image_data
    else:
        return None

def sub_joint_state(shm_dora_publish_joint_state):
    joint_state_data = pickle.loads(shm_dora_publish_joint_state.buf)
    return joint_state_data

def pub_joint_state(shm_dora_subscribe_joint_state, joint_state_data):
    joint_state_data = pickle.dumps(joint_state_data)
    shm_dora_subscribe_joint_state.buf[:len(joint_state_data)] = joint_state_data

def inference(image_data, joint_state_data):
    next_joint_state_data = [random.uniform(-3.13, 3.13) for _ in range(len_joint_state)]
    return next_joint_state_data

def main(shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state):
    node = Node()

    for event in node:
        if event["type"] == "INPUT":
            image_data = sub_image(shm_dora_publish_image)
            joint_state_data = sub_joint_state(shm_dora_publish_joint_state)
            next_joint_state_data = inference(image_data, joint_state_data)
            pub_joint_state(shm_dora_subscribe_joint_state, next_joint_state_data)

            image_data = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR)
            image_data = np.transpose(image_data, (1, 0, 2))
            cv2.imshow("image", image_data)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return DoraStatus.STOP
    destroy_shm(shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state)


if __name__ == "__main__":
    shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state = create_shm()
    main(shm_dora_publish_image, shm_dora_publish_joint_state, shm_dora_subscribe_joint_state)
