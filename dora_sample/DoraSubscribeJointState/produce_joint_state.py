from multiprocessing import shared_memory
import numpy as np
import time
import pickle


def main():
    try:
        existing_shm = shared_memory.SharedMemory(name="dora_subscribe_joint_state")
        existing_shm.close()
        existing_shm.unlink()
    except:
        pass

    shm = shared_memory.SharedMemory(name="dora_subscribe_joint_state", create = True, size=1024)
    count = 0
    try:
        while True:
            if count % 2 == 0:
                data = [0.012, -0.57, 0.0, -2.81, 0.0, 3.037, 0.741, 0.0399, 0.0399]
            else:
                data = [0.0 for _ in range(9)]
            count += 1
            data = pickle.dumps(data)
            shm.buf[:len(data)] = data
            time.sleep(1)
    finally:
        shm.close()
        shm.unlink()

if __name__ == "__main__":
    main()
