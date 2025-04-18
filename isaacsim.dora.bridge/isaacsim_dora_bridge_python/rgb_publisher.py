import omni.replicator.core as rep
from listener_and_writer import DoraRGBListener, DoraRGBWriter
import json
import os
import asyncio

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)
camera_cfg_file_path = dir_path + "/camera_cfg.json"
with open(camera_cfg_file_path, "r", encoding="utf-8") as f:
    camera_cfg = json.load(f)


async def rgb_publish():
    rp = rep.create.render_product(
        camera_cfg["path"], (camera_cfg["width"], camera_cfg["height"]), force_new = True
    )
    dora_rgb_listener = DoraRGBListener()
    dora_rgb_writer = DoraRGBWriter(dora_rgb_listener)
    dora_rgb_writer.attach(rp)
    for i in range(3):
        print(f"Step: {i}")
        await rep.orchestrator.step_async()
        print(str(dora_rgb_writer.listener.get_rgb_data()))
    dora_rgb_writer.detach()
    rp.destroy()
    await rep.orchestrator.wait_until_complete_async()

asyncio.ensure_future(rgb_publish())