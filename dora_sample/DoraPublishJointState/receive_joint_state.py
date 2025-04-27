from multiprocessing import shared_memory
import numpy as np
import time
import pickle

# arm_dof = 7
# num_gripper = 2

def main():
    existing_shm = shared_memory.SharedMemory(name="dora_publish_joint_state", create = False)
    try:
        # data_array = np.ndarray((arm_dof+num_gripper,), dtype=np.uint8, buffer=existing_shm.buf)
        while True:
            # print(f"Consumed data: {data_array}")
            positions = pickle.loads(existing_shm.buf)
            print(positions)
            print(len(positions))
            time.sleep(1)
    finally:
        existing_shm.close()

if __name__ == "__main__":
    main()
