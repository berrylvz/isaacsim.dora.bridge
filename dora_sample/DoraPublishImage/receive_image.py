from multiprocessing import shared_memory
import numpy as np
import time
import pickle

camera_width = 640
camera_height = 480
rgb = 3

def main():
    existing_shm = shared_memory.SharedMemory(name="dora_publish_image", create = False)
    try:
        while True:
            image_data = pickle.loads(existing_shm.buf)
            image_data = np.array(image_data).reshape(camera_width, camera_height, rgb)
            print(f"Consumed data: {image_data.shape}")
            time.sleep(1)
    finally:
        existing_shm.close()

if __name__ == "__main__":
    main()
